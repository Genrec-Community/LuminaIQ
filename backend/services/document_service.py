import os
import asyncio
import json
from typing import Optional, List
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
from utils.performance import PerformanceTracker
from core.redis_manager import get_redis_manager


class DocumentService:
    """
    Unified document processing service.

    Handles the complete pipeline: extract → chunk → embed → topics → knowledge graph.
    Emits real-time SSE progress events throughout processing.

    Features:
    - Direct file processing (no external pdfprocess service)
    - Parallel batch embedding with global concurrency control
    - Real-time SSE progress for frontend
    - Automatic temp file cleanup
    - Retry with exponential backoff for transient failures
    - Document metadata caching with 6-hour TTL
    """

    def __init__(self):
        self.client = get_supabase_client()
        self.file_parser = FileParser()
        self.text_chunker = TextChunker(
            chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP
        )
        self.batch_size = getattr(settings, "EMBEDDING_BATCH_SIZE", 100)
        # Dedicated thread pool for CPU-heavy file extraction
        # Prevents extraction from competing with embedding API calls for threads
        self._extraction_executor = ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="file_extract"
        )
        
        # Initialize Redis cache manager for document metadata caching
        try:
            self.redis_manager = get_redis_manager()
            self.cache_enabled = True
            logger.info("Document metadata caching enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis for document caching: {e}")
            self.redis_manager = None
            self.cache_enabled = False

    async def process_document(
        self, document_id: str, project_id: str, file_path: str, filename: str
    ):
        """
        Process uploaded document: extract text, chunk, embed, generate topics, build graph.

        Emits SSE progress events at each stage for real-time frontend updates.
        """
        progress = get_progress_manager()

        try:
            # Gate with doc_semaphore: max 3 docs process the heavy pipeline concurrently.
            # Additional uploads wait here until a slot opens.
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
                    document_id, project_id, file_path, filename, progress
                )

        except Exception as e:
            logger.error(f"Error processing document {filename}: {str(e)}")
            await self._update_document_status(document_id, "failed", str(e))
            await progress.emit(document_id, "failed", 0, str(e))

        finally:
            # Always clean up temp file
            self._cleanup_temp_file(file_path)

    async def _run_pipeline(
        self, document_id: str, project_id: str, file_path: str,
        filename: str, progress
    ):
        """
        The actual processing pipeline, called inside doc_semaphore.
        Separated so the semaphore scope is clear.
        """
        perf = PerformanceTracker()
        perf.start("total_pipeline")
        try:
            # Update status to processing
            await self._update_document_status(document_id, "processing")
            await progress.emit(document_id, "extracting", 0, "Extracting text...")

            loop = asyncio.get_running_loop()

            # 1. Extract text (dedicated thread pool to avoid starving other executors)
            logger.info(f"Extracting text from {filename}")
            await self._update_document_status(
                document_id, "processing", "Extracting text..."
            )
            perf.start("pdf_parsing")
            text = await loop.run_in_executor(
                self._extraction_executor, self.file_parser.extract_text, file_path
            )
            perf.stop("pdf_parsing")

            if not text:
                raise ValueError("PDF extraction failed: no usable text could be extracted from the document.")

            await progress.emit(
                document_id, "extracting", 100,
                f"Extracted {len(text)} characters"
            )

            # 2. Chunk text (Run in thread pool to avoid blocking)
            logger.info(f"Chunking text from {filename}")
            await self._update_document_status(
                document_id, "processing", "Chunking text..."
            )
            await progress.emit(document_id, "chunking", 0, "Splitting into chunks...")

            perf.start("text_chunking")
            chunks = await loop.run_in_executor(
                None, lambda: self.text_chunker.chunk_text(text)
            )
            perf.stop("text_chunking")

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

            # 3. Create Qdrant collection
            collection_name = f"project_{project_id}"
            await qdrant_service.create_collection(collection_name)

            # 4. Process embeddings with global limits + progress
            await progress.emit(
                document_id, "embedding", 0,
                f"Embedding {len(chunks)} chunks..."
            )
            perf.start("embedding")
            await self._process_embeddings_direct(
                chunks, document_id, filename, collection_name
            )
            perf.stop("embedding")

            # 5. Generate Topics (LLM-gated: max 2 concurrent LLM calls)
            await self._update_document_status(
                document_id, "processing", "Generating topics..."
            )
            await progress.emit(
                document_id, "topics", 0, "Generating document topics..."
            )
            llm_semaphore = EmbeddingQueue.get_llm_semaphore()
            try:
                from services.mcq_service import mcq_service

                perf.start("topic_generation")
                async with llm_semaphore:
                    await mcq_service.generate_document_topics(project_id, document_id)
                perf.stop("topic_generation")
                logger.info(f"Topics generated for {filename}")
                await progress.emit(
                    document_id, "topics", 100, "Topics generated"
                )
            except Exception as topic_err:
                logger.error(f"Failed to generate topics for {filename}: {topic_err}")
                await progress.emit(
                    document_id, "topics", 100, "Topic generation skipped"
                )

            # 6. Auto-build knowledge graph from all project topics
            await progress.emit(
                document_id, "graph", 0, "Building knowledge graph..."
            )
            try:
                from services.knowledge_graph_service import knowledge_graph

                docs = await async_db(
                    lambda: self.client
                    .table("documents")
                    .select("topics")
                    .eq("project_id", project_id)
                    .eq("upload_status", "completed")
                    .execute()
                )
                all_topics = []
                for d in docs.data or []:
                    all_topics.extend(d.get("topics") or [])

                # Also include topics from the current doc (not yet marked completed)
                current_doc = await async_db(
                    lambda: self.client
                    .table("documents")
                    .select("topics")
                    .eq("id", document_id)
                    .execute()
                )
                if current_doc.data:
                    all_topics.extend(current_doc.data[0].get("topics") or [])

                all_topics = list(set(all_topics))
                if len(all_topics) >= 2:
                    logger.info(
                        f"Auto-building knowledge graph with {len(all_topics)} topics"
                    )
                    perf.start("knowledge_graph")
                    async with llm_semaphore:
                        await knowledge_graph.build_graph_from_topics(
                            project_id, all_topics, force_rebuild=True
                        )
                    perf.stop("knowledge_graph")
                    logger.info(f"Knowledge graph built for {filename}")
                await progress.emit(
                    document_id, "graph", 100, "Knowledge graph updated"
                )
            except Exception as kg_err:
                logger.error(f"Failed to build knowledge graph: {kg_err}")
                await progress.emit(
                    document_id, "graph", 100, "Knowledge graph skipped"
                )

            # 7. Update status to completed
            await self._update_document_status(document_id, "completed")
            await progress.emit(
                document_id, "completed", 100, "Document processed successfully"
            )
            logger.info(f"Document {filename} processed successfully")
            
            perf.stop("total_pipeline")
            perf.log_total(logger)

        except Exception as e:
            logger.error(f"Error in pipeline for {filename}: {str(e)}")
            await self._update_document_status(document_id, "failed", str(e))
            await progress.emit(document_id, "failed", 0, str(e))

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
        Process embeddings using GLOBAL concurrency limits.

        Emits SSE progress events after each batch for real-time frontend updates.
        """
        progress = get_progress_manager()

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
                    pct = int((completed[0] / total_batches) * 100)

                    # Emit SSE progress every batch
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
            
            # Invalidate document cache when status changes
            await self._invalidate_document_cache(document_id)
            
            # Invalidate vector search cache when document is completed
            # New documents change the vector search results
            if status == "completed" and self.cache_enabled:
                try:
                    doc_metadata = await self.get_document_metadata(document_id)
                    if doc_metadata:
                        project_id = doc_metadata.get("project_id")
                        if project_id:
                            from core.vector_cache import VectorSearchCache
                            vector_cache = VectorSearchCache(self.redis_manager)
                            await vector_cache.invalidate_project(project_id)
                            logger.info(
                                f"Invalidated vector search cache for project {project_id} "
                                f"after document {document_id} completed"
                            )
                            
                            # Invalidate query result caches (Requirement 16.3)
                            await self._invalidate_query_result_caches(project_id)
                except Exception as cache_err:
                    logger.warning(f"Failed to invalidate vector search cache on document completion: {cache_err}")
            
            # Invalidate semantic query cache when document is completed
            # New documents change the knowledge base, so cached RAG answers may be stale
            if status == "completed" and self.cache_enabled:
                try:
                    # Get project_id for this document
                    doc_metadata = await self.get_document_metadata(document_id)
                    if doc_metadata:
                        project_id = doc_metadata.get("project_id")
                        if project_id:
                            from core.semantic_cache import SemanticCacheService
                            semantic_cache = SemanticCacheService(self.redis_manager)
                            await semantic_cache.invalidate_project_cache(project_id)
                            logger.info(
                                f"Invalidated semantic cache for project {project_id} "
                                f"after document {document_id} completed"
                            )
                except Exception as cache_err:
                    logger.warning(f"Failed to invalidate semantic cache on document completion: {cache_err}")

        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")

    async def delete_document(self, project_id: str, document_id: str):
        """Delete document from DB, Vector Store, and Storage (non-blocking)"""
        try:
            collection_name = f"project_{project_id}"
            await qdrant_service.delete_vectors(collection_name, document_id)
            
            # Delete from Supabase Storage
            try:
                doc_record = await async_db(
                    lambda: self.client.table("documents")
                    .select("filename")
                    .eq("id", document_id)
                    .execute()
                )
                if doc_record.data and len(doc_record.data) > 0:
                    filename = doc_record.data[0].get("filename")
                    if filename:
                        storage_path = f"{project_id}/{document_id}_{filename}"
                        
                        def _delete_storage():
                            self.client.storage.from_("documents").remove([storage_path])
                            
                        await async_db(_delete_storage)
                        logger.info(f"Deleted {storage_path} from storage")
            except Exception as storage_err:
                logger.error(f"Failed to delete document from storage: {storage_err}")

            await async_db(
                lambda: self.client.table("documents")
                .delete()
                .eq("id", document_id)
                .execute()
            )
            
            # Invalidate document metadata cache
            await self._invalidate_document_cache(document_id)
            await self._invalidate_project_documents_cache(project_id)
            
            # Invalidate vector search cache for project
            # Deleted documents change vector search results
            if self.cache_enabled:
                try:
                    from core.vector_cache import VectorSearchCache
                    vector_cache = VectorSearchCache(self.redis_manager)
                    await vector_cache.invalidate_project(project_id)
                    logger.info(
                        f"Invalidated vector search cache for project {project_id} "
                        f"after document {document_id} deleted"
                    )
                    
                    # Invalidate query result caches (Requirement 16.3)
                    await self._invalidate_query_result_caches(project_id)
                except Exception as cache_err:
                    logger.warning(f"Failed to invalidate vector search cache on document deletion: {cache_err}")
            
            # Invalidate semantic query cache for project
            try:
                from core.semantic_cache import SemanticCacheService
                semantic_cache = SemanticCacheService(self.redis_manager)
                await semantic_cache.invalidate_project_cache(project_id)
            except Exception as cache_err:
                logger.warning(f"Failed to invalidate semantic cache: {cache_err}")
            
            logger.info(f"Deleted document {document_id} from project {project_id}")
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            raise
    
    async def get_document_metadata(self, document_id: str) -> Optional[dict]:
        """
        Get document metadata with caching.
        
        Checks Redis cache first, falls back to database if not found.
        Caches result with 6-hour TTL.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Document metadata dict or None if not found
        """
        # Try cache first
        if self.cache_enabled:
            cache_key = f"doc:{document_id}"
            cached_data = await self.redis_manager.get(cache_key)
            
            if cached_data:
                try:
                    metadata = json.loads(cached_data)
                    logger.debug(f"Document metadata cache HIT for {document_id}")
                    return metadata
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode cached document metadata for {document_id}")
        
        # Cache miss - query database
        try:
            result = await async_db(
                lambda: self.client.table("documents")
                .select("id, filename, project_id, topics, upload_status, created_at")
                .eq("id", document_id)
                .execute()
            )
            
            if not result.data:
                return None
            
            metadata = result.data[0]
            
            # Cache the result
            if self.cache_enabled:
                cache_key = f"doc:{document_id}"
                await self.redis_manager.set(
                    cache_key,
                    json.dumps(metadata),
                    ttl=21600  # 6 hours
                )
                logger.debug(f"Cached document metadata for {document_id}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error fetching document metadata: {e}")
            return None
    
    async def get_documents_metadata_batch(self, document_ids: List[str]) -> dict:
        """
        Get metadata for multiple documents in a single operation.
        
        Uses batch cache retrieval for efficiency.
        
        Args:
            document_ids: List of document identifiers
            
        Returns:
            Dictionary mapping document_id to metadata
        """
        if not document_ids:
            return {}
        
        result = {}
        uncached_ids = []
        
        # Try to get from cache first
        if self.cache_enabled:
            cache_keys = [f"doc:{doc_id}" for doc_id in document_ids]
            cached_data = await self.redis_manager.get_many(cache_keys)
            
            for doc_id, cache_key in zip(document_ids, cache_keys):
                if cache_key in cached_data:
                    try:
                        metadata = json.loads(cached_data[cache_key])
                        result[doc_id] = metadata
                    except json.JSONDecodeError:
                        uncached_ids.append(doc_id)
                else:
                    uncached_ids.append(doc_id)
            
            logger.debug(
                f"Document metadata batch: {len(result)}/{len(document_ids)} from cache, "
                f"{len(uncached_ids)} from database"
            )
        else:
            uncached_ids = document_ids
        
        # Fetch uncached documents from database
        if uncached_ids:
            try:
                db_result = await async_db(
                    lambda: self.client.table("documents")
                    .select("id, filename, project_id, topics, upload_status, created_at")
                    .in_("id", uncached_ids)
                    .execute()
                )
                
                # Cache the results
                if self.cache_enabled and db_result.data:
                    cache_items = {}
                    for doc in db_result.data:
                        doc_id = doc["id"]
                        result[doc_id] = doc
                        cache_key = f"doc:{doc_id}"
                        cache_items[cache_key] = json.dumps(doc)
                    
                    await self.redis_manager.set_many(cache_items, ttl=21600)  # 6 hours
                else:
                    for doc in db_result.data:
                        result[doc["id"]] = doc
                        
            except Exception as e:
                logger.error(f"Error fetching documents metadata batch: {e}")
        
        return result
    
    async def get_project_documents(self, project_id: str) -> List[dict]:
        """
        Get all documents for a project with caching.
        
        Args:
            project_id: Project identifier
            
        Returns:
            List of document metadata dicts
        """
        # Try cache first
        if self.cache_enabled:
            cache_key = f"docs:{project_id}"
            cached_data = await self.redis_manager.get(cache_key)
            
            if cached_data:
                try:
                    documents = json.loads(cached_data)
                    logger.debug(f"Project documents cache HIT for {project_id}")
                    return documents
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode cached project documents for {project_id}")
        
        # Cache miss - query database
        try:
            result = await async_db(
                lambda: self.client.table("documents")
                .select("id, filename, project_id, topics, upload_status, created_at")
                .eq("project_id", project_id)
                .execute()
            )
            
            documents = result.data or []
            
            # Cache the result
            if self.cache_enabled:
                cache_key = f"docs:{project_id}"
                await self.redis_manager.set(
                    cache_key,
                    json.dumps(documents),
                    ttl=21600  # 6 hours
                )
                logger.debug(f"Cached project documents for {project_id}")
            
            return documents
            
        except Exception as e:
            logger.error(f"Error fetching project documents: {e}")
            return []
    
    async def _invalidate_document_cache(self, document_id: str) -> None:
        """
        Invalidate cache for a specific document.
        
        Args:
            document_id: Document identifier
        """
        if self.cache_enabled:
            cache_key = f"doc:{document_id}"
            await self.redis_manager.delete(cache_key)
            logger.debug(f"Invalidated document cache for {document_id}")
    
    async def _invalidate_project_documents_cache(self, project_id: str) -> None:
        """
        Invalidate cache for project documents list.
        
        Args:
            project_id: Project identifier
        """
        if self.cache_enabled:
            cache_key = f"docs:{project_id}"
            await self.redis_manager.delete(cache_key)
            logger.debug(f"Invalidated project documents cache for {project_id}")
    
    async def _invalidate_query_result_caches(self, project_id: str) -> None:
        """
        Invalidate query result caches for a project.
        
        This invalidates caches for endpoints like:
        - GET /api/v1/documents/{project_id}
        - GET /api/v1/mcq/topics/{project_id}
        
        Args:
            project_id: Project identifier
        """
        if self.cache_enabled:
            # Invalidate documents list cache (Requirement 16.3)
            documents_cache_key = f"query:documents:{project_id}"
            await self.redis_manager.delete(documents_cache_key)
            
            # Invalidate topics list cache (Requirement 16.3)
            topics_cache_key = f"query:topics:{project_id}"
            await self.redis_manager.delete(topics_cache_key)
            
            logger.debug(f"Invalidated query result caches for project {project_id}")
    
    async def warm_cache_for_projects(self, project_ids: List[str]) -> None:
        """
        Preload document metadata for multiple projects into cache.
        
        This is called on application startup to warm the cache.
        
        Args:
            project_ids: List of project identifiers to warm cache for
        """
        if not self.cache_enabled:
            logger.info("Cache warming skipped - caching disabled")
            return
        
        logger.info(f"Warming document metadata cache for {len(project_ids)} projects")
        
        for project_id in project_ids:
            try:
                # Fetch and cache project documents
                documents = await self.get_project_documents(project_id)
                
                # Also cache individual document metadata
                if documents:
                    cache_items = {}
                    for doc in documents:
                        cache_key = f"doc:{doc['id']}"
                        cache_items[cache_key] = json.dumps(doc)
                    
                    await self.redis_manager.set_many(cache_items, ttl=21600)
                
                logger.debug(f"Warmed cache for project {project_id}: {len(documents)} documents")
                
            except Exception as e:
                logger.error(f"Error warming cache for project {project_id}: {e}")
        
        logger.info("Document metadata cache warming completed")

    async def process_chunks_direct(
        self, document_id: str, project_id: str, filename: str, chunks: List[str]
    ):
        """
        Process chunks received directly from PDF service (legacy webhook support).

        Kept for backward compatibility with existing pdfprocess deployments.
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

                # Process embeddings
                await self._process_embeddings_direct(
                    chunks, document_id, filename, collection_name
                )

                # Generate Topics
                await self._update_document_status(
                    document_id, "embedding", "Generating topics..."
                )
                try:
                    from services.mcq_service import mcq_service

                    await mcq_service.generate_document_topics(project_id, document_id)
                    logger.info(f"Topics generated for {filename}")
                except Exception as topic_err:
                    logger.error(
                        f"Failed to generate topics for {filename}: {topic_err}"
                    )

                # Auto-build knowledge graph
                try:
                    from services.knowledge_graph_service import knowledge_graph

                    docs = await async_db(
                        lambda: self.client
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
                        lambda: self.client
                        .table("documents")
                        .select("topics")
                        .eq("id", document_id)
                        .execute()
                    )
                    if current_doc.data:
                        all_topics.extend(current_doc.data[0].get("topics") or [])

                    all_topics = list(set(all_topics))
                    if len(all_topics) >= 2:
                        logger.info(
                            f"Auto-building knowledge graph with {len(all_topics)} topics"
                        )
                        await knowledge_graph.build_graph_from_topics(
                            project_id, all_topics, force_rebuild=True
                        )
                        logger.info(f"Knowledge graph built for {filename}")
                except Exception as kg_err:
                    logger.error(f"Failed to build knowledge graph: {kg_err}")

                # Update status to completed
                await self._update_document_status(document_id, "completed")
                logger.info(
                    f"Document {filename} embeddings completed successfully"
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


document_service = DocumentService()
