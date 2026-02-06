import os
import asyncio
from typing import Optional, List
from db.client import supabase_client
from config.settings import settings
from utils.file_parser import FileParser
from utils.text_chunker import TextChunker
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service
from utils.logger import logger
from utils.embedding_queue import get_embedding_queue, EmbeddingJob, EmbeddingQueue


class DocumentService:
    """
    Document processing service with global concurrency control.

    Features:
    - Parallel processing of multiple documents
    - GLOBAL concurrency limits prevent Qdrant timeouts
    - Progress tracking per document
    - Automatic retry on transient failures

    Key fix: Uses shared semaphores across all documents to prevent
    overwhelming Qdrant when multiple PDFs are uploaded together.
    """

    def __init__(self):
        self.client = supabase_client
        self.file_parser = FileParser()
        self.text_chunker = TextChunker(
            chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP
        )
        # Batch size - kept same as user requested
        self.batch_size = getattr(settings, "EMBEDDING_BATCH_SIZE", 100)

    async def process_document(
        self, document_id: str, project_id: str, file_path: str, filename: str
    ):
        """Process uploaded document: extract text, chunk, embed, and store"""
        try:
            # Update status to processing
            await self._update_document_status(document_id, "processing")

            loop = asyncio.get_running_loop()

            # 1. Extract text (Run in thread pool to avoid blocking)
            logger.info(f"Extracting text from {filename}")
            await self._update_document_status(
                document_id, "processing", "Extracting text..."
            )
            text = await loop.run_in_executor(
                None, self.file_parser.extract_text, file_path
            )

            if not text:
                await self._update_document_status(
                    document_id, "failed", "Failed to extract text"
                )
                return

            # 2. Chunk text (Run in thread pool to avoid blocking)
            logger.info(f"Chunking text from {filename}")
            await self._update_document_status(
                document_id, "processing", "Chunking text..."
            )
            chunks = await loop.run_in_executor(
                None, lambda: self.text_chunker.chunk_text(text)
            )

            if not chunks:
                await self._update_document_status(
                    document_id, "failed", "No chunks generated"
                )
                return

            # 3. Create collection
            collection_name = f"project_{project_id}"
            await qdrant_service.create_collection(collection_name)

            # 4. Process embeddings with global limits
            await self._process_embeddings_direct(
                chunks, document_id, filename, collection_name
            )

            # 5. Update status to completed
            await self._update_document_status(document_id, "completed")
            logger.info(f"Document {filename} processed successfully")

            # 6. Generate Topics
            try:
                from services.mcq_service import mcq_service

                await mcq_service.generate_document_topics(project_id, document_id)
            except Exception as topic_err:
                logger.error(f"Failed to generate topics for {filename}: {topic_err}")

        except Exception as e:
            logger.error(f"Error processing document {filename}: {str(e)}")
            await self._update_document_status(document_id, "failed", str(e))

    async def _process_embeddings_direct(
        self, chunks: List[str], document_id: str, filename: str, collection_name: str
    ):
        """
        Process embeddings using GLOBAL concurrency limits.

        This ensures multiple documents don't overwhelm Qdrant.
        """
        # Prepare batches
        batches = []
        for i in range(0, len(chunks), self.batch_size):
            batch_data = chunks[i : i + self.batch_size]
            batches.append((i, batch_data))

        total_batches = len(batches)

        # Get GLOBAL semaphores - shared across all documents
        embed_semaphore = EmbeddingQueue.get_embed_semaphore()
        db_semaphore = EmbeddingQueue.get_db_semaphore()

        logger.info(
            f"[{filename}] Starting embedding: {len(chunks)} chunks, "
            f"{total_batches} batches (using global limits)"
        )

        completed = [0]  # Use list for mutable counter in closure
        failed_batches = []

        async def process_batch(
            batch_idx: int, start_index: int, batch_data: List[str]
        ):
            retries = 3
            for attempt in range(retries):
                try:
                    # Use GLOBAL embedding semaphore
                    async with embed_semaphore:
                        batch_embeddings = await embedding_service.generate_embeddings(
                            batch_data
                        )

                    # Prepare metadata
                    batch_metadata = [
                        {
                            "document_id": document_id,
                            "document_name": filename,
                            "chunk_id": start_index + k,
                        }
                        for k in range(len(batch_data))
                    ]

                    # Use GLOBAL DB semaphore for upsert
                    async with db_semaphore:
                        await qdrant_service.upsert_chunks(
                            collection_name=collection_name,
                            chunks=batch_data,
                            embeddings=batch_embeddings,
                            metadata=batch_metadata,
                        )

                    # Update progress
                    completed[0] += 1
                    if completed[0] % 5 == 0 or completed[0] == total_batches:
                        logger.info(
                            f"[{filename}] Progress: {completed[0]}/{total_batches} batches"
                        )
                    return

                except Exception as e:
                    error_str = str(e).lower()
                    is_retryable = any(
                        x in error_str
                        for x in [
                            "429",
                            "too many requests",
                            "timeout",
                            "timed out",
                            "connection",
                            "temporary",
                            "unavailable",
                        ]
                    )

                    if is_retryable and attempt < retries - 1:
                        wait_time = (2**attempt) + (0.1 * (batch_idx % 5))
                        logger.warning(
                            f"[{filename}] Batch {batch_idx + 1} retry {attempt + 1}/{retries} "
                            f"in {wait_time:.1f}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    logger.error(f"[{filename}] Batch {batch_idx + 1} failed: {e}")
                    if attempt == retries - 1:
                        failed_batches.append(batch_idx)
                        # Don't raise - let other batches complete
                        return

        # Run batches - they'll be limited by global semaphores
        tasks = [
            process_batch(idx, start_idx, batch)
            for idx, (start_idx, batch) in enumerate(batches)
        ]
        await asyncio.gather(*tasks)

        if failed_batches:
            logger.warning(
                f"[{filename}] Completed with {len(failed_batches)} failed batches: {failed_batches}"
            )
        else:
            logger.info(f"[{filename}] Embedding completed: {total_batches} batches")

    async def _update_document_status(
        self, document_id: str, status: str, message: Optional[str] = None
    ):
        """Update document processing status in database"""
        try:
            update_data = {"upload_status": status}
            if status == "completed":
                update_data["error_message"] = None
            elif message:
                update_data["error_message"] = message

            self.client.table("documents").update(update_data).eq(
                "id", document_id
            ).execute()

        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")

    async def delete_document(self, project_id: str, document_id: str):
        """Delete document from DB and Vector Store"""
        try:
            collection_name = f"project_{project_id}"
            await qdrant_service.delete_vectors(collection_name, document_id)
            self.client.table("documents").delete().eq("id", document_id).execute()
            logger.info(f"Deleted document {document_id} from project {project_id}")
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise

    async def process_chunks_direct(
        self, document_id: str, project_id: str, filename: str, chunks: List[str]
    ):
        """
        Process chunks received directly from PDF service.

        Uses parallel processing with global concurrency limits.
        All documents process simultaneously but share resource limits.
        """
        queue = get_embedding_queue()

        # Update status
        queue_stats = queue.get_queue_stats()
        active = queue_stats["processing"] + queue_stats["queued"]

        if active > 0:
            await self._update_document_status(
                document_id, "embedding", f"Processing with {active} other documents..."
            )
        else:
            await self._update_document_status(
                document_id, "embedding", "Generating embeddings..."
            )

        # Create the processing callback
        async def process_job(job: EmbeddingJob):
            """Called by queue for processing"""
            try:
                await self._update_document_status(
                    document_id, "embedding", "Generating embeddings..."
                )

                logger.info(f"Processing {len(chunks)} chunks for document {filename}")

                # Create Qdrant collection
                collection_name = f"project_{project_id}"
                await qdrant_service.create_collection(collection_name)

                # Process embeddings with progress tracking
                await self._process_embeddings_with_progress(
                    chunks, document_id, filename, collection_name, job
                )

                # Update status to completed
                await self._update_document_status(document_id, "completed")
                logger.info(f"Document {filename} embeddings completed successfully")

                # Generate Topics
                try:
                    from services.mcq_service import mcq_service

                    await mcq_service.generate_document_topics(project_id, document_id)
                except Exception as topic_err:
                    logger.error(
                        f"Failed to generate topics for {filename}: {topic_err}"
                    )

            except Exception as e:
                logger.error(f"Error processing chunks for {filename}: {str(e)}")
                await self._update_document_status(document_id, "failed", str(e))
                raise  # Re-raise so queue marks job as failed

        # Enqueue the job
        await queue.enqueue(
            document_id=document_id,
            project_id=project_id,
            filename=filename,
            chunks=chunks,
            process_callback=process_job,
        )

    async def _process_embeddings_with_progress(
        self,
        chunks: List[str],
        document_id: str,
        filename: str,
        collection_name: str,
        job: EmbeddingJob,
    ):
        """
        Process embeddings with progress tracking using GLOBAL limits.

        Key difference from before: Uses shared semaphores so multiple
        documents don't overwhelm the database.
        """
        queue = get_embedding_queue()

        # Prepare batches
        batches = []
        for i in range(0, len(chunks), self.batch_size):
            batch_data = chunks[i : i + self.batch_size]
            batches.append((i, batch_data))

        total_batches = len(batches)
        job.total_batches = total_batches

        # Get GLOBAL semaphores
        embed_semaphore = EmbeddingQueue.get_embed_semaphore()
        db_semaphore = EmbeddingQueue.get_db_semaphore()

        logger.info(
            f"[{filename}] Starting embedding: {len(chunks)} chunks, "
            f"{total_batches} batches (global limits active)"
        )

        completed = [0]
        failed_batches = []

        async def process_batch(
            batch_idx: int, start_index: int, batch_data: List[str]
        ):
            retries = 3
            for attempt in range(retries):
                try:
                    # Use GLOBAL embedding semaphore
                    async with embed_semaphore:
                        batch_embeddings = await embedding_service.generate_embeddings(
                            batch_data
                        )

                    # Prepare metadata
                    batch_metadata = [
                        {
                            "document_id": document_id,
                            "document_name": filename,
                            "chunk_id": start_index + k,
                        }
                        for k in range(len(batch_data))
                    ]

                    # Use GLOBAL DB semaphore
                    async with db_semaphore:
                        await qdrant_service.upsert_chunks(
                            collection_name=collection_name,
                            chunks=batch_data,
                            embeddings=batch_embeddings,
                            metadata=batch_metadata,
                        )

                    # Update progress
                    completed[0] += 1
                    queue.update_job_progress(job.job_id, completed[0], total_batches)

                    if completed[0] % 5 == 0 or completed[0] == total_batches:
                        progress_pct = int((completed[0] / total_batches) * 100)
                        logger.info(
                            f"[{filename}] Progress: {completed[0]}/{total_batches} ({progress_pct}%)"
                        )
                    return

                except Exception as e:
                    error_str = str(e).lower()
                    is_retryable = any(
                        x in error_str
                        for x in [
                            "429",
                            "too many requests",
                            "timeout",
                            "timed out",
                            "connection",
                            "temporary",
                            "unavailable",
                        ]
                    )

                    if is_retryable and attempt < retries - 1:
                        wait_time = (2**attempt) + (0.1 * (batch_idx % 5))
                        logger.warning(
                            f"[{filename}] Batch {batch_idx + 1} retry {attempt + 1}/{retries} "
                            f"in {wait_time:.1f}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    logger.error(f"[{filename}] Batch {batch_idx + 1} error: {e}")
                    if attempt == retries - 1:
                        failed_batches.append(batch_idx)
                        return

        # Run all batches - global semaphores control actual concurrency
        tasks = [
            process_batch(idx, start_idx, batch)
            for idx, (start_idx, batch) in enumerate(batches)
        ]
        await asyncio.gather(*tasks)

        if failed_batches:
            error_msg = f"{len(failed_batches)} batches failed"
            logger.error(f"[{filename}] {error_msg}")
            raise Exception(error_msg)

        logger.info(f"[{filename}] Embedding completed: {total_batches} batches")


document_service = DocumentService()
