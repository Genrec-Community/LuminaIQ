import os
import time
import asyncio
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from db.client import get_supabase_client, async_db
from config.settings import settings
from utils.file_parser import FileParser
from services.embedding_service import embedding_service
from utils.logger import logger
from utils.concurrency import doc_semaphore, llm_semaphore
from services import vector_store
from services.indexing import index_chunks, make_chunks
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
            doc_semaphore_ = doc_semaphore()

            # Notify frontend if doc is queued (semaphore full)
            if doc_semaphore_.locked():
                await progress.emit(
                    document_id, "queued", 0,
                    "Waiting for other documents to finish..."
                )
                await self._update_document_status(
                    document_id, "queued", "Waiting for processing slot..."
                )
                logger.info(f"[{filename}] Queued — waiting for doc_semaphore slot")

            async with doc_semaphore_:
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
            last_beat = [0.0]

            def on_ocr_page(done: int, total: int):
                # Called from the extraction thread while a scanned PDF is OCR'd
                asyncio.run_coroutine_threadsafe(
                    progress.emit(document_id, "extracting", int(done * 100 / max(total, 1)),
                                  f"Scanning page {done}/{total}"),
                    loop,
                )
                # Heartbeat (bumps updated_at) so the app can tell slow from stopped
                if time.monotonic() - last_beat[0] >= 30 or done == total:
                    last_beat[0] = time.monotonic()
                    asyncio.run_coroutine_threadsafe(
                        self._update_document_status(document_id, "processing", f"Scanning page {done}/{total}"),
                        loop,
                    )

            text = await loop.run_in_executor(
                self._extraction_executor, self.file_parser.extract_text, file_path, on_ocr_page
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
                make_chunks(text, filename),
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
            llm_sem = llm_semaphore()

            async def embed():
                try:
                    async def report(pct, msg):
                        await progress.emit(document_id, "embedding", pct, msg)
                        # Heartbeat (bumps updated_at) so the app can tell slow from stopped
                        await self._update_document_status(document_id, "processing", msg)
                    await index_chunks(project_id, document_id, chunks, report)
                    return None
                except Exception as embed_err:
                    return embed_err

            async def topics():
                try:
                    from services.mcq_service import mcq_service

                    async with llm_sem:
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
                    await vector_store.delete_document(document_id)
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

    # ──────────────────────────────────────────────────────────────────────────
    # Index self-healing
    # ──────────────────────────────────────────────────────────────────────────

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
        Find "completed" documents that have no passages (e.g. embedding failed
        during upload) and queue a re-index from their stored text.

        Returns the IDs of documents being re-indexed.
        """
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
            failed_at = self._reindex_failed_at.get(doc["id"])
            if failed_at and time.time() - failed_at < self.REINDEX_RETRY_SECONDS:
                continue
            try:
                count = await vector_store.count(doc["id"])
            except Exception as e:
                logger.warning(f"Vector count failed for {doc['id']}: {e}")
                continue
            if count > 0:
                continue

            logger.warning(
                f"[Reindex] Document {doc['filename']} ({doc['id']}) is marked "
                f"completed but has no passages — re-indexing"
            )
            reindexing.append(doc["id"])
            try:
                from services.jobs import enqueue
                await enqueue("reindex_document", {"document": doc},
                              dedupe_key=f"reindex_document:{doc['id']}")
            except Exception as e:
                logger.warning(f"[Reindex] could not queue {doc['id']}: {e}")

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

            async with doc_semaphore():
                chunks = await make_chunks(text, filename)
                if not chunks:
                    logger.error(f"[Reindex] No chunks generated for {filename}")
                    return
                await progress.emit(document_id, "embedding", 0, f"Re-indexing {len(chunks)} passages...")
                await index_chunks(project_id, document_id, chunks)

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
            await vector_store.delete_document(document_id)

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

    async def process_chunks_direct(self, document_id: str, project_id: str, filename: str, chunks: List[str]):
        """Legacy webhook (an external parser sent pre-split chunks): index their text."""
        try:
            await index_chunks(project_id, document_id, await make_chunks("\n\n".join(chunks), filename))
            await self._update_document_status(document_id, "completed")
        except Exception as e:
            logger.error(f"[Webhook] indexing failed for {filename}: {e}")
            await self._update_document_status(document_id, "failed", str(e))


document_service = DocumentService()
