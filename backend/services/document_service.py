import os
import time
import asyncio
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from db.client import get_supabase_client, async_db
from config.settings import settings
from utils.file_parser import FileParser
from utils.text_chunker import TextChunker
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service
from utils.logger import logger
from utils.embedding_queue import get_embedding_queue, EmbeddingJob, EmbeddingQueue
from utils.progress_manager import get_progress_manager


class DocumentService:
    """
    Unified document processing service.

    Handles the complete pipeline:
        extract → save txt to Supabase → chunk → embed → topics → knowledge graph

    Storage strategy:
        - Raw uploaded files are NOT stored permanently (temp file is deleted after extraction)
        - Only the extracted .txt is stored in the Supabase 'texts/' bucket
        - This is 10-50x smaller than the original PDF

    Features:
    - Parallel batch embedding with global concurrency control (configurable via settings.py)
    - Real-time SSE progress for frontend
    - Automatic temp file cleanup
    - Creates book record if document is marked public
    - Retry with exponential backoff for transient failures
    """

    def __init__(self):
        self.client = get_supabase_client()
        self.file_parser = FileParser()
        self.text_chunker = TextChunker(
            chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP
        )
        self.batch_size = getattr(settings, "EMBEDDING_BATCH_SIZE", 100)
        # Dedicated thread pool for CPU-heavy file extraction
        # Prevents PDF parsing from competing with embedding API calls for threads
        self._extraction_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="file_extract"
        )

    async def process_document(
        self,
        document_id: str,
        project_id: str,
        file_path: str,
        filename: str,
        user_id: str = "",
        book_meta: Optional[Dict[str, Any]] = None,
    ):
        """
        Process uploaded document: extract text → save txt → chunk → embed → topics → graph.
        Optionally creates a book record if book_meta is provided.

        Emits SSE progress events at each stage for real-time frontend updates.
        """
        progress = get_progress_manager()

        try:
            # Gate with doc_semaphore: max MAX_CONCURRENT_DOCUMENT_UPLOADS docs process concurrently.
            doc_semaphore = EmbeddingQueue.get_doc_semaphore()

            # Notify frontend if doc is queued (semaphore full)
            if doc_semaphore.locked():
                await progress.emit(
                    document_id, "queued", 0,
                    "Waiting for other documents to finish..."
                )
                await self._update_document_status(
                    document_id, "queued", "Waiting for processing slot..."
                )
                logger.info(f"[{filename}] Queued — waiting for doc_semaphore slot")

            async with doc_semaphore:
                await self._run_pipeline(
                    document_id, project_id, file_path, filename, progress,
                    user_id=user_id, book_meta=book_meta
                )

        except Exception as e:
            logger.error(f"Error processing document {filename}: {str(e)}")
            await self._update_document_status(document_id, "failed", str(e))
            await progress.emit(document_id, "failed", 0, str(e))

        finally:
            # Always clean up temp file
            self._cleanup_temp_file(file_path)

    async def _run_pipeline(
        self,
        document_id: str,
        project_id: str,
        file_path: str,
        filename: str,
        progress,
        user_id: str = "",
        book_meta: Optional[Dict[str, Any]] = None,
    ):
        """
        The actual processing pipeline, called inside doc_semaphore.
        Separated so the semaphore scope is clear.
        """
        try:
            await self._update_document_status(document_id, "processing")
            await progress.emit(document_id, "extracting", 0, "Extracting text...")

            loop = asyncio.get_running_loop()

            # ── 1. Extract text ────────────────────────────────────────────────
            logger.info(f"Extracting text from {filename}")
            await self._update_document_status(
                document_id, "processing", "Extracting text..."
            )
            text = await loop.run_in_executor(
                self._extraction_executor, self.file_parser.extract_text, file_path
            )

            if not text:
                raise ValueError(
                    "Extraction failed: no usable text could be extracted from the document."
                )

            await progress.emit(
                document_id, "extracting", 100,
                f"Extracted {len(text)} characters"
            )

            # ── 2+3. Save extracted text (texts/ bucket) and chunk it, in parallel ──
            async def save_text():
                path = await self._save_text_to_storage(
                    document_id, project_id, filename, text
                )
                if path:
                    await self._update_document_text_path(document_id, path)
                return path

            logger.info(f"Chunking text from {filename}")
            await progress.emit(document_id, "chunking", 0, "Splitting into chunks...")
            text_storage_path, chunks, _ = await asyncio.gather(
                save_text(),
                loop.run_in_executor(None, lambda: self.text_chunker.chunk_text(text)),
                # Keep the original PDF so students can read it in the app and
                # citations can open at the exact passage
                self._save_original_to_storage(document_id, project_id, filename, file_path),
            )

            if not chunks:
                await self._update_document_status(
                    document_id, "failed", "No chunks generated"
                )
                await progress.emit(
                    document_id, "failed", 0, "No chunks generated from text"
                )
                return

            await progress.emit(
                document_id, "chunking", 100,
                f"Generated {len(chunks)} chunks"
            )

            # ── 4. Create Qdrant collection ────────────────────────────────────
            collection_name = f"project_{project_id}"
            await qdrant_service.create_collection(collection_name)

            # ── 5+6. Embeddings and topic extraction run in parallel ───────────
            # Topics are extracted from the stored text, so they don't need to
            # wait for the vectors; the slower of the two sets the pace.
            await self._update_document_status(
                document_id, "processing", "Indexing and finding topics..."
            )
            await progress.emit(
                document_id, "embedding", 0,
                f"Embedding {len(chunks)} chunks..."
            )
            llm_semaphore = EmbeddingQueue.get_llm_semaphore()

            async def embed():
                try:
                    await self._process_embeddings_direct(
                        chunks, document_id, filename, collection_name
                    )
                    return None
                except Exception as embed_err:
                    return embed_err

            async def topics():
                try:
                    from services.mcq_service import mcq_service

                    async with llm_semaphore:
                        await mcq_service.generate_document_topics(project_id, document_id)
                    logger.info(f"Topics generated for {filename}")
                except Exception as topic_err:
                    logger.error(f"Failed to generate topics for {filename}: {topic_err}")

            embed_err, _ = await asyncio.gather(embed(), topics())
            if embed_err:
                if not text_storage_path:
                    raise embed_err
                # The text is saved: the document stays usable (search falls back
                # to the stored text) and the index is rebuilt in the background
                # by ensure_project_indexed once the embedding provider works.
                logger.error(
                    f"[{filename}] Embedding failed, continuing without vectors "
                    f"(will re-index later): {embed_err}"
                )
                self._reindex_failed_at[document_id] = time.time()
                # Drop a partial index so the rebuild (which looks for documents
                # without vectors) redoes this document completely
                try:
                    await qdrant_service.delete_vectors(collection_name, document_id)
                except Exception as del_err:
                    logger.warning(f"[{filename}] Could not clear partial vectors: {del_err}")
            await progress.emit(document_id, "topics", 100, "Topics ready")

            # ── 7. Auto-build knowledge graph from all project topics ──────────
            await progress.emit(document_id, "graph", 0, "Building knowledge graph...")
            try:
                from services.knowledge_graph_service import knowledge_graph

                from services.topic_ordering import topics_in_book_order

                # Includes the current doc: it is marked completed only after this step
                docs = await async_db(
                    lambda: get_supabase_client()
                    .table("documents")
                    .select("id, topics, upload_status")
                    .eq("project_id", project_id)
                    .in_("upload_status", ["completed", "processing"])
                    .order("created_at")
                    .execute()
                )
                # Book order keeps related topics in the same LLM batch
                all_topics = topics_in_book_order(
                    [d for d in (docs.data or [])
                     if d["upload_status"] == "completed" or d["id"] == document_id]
                )
                if len(all_topics) >= 2:
                    logger.info(
                        f"Auto-building knowledge graph with {len(all_topics)} topics"
                    )
                    async with llm_semaphore:
                        await knowledge_graph.build_graph_from_topics(
                            project_id, all_topics, force_rebuild=True
                        )
                    logger.info(f"Knowledge graph built for {filename}")
                await progress.emit(document_id, "graph", 100, "Knowledge graph updated")
            except Exception as kg_err:
                logger.error(f"Failed to build knowledge graph: {kg_err}")
                await progress.emit(document_id, "graph", 100, "Knowledge graph skipped")

            # ── 8. Update status to completed ──────────────────────────────────
            await self._update_document_status(document_id, "completed")
            await progress.emit(
                document_id, "completed", 100, "Document processed successfully"
            )
            logger.info(f"Document {filename} processed successfully")

            # ── 9. Create book record if public ───────────────────────────────
            if book_meta:
                await self._create_book_record(document_id, text_storage_path, book_meta)

        except Exception as e:
            logger.error(f"Error in pipeline for {filename}: {str(e)}")
            await self._update_document_status(document_id, "failed", str(e))
            await progress.emit(document_id, "failed", 0, str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Storage helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _save_text_to_storage(
        self,
        document_id: str,
        project_id: str,
        filename: str,
        text: str,
    ) -> Optional[str]:
        """
        Upload extracted text as a .txt file to Supabase 'texts/' bucket.
        This is much smaller than the original file (10-50x compression).

        Returns the storage path on success, None on failure (non-fatal).
        """
        try:
            storage_path = f"{project_id}/{document_id}.txt"
            text_bytes = text.encode("utf-8")

            def _upload():
                supabase = get_supabase_client()
                supabase.storage.from_(settings.BOOK_IMPORT_TEXTS_BUCKET).upload(
                    file=text_bytes,
                    path=storage_path,
                    file_options={"content-type": "text/plain"},
                )

            await async_db(_upload)
            logger.info(
                f"Saved extracted text to texts/{storage_path} "
                f"({len(text_bytes):,} bytes)"
            )
            return storage_path

        except Exception as e:
            logger.error(f"Failed to save text to storage for {document_id}: {e}")
            return None

    ORIGINALS_BUCKET = "documents"
    MAX_ORIGINAL_BYTES = 50 * 1024 * 1024  # Supabase free-tier per-file limit

    async def _save_original_to_storage(
        self, document_id: str, project_id: str, filename: str, file_path: str
    ) -> Optional[str]:
        """Store the uploaded PDF (originals of other types aren't viewable, so skip them)."""
        try:
            if not filename.lower().endswith(".pdf") or not os.path.exists(file_path):
                return None
            if os.path.getsize(file_path) > self.MAX_ORIGINAL_BYTES:
                logger.info(f"[{filename}] Original too large to store; reader will show text")
                return None
            path = f"{project_id}/{document_id}.pdf"
            with open(file_path, "rb") as f:
                data = f.read()

            def _upload():
                get_supabase_client().storage.from_(self.ORIGINALS_BUCKET).upload(
                    file=data, path=path,
                    file_options={"content-type": "application/pdf", "upsert": "true"},
                )

            await async_db(_upload)
            stored = f"{self.ORIGINALS_BUCKET}/{path}"
            await async_db(lambda: self.client.table("documents").update({"file_url": stored})
                           .eq("id", document_id).execute())
            return stored
        except Exception as e:
            logger.warning(f"[{filename}] Original file not stored: {e}")
            return None

    async def _update_document_text_path(self, document_id: str, path: str):
        """Update text_storage_path in the documents record."""
        try:
            await async_db(
                lambda: self.client.table("documents")
                .update({"text_storage_path": path})
                .eq("id", document_id)
                .execute()
            )
        except Exception as e:
            logger.warning(f"Failed to update text_storage_path: {e}")

    async def _create_book_record(
        self,
        document_id: str,
        text_path: Optional[str],
        book_meta: Dict[str, Any],
    ):
        """
        Create a record in the books table for publicly shared books.
        Called after successful processing so failed uploads don't appear in the store.
        """
        try:
            book_data = {
                "user_id": book_meta.get("user_id"),
                "document_id": document_id,
                "title": book_meta.get("title"),
                "author": book_meta.get("author"),
                "description": book_meta.get("description"),
                "tags": book_meta.get("tags", []),
                "file_size": book_meta.get("file_size"),
                "file_type": book_meta.get("file_type"),
                "text_path": text_path,
                "is_public": True,
            }

            result = await async_db(
                lambda: self.client.table("books").insert(book_data).execute()
            )

            if result.data:
                logger.info(
                    f"Book record created (id={result.data[0]['id']}) "
                    f"for document {document_id}"
                )
        except Exception as e:
            logger.error(f"Failed to create book record for {document_id}: {e}")
            # Non-fatal — document is already processed successfully

    # ──────────────────────────────────────────────────────────────────────────
    # Embedding helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _cleanup_temp_file(self, file_path: str):
        """Remove temporary file after processing"""
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {e}")

    async def _process_embeddings_direct(
        self, chunks: List[str], document_id: str, filename: str, collection_name: str
    ):
        """
        Process embeddings using GLOBAL concurrency limits (shared across all docs).
        Emits SSE progress events after each batch for real-time frontend updates.
        """
        progress = get_progress_manager()

        batches = []
        for i in range(0, len(chunks), self.batch_size):
            batch_data = chunks[i: i + self.batch_size]
            batches.append((i, batch_data))

        total_batches = len(batches)

        embed_semaphore = EmbeddingQueue.get_embed_semaphore()
        db_semaphore = EmbeddingQueue.get_db_semaphore()

        logger.info(
            f"[{filename}] Starting embedding: {len(chunks)} chunks, "
            f"{total_batches} batches (global limits)"
        )

        completed = [0]
        failed_batches = []
        # A rejected key or bad config fails every batch: stop after the first
        fatal = []

        async def process_batch(batch_idx: int, start_index: int, batch_data: List[str]):
            retries = 6
            for attempt in range(retries):
                if fatal:
                    failed_batches.append(batch_idx)
                    return
                try:
                    async with embed_semaphore:
                        if fatal:  # another batch hit a fatal error while we waited
                            failed_batches.append(batch_idx)
                            return
                        batch_embeddings = await embedding_service.generate_embeddings(
                            batch_data
                        )

                    batch_metadata = [
                        {
                            "document_id": document_id,
                            "document_name": filename,
                            "chunk_id": start_index + k,
                        }
                        for k in range(len(batch_data))
                    ]

                    async with db_semaphore:
                        await qdrant_service.upsert_chunks(
                            collection_name=collection_name,
                            chunks=batch_data,
                            embeddings=batch_embeddings,
                            metadata=batch_metadata,
                        )

                    completed[0] += 1
                    pct = int((completed[0] / total_batches) * 100)

                    await progress.emit(
                        document_id, "embedding", pct,
                        f"Batch {completed[0]}/{total_batches}"
                    )

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
                            "429", "too many requests", "timeout",
                            "timed out", "connection", "temporary", "unavailable",
                        ]
                    )

                    if is_retryable and attempt < retries - 1:
                        # Much higher backoff for rate limiting: 1s, 4s, 16s, 64s, 256s
                        wait_time = (4 ** attempt) + (2.0 * (batch_idx % 5))
                        logger.warning(
                            f"[{filename}] Batch {batch_idx + 1} retry {attempt + 1}/{retries} "
                            f"in {wait_time:.1f}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    logger.error(f"[{filename}] Batch {batch_idx + 1} failed: {e}")
                    if any(x in error_str for x in ["401", "402", "403", "invalid api key", "api key not valid", "invalid_api_key", "404", "credits are depleted", "insufficient_quota"]):
                        fatal.append(e)
                    # Non-retryable, or out of retries: give up on this batch
                    failed_batches.append(batch_idx)
                    return  # Let other batches complete

        tasks = [
            process_batch(idx, start_idx, batch)
            for idx, (start_idx, batch) in enumerate(batches)
        ]
        await asyncio.gather(*tasks)

        if failed_batches:
            error_msg = f"Embedding completed with {len(failed_batches)} failed batches."
            logger.error(f"[{filename}] {error_msg}")
            raise Exception(error_msg)
        else:
            logger.info(f"[{filename}] Embedding completed: {total_batches} batches")

    # ──────────────────────────────────────────────────────────────────────────
    # Index self-healing
    # ──────────────────────────────────────────────────────────────────────────

    # Document IDs currently being re-indexed (prevents duplicate background jobs)
    _reindexing: set = set()
    # Strong refs to background tasks so they aren't garbage-collected mid-run
    _background_tasks: set = set()
    # document_id -> time of last failed re-index (avoid retrying on every request)
    _reindex_failed_at: dict = {}
    REINDEX_RETRY_SECONDS = 600

    async def load_stored_text(self, document: Dict[str, Any]) -> Optional[str]:
        """Download a document's extracted text from the texts/ bucket."""
        path = document.get("text_storage_path") or (
            f"{document['project_id']}/{document['id']}.txt"
            if document.get("project_id") else None
        )
        if not path:
            return None
        try:
            text_bytes = await async_db(
                lambda: self.client.storage.from_(
                    settings.BOOK_IMPORT_TEXTS_BUCKET
                ).download(path)
            )
            return text_bytes.decode("utf-8") if text_bytes else None
        except Exception as e:
            logger.warning(f"Could not load stored text for {document.get('id')}: {e}")
            return None

    async def ensure_project_indexed(self, project_id: str) -> List[str]:
        """
        Find "completed" documents that have no vectors in Qdrant (e.g. the
        collection was wiped or the vector DB was replaced) and re-embed them
        in the background from their stored text.

        Returns the IDs of documents being re-indexed.
        """
        collection_name = f"project_{project_id}"
        docs = await async_db(
            lambda: self.client.table("documents")
            .select("id, project_id, filename, text_storage_path")
            .eq("project_id", project_id)
            .eq("upload_status", "completed")
            .execute()
        )

        import time

        reindexing = []
        for doc in docs.data or []:
            if doc["id"] in self._reindexing:
                reindexing.append(doc["id"])
                continue
            failed_at = self._reindex_failed_at.get(doc["id"])
            if failed_at and time.time() - failed_at < self.REINDEX_RETRY_SECONDS:
                continue
            try:
                count = await qdrant_service.count_document_vectors(
                    collection_name, doc["id"]
                )
            except Exception as e:
                logger.warning(f"Vector count failed for {doc['id']}: {e}")
                continue
            if count > 0:
                continue

            logger.warning(
                f"[Reindex] Document {doc['filename']} ({doc['id']}) is marked "
                f"completed but has no vectors in {collection_name} — re-indexing"
            )
            self._reindexing.add(doc["id"])
            reindexing.append(doc["id"])
            task = asyncio.create_task(self._reindex_from_storage(doc))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        return reindexing

    async def _reindex_from_storage(self, document: Dict[str, Any]):
        """
        Re-chunk and re-embed a document from its stored text.

        Deliberately does NOT change upload_status: the document stays usable
        (search falls back to its stored text meanwhile), and environments that
        share one database but use separate vector stores (e.g. a test
        deployment) never flip production documents to processing/failed.
        """
        document_id = document["id"]
        project_id = document["project_id"]
        filename = document["filename"]
        progress = get_progress_manager()

        try:
            text = await self.load_stored_text(document)
            if not text:
                logger.error(
                    f"[Reindex] {filename} ({document_id}) has no vectors and no stored "
                    "text — it must be re-uploaded to be searchable here"
                )
                return

            async with EmbeddingQueue.get_doc_semaphore():
                loop = asyncio.get_running_loop()
                chunks = await loop.run_in_executor(
                    None, lambda: self.text_chunker.chunk_text(text)
                )
                if not chunks:
                    logger.error(f"[Reindex] No chunks generated for {filename}")
                    return

                collection_name = f"project_{project_id}"
                await qdrant_service.create_collection(collection_name)
                # Drop any partial vectors so we don't duplicate chunks
                await qdrant_service.delete_vectors(collection_name, document_id)
                await progress.emit(
                    document_id, "embedding", 0,
                    f"Re-indexing {len(chunks)} chunks..."
                )
                await self._process_embeddings_direct(
                    chunks, document_id, filename, collection_name
                )

            await progress.emit(document_id, "completed", 100, "Document re-indexed")
            logger.info(f"[Reindex] {filename} re-indexed ({len(chunks)} chunks)")
            self._reindex_failed_at.pop(document_id, None)

        except Exception as e:
            import time

            self._reindex_failed_at[document_id] = time.time()
            logger.error(
                f"[Reindex] Failed for {filename}: {e} — will retry after "
                f"{self.REINDEX_RETRY_SECONDS // 60} minutes"
            )
        finally:
            self._reindexing.discard(document_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Database helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _update_document_status(
        self, document_id: str, status: str, message: Optional[str] = None
    ):
        """Update document processing status in database (non-blocking)"""
        try:
            update_data = {"upload_status": status}
            if status == "completed":
                update_data["error_message"] = None
            elif message:
                update_data["error_message"] = message

            await async_db(
                lambda: self.client.table("documents")
                .update(update_data)
                .eq("id", document_id)
                .execute()
            )

        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")

    async def delete_document(self, project_id: str, document_id: str):
        """Delete document from DB, Vector Store, and Storage (non-blocking)"""
        try:
            collection_name = f"project_{project_id}"
            await qdrant_service.delete_vectors(collection_name, document_id)

            # Delete extracted text from texts/ bucket, unless class copies of
            # this book (other documents) still read it
            try:
                text_storage_path = f"{project_id}/{document_id}.txt"
                still_used = await async_db(
                    lambda: self.client.table("documents").select("id")
                    .eq("text_storage_path", text_storage_path).neq("id", document_id)
                    .limit(1).execute()
                )
                if still_used.data:
                    raise RuntimeError("text still used by class copies; kept")

                def _delete_text():
                    self.client.storage.from_(
                        settings.BOOK_IMPORT_TEXTS_BUCKET
                    ).remove([text_storage_path])

                await async_db(_delete_text)
                logger.info(f"Deleted text file texts/{text_storage_path}")
            except Exception as storage_err:
                logger.warning(f"Failed to delete text from storage: {storage_err}")

            await async_db(
                lambda: self.client.table("documents")
                .delete()
                .eq("id", document_id)
                .execute()
            )
            logger.info(f"Deleted document {document_id} from project {project_id}")
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise

    async def process_chunks_direct(
        self, document_id: str, project_id: str, filename: str, chunks: List[str]
    ):
        """
        Process chunks received directly from PDF service (legacy webhook support).
        Kept for backward compatibility.
        """
        queue = get_embedding_queue()

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

        async def process_job(job: EmbeddingJob):
            """Called by queue for processing"""
            try:
                await self._update_document_status(
                    document_id, "embedding", "Generating embeddings..."
                )

                logger.info(f"Processing {len(chunks)} chunks for document {filename}")

                collection_name = f"project_{project_id}"
                await qdrant_service.create_collection(collection_name)
                await self._process_embeddings_direct(
                    chunks, document_id, filename, collection_name
                )

                await self._update_document_status(
                    document_id, "embedding", "Generating topics..."
                )
                try:
                    from services.mcq_service import mcq_service
                    await mcq_service.generate_document_topics(project_id, document_id)
                    logger.info(f"Topics generated for {filename}")
                except Exception as topic_err:
                    logger.error(f"Failed to generate topics: {topic_err}")

                try:
                    from services.knowledge_graph_service import knowledge_graph
                    docs = await async_db(
                        lambda: get_supabase_client()
                        .table("documents")
                        .select("topics")
                        .eq("project_id", project_id)
                        .eq("upload_status", "completed")
                        .execute()
                    )
                    all_topics = []
                    for d in docs.data or []:
                        all_topics.extend(d.get("topics") or [])
                    current_doc = await async_db(
                        lambda: get_supabase_client()
                        .table("documents")
                        .select("topics")
                        .eq("id", document_id)
                        .execute()
                    )
                    if current_doc.data:
                        all_topics.extend(current_doc.data[0].get("topics") or [])
                    all_topics = list(set(all_topics))
                    if len(all_topics) >= 2:
                        await knowledge_graph.build_graph_from_topics(
                            project_id, all_topics, force_rebuild=True
                        )
                except Exception as kg_err:
                    logger.error(f"Failed to build knowledge graph: {kg_err}")

                await self._update_document_status(document_id, "completed")
                logger.info(f"Document {filename} embeddings completed successfully")

            except Exception as e:
                logger.error(f"Error processing chunks for {filename}: {str(e)}")
                await self._update_document_status(document_id, "failed", str(e))
                raise

        await queue.enqueue(
            document_id=document_id,
            project_id=project_id,
            filename=filename,
            chunks=chunks,
            process_callback=process_job,
        )


document_service = DocumentService()
