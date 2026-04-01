"""
Book Store Service

Handles all operations for the Book Store:
- Listing public books (with search + tag filtering)
- Reading a user's own books
- Importing a public book into a project
- Updating book metadata / visibility
- Deleting a book (owner only)

## Book Import Strategy (Fast Path)

When a user imports from the store, the book is already embedded in Qdrant
under the original uploader's project collection. We clone those vectors
directly into the importer's project collection and copy the topics from
the source document — no re-embedding, no LLM calls.

Import time: ~2-5 seconds instead of 2-5 minutes.

Fallback: If source vectors are not found (edge case — source doc deleted),
we fall back to the old re-embedding pipeline so imports never silently fail.
"""

import asyncio
from typing import Optional, List, Dict, Any
from db.client import get_supabase_client, async_db
from config.settings import settings
from utils.logger import logger
from utils.embedding_queue import EmbeddingQueue


class BookService:

    def __init__(self):
        self.client = get_supabase_client()

    # ──────────────────────────────────────────────────────────────────────────
    # READ
    # ──────────────────────────────────────────────────────────────────────────

    async def get_public_books(
        self,
        page: int = 1,
        page_size: int = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Return paginated list of public books for the Book Store.
        Supports full-text search on title/author/description and tag filtering.
        """
        page_size = page_size or settings.BOOK_STORE_PAGE_SIZE
        offset = (page - 1) * page_size

        def _query():
            supabase = get_supabase_client()
            q = (
                supabase.table("books")
                .select(
                    "id, title, author, description, cover_url, file_size, file_type, "
                    "tags, import_count, created_at, user_id",
                    count="exact",
                )
                .eq("is_public", True)
                .order("import_count", desc=True)
                .order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
            )

            if search:
                q = q.or_(
                    f"title.ilike.%{search}%,"
                    f"author.ilike.%{search}%,"
                    f"description.ilike.%{search}%"
                )

            if tags:
                q = q.contains("tags", tags)

            return q.execute()

        try:
            result = await async_db(_query)
            total = result.count or 0
            return {
                "books": result.data or [],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": max(1, (total + page_size - 1) // page_size),
            }
        except Exception as e:
            logger.error(f"Failed to fetch public books: {e}")
            raise

    async def get_user_books(self, user_id: str) -> List[Dict]:
        """Return all books (public + private) belonging to the current user."""
        def _query():
            return (
                get_supabase_client()
                .table("books")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )

        try:
            result = await async_db(_query)
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch user books: {e}")
            raise

    async def get_book(self, book_id: str, user_id: str) -> Optional[Dict]:
        """
        Return a single book.
        Returns None if book doesn't exist or user doesn't have read access.
        """
        def _query():
            return (
                get_supabase_client()
                .table("books")
                .select("*")
                .eq("id", book_id)
                .execute()
            )

        try:
            result = await async_db(_query)
            if not result.data:
                return None
            book = result.data[0]
            if not book["is_public"] and book["user_id"] != user_id:
                return None
            return book
        except Exception as e:
            logger.error(f"Failed to fetch book {book_id}: {e}")
            raise

    async def check_import_status(
        self, book_id: str, project_id: str, user_id: str
    ) -> Optional[Dict]:
        """
        Check if a book has already been imported into a project AND that the
        resulting document still exists.

        If the user deleted the document after importing, the book_imports row
        becomes stale. We clean it up so the user can re-import freely.
        """
        def _query():
            return (
                get_supabase_client()
                .table("book_imports")
                .select("*")
                .eq("book_id", book_id)
                .eq("project_id", project_id)
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )

        try:
            result = await async_db(_query)
            import_record = result.data if result else None

            if not import_record:
                return None

            # Verify the linked document still exists
            document_id = import_record.get("document_id")
            if document_id:
                def _check_doc():
                    return (
                        get_supabase_client()
                        .table("documents")
                        .select("id")
                        .eq("id", document_id)
                        .maybe_single()
                        .execute()
                    )

                doc_result = await async_db(_check_doc)
                if not doc_result or not doc_result.data:
                    # Document was deleted — clean up the stale import record
                    logger.info(
                        f"[BookImport] Stale import record found for book {book_id} "
                        f"(document {document_id} no longer exists). Cleaning up."
                    )
                    def _delete_stale():
                        return (
                            get_supabase_client()
                            .table("book_imports")
                            .delete()
                            .eq("book_id", book_id)
                            .eq("project_id", project_id)
                            .eq("user_id", user_id)
                            .execute()
                        )
                    await async_db(_delete_stale)
                    return None  # Allow re-import

            return import_record

        except Exception as e:
            logger.error(f"Failed to check import status: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # WRITE — Import (fast vector-clone path)
    # ──────────────────────────────────────────────────────────────────────────

    async def import_book(
        self, book_id: str, project_id: str, user_id: str
    ) -> Dict[str, Any]:
        """
        Import a public book into a user's project.

        The HTTP response returns in ~1 second — only lightweight DB work
        is done synchronously:
          1. Validate book + duplicate check
          2. Create document record (status: pending)
          3. Record import + increment counter
          4. Return the document to the frontend immediately

        All heavy I/O (text copy, vector clone, topic copy) is fired into a
        background task so the "Added!" tick appears instantly in the UI.
        """
        # ── Synchronous: validate ──────────────────────────────────────────
        book = await self.get_book(book_id, user_id)
        if not book:
            raise ValueError("Book not found or not accessible")
        if not book["is_public"]:
            raise PermissionError("This book is not publicly available")

        existing = await self.check_import_status(book_id, project_id, user_id)
        if existing:
            raise ValueError("This book has already been imported into this project")

        source_text_path = book.get("text_path")
        if not source_text_path:
            raise ValueError(
                "This book's text content is not available for import. "
                "Please ask the owner to re-process it."
            )

        # ── Synchronous: create document record ────────────────────────────
        doc_data = {
            "project_id": project_id,
            "filename": f"{book['title']}.txt",
            "file_type": "text/plain",
            "file_size": 0,  # will be updated by background task
            "upload_status": "pending",
            "user_id": user_id,
        }

        def _insert_doc():
            return (
                get_supabase_client()
                .table("documents")
                .insert(doc_data)
                .execute()
            )

        doc_result = await async_db(_insert_doc)
        if not doc_result.data:
            raise RuntimeError("Failed to create document record for imported book")

        document = doc_result.data[0]
        document_id = document["id"]

        # ── Synchronous: record the import + increment counter ─────────────
        def _record_import():
            return (
                get_supabase_client()
                .table("book_imports")
                .insert({
                    "book_id": book_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "document_id": document_id,
                })
                .execute()
            )

        await async_db(_record_import)

        try:
            def _increment():
                return (
                    get_supabase_client()
                    .rpc("increment_book_import_count", {"book_id_input": book_id})
                    .execute()
                )
            await async_db(_increment)
        except Exception:
            try:
                def _increment_fallback():
                    supabase = get_supabase_client()
                    current = (
                        supabase.table("books")
                        .select("import_count")
                        .eq("id", book_id)
                        .single()
                        .execute()
                    )
                    count = (current.data or {}).get("import_count", 0) + 1
                    return (
                        supabase.table("books")
                        .update({"import_count": count})
                        .eq("id", book_id)
                        .execute()
                    )
                await async_db(_increment_fallback)
            except Exception as e:
                logger.warning(f"Failed to increment import_count: {e}")

        logger.info(
            f"[BookImport] '{book['title']}' registered for project {project_id} "
            f"as document {document_id}  — background clone starting"
        )

        # ── Background: text copy + vector clone + topics ──────────────────
        asyncio.create_task(
            self._background_clone(
                book=book,
                document_id=document_id,
                project_id=project_id,
                doc_filename=doc_data["filename"],
                source_text_path=source_text_path,
            )
        )

        return document

    # ──────────────────────────────────────────────────────────────────────────
    # Background clone — runs after the HTTP response is already sent
    # ──────────────────────────────────────────────────────────────────────────

    async def _background_clone(
        self,
        book: Dict,
        document_id: str,
        project_id: str,
        doc_filename: str,
        source_text_path: str,
    ):
        """
        Runs in asyncio.create_task after the import endpoint has already
        returned 200 to the frontend.

        Steps:
          1. Download source text from storage
          2. Copy text to target project path
          3. Resolve source document_id / project_id
          4. Clone Qdrant vectors (fast path)
          5. Copy topics + mark completed

        If vector clone fails or finds 0 vectors → falls back to full
        re-embedding pipeline (which also runs in background).
        """
        try:
            # 1. Download source text
            def _read_text():
                return get_supabase_client().storage.from_(
                    settings.BOOK_IMPORT_TEXTS_BUCKET
                ).download(source_text_path)

            text_bytes = await async_db(_read_text)
            text_content = text_bytes.decode("utf-8")

            # Update file_size now that we have the bytes
            def _update_size():
                return (
                    get_supabase_client()
                    .table("documents")
                    .update({"file_size": len(text_bytes)})
                    .eq("id", document_id)
                    .execute()
                )
            await async_db(_update_size)

            # 2. Copy text to target project path
            target_text_path = f"{project_id}/{document_id}.txt"
            try:
                def _upload_text():
                    get_supabase_client().storage.from_(
                        settings.BOOK_IMPORT_TEXTS_BUCKET
                    ).upload(
                        file=text_bytes,
                        path=target_text_path,
                        file_options={"content-type": "text/plain"},
                    )
                await async_db(_upload_text)

                def _update_path():
                    return (
                        get_supabase_client()
                        .table("documents")
                        .update({"text_storage_path": target_text_path})
                        .eq("id", document_id)
                        .execute()
                    )
                await async_db(_update_path)
            except Exception as e:
                logger.warning(f"[BackgroundClone] Text copy failed: {e}")

            # 3. Resolve source document_id and source project_id
            source_document_id = book.get("document_id")
            source_project_id = None

            if source_document_id:
                try:
                    def _get_source_doc():
                        return (
                            get_supabase_client()
                            .table("documents")
                            .select("project_id")
                            .eq("id", source_document_id)
                            .single()
                            .execute()
                        )
                    src_doc = await async_db(_get_source_doc)
                    if src_doc.data:
                        source_project_id = src_doc.data.get("project_id")
                except Exception as e:
                    logger.warning(f"[BackgroundClone] Could not resolve source project: {e}")

            # 4. Clone Qdrant vectors
            vectors_cloned = 0
            if source_document_id and source_project_id:
                try:
                    from services.qdrant_service import qdrant_service

                    source_collection = f"project_{source_project_id}"
                    target_collection = f"project_{project_id}"

                    await qdrant_service.create_collection(target_collection)

                    vectors_cloned = await qdrant_service.clone_document_vectors(
                        source_collection=source_collection,
                        target_collection=target_collection,
                        source_document_id=source_document_id,
                        target_document_id=document_id,
                        target_document_name=doc_filename,
                    )

                    logger.info(
                        f"[BackgroundClone] Cloned {vectors_cloned} vectors for "
                        f"'{book['title']}' into project {project_id}"
                    )
                except Exception as e:
                    logger.error(f"[BackgroundClone] Vector clone failed: {e}")

            # 5. Finalize
            if vectors_cloned > 0:
                await self._copy_topics_and_complete(
                    source_document_id=source_document_id,
                    target_document_id=document_id,
                )
                logger.info(
                    f"[BackgroundClone] '{book['title']}' completed (cloned {vectors_cloned} vectors)"
                )
            else:
                logger.warning(
                    f"[BackgroundClone] No vectors to clone for '{book['title']}' — "
                    "falling back to full embedding pipeline"
                )
                await self._embed_imported_text(
                    document_id=document_id,
                    project_id=project_id,
                    filename=doc_filename,
                    text_content=text_content,
                )

        except Exception as e:
            logger.error(f"[BackgroundClone] Fatal error for {document_id}: {e}")
            await self._update_doc_status(document_id, "failed", str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # Fast path helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _copy_topics_and_complete(
        self,
        source_document_id: str,
        target_document_id: str,
    ):
        """
        Copy topics from source document to target document and mark as completed.
        Called immediately after a successful vector clone — no LLM needed.
        """
        try:
            # Fetch source topics
            def _get_topics():
                return (
                    get_supabase_client()
                    .table("documents")
                    .select("topics")
                    .eq("id", source_document_id)
                    .single()
                    .execute()
                )

            src = await async_db(_get_topics)
            topics = (src.data or {}).get("topics") or []

            # Update target with topics + completed status
            def _complete():
                return (
                    get_supabase_client()
                    .table("documents")
                    .update({
                        "upload_status": "completed",
                        "topics": topics,
                        "error_message": None,
                    })
                    .eq("id", target_document_id)
                    .execute()
                )

            await async_db(_complete)
            logger.info(
                f"[BookImport] Document {target_document_id} marked completed "
                f"with {len(topics)} topics (copied from {source_document_id})"
            )

        except Exception as e:
            logger.error(
                f"[BookImport] Failed to copy topics/complete for {target_document_id}: {e}"
            )
            # Still mark as completed even without topics
            try:
                await async_db(
                    lambda: get_supabase_client()
                    .table("documents")
                    .update({"upload_status": "completed", "error_message": None})
                    .eq("id", target_document_id)
                    .execute()
                )
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────────────
    # Fallback — full re-embed (only used if vector clone fails)
    # ──────────────────────────────────────────────────────────────────────────

    async def _embed_imported_text(
        self,
        document_id: str,
        project_id: str,
        filename: str,
        text_content: str,
    ):
        """
        Fallback: full embedding pipeline for imported book text.
        Only triggered when source Qdrant vectors are missing.
        """
        from utils.progress_manager import get_progress_manager
        from utils.text_chunker import TextChunker
        from services.qdrant_service import qdrant_service
        from services.embedding_service import embedding_service

        progress = get_progress_manager()
        doc_semaphore = EmbeddingQueue.get_doc_semaphore()

        try:
            if doc_semaphore.locked():
                await progress.emit(document_id, "queued", 0, "Waiting for processing slot...")

            async with doc_semaphore:
                await progress.emit(document_id, "chunking", 0, "Chunking book content...")

                chunker = TextChunker(
                    chunk_size=settings.CHUNK_SIZE,
                    overlap=settings.CHUNK_OVERLAP,
                )
                loop = asyncio.get_running_loop()
                chunks = await loop.run_in_executor(
                    None, lambda: chunker.chunk_text(text_content)
                )

                if not chunks:
                    await self._update_doc_status(document_id, "failed", "No content chunks")
                    return

                await progress.emit(document_id, "chunking", 100, f"Generated {len(chunks)} chunks")

                collection_name = f"project_{project_id}"
                await qdrant_service.create_collection(collection_name)
                await progress.emit(document_id, "embedding", 0, f"Embedding {len(chunks)} chunks...")

                from services.document_service import document_service
                await document_service._process_embeddings_direct(
                    chunks, document_id, filename, collection_name
                )

                await progress.emit(document_id, "topics", 0, "Generating topics...")
                llm_semaphore = EmbeddingQueue.get_llm_semaphore()
                try:
                    from services.mcq_service import mcq_service
                    async with llm_semaphore:
                        await mcq_service.generate_document_topics(project_id, document_id)
                    await progress.emit(document_id, "topics", 100, "Topics generated")
                except Exception as te:
                    logger.warning(f"Topic generation skipped for import: {te}")
                    await progress.emit(document_id, "topics", 100, "Topics skipped")

                await self._update_doc_status(document_id, "completed")
                await progress.emit(document_id, "completed", 100, "Book import complete")
                logger.info(f"Imported book {filename} embedded successfully (fallback path)")

        except Exception as e:
            logger.error(f"Failed to embed imported book {document_id}: {e}")
            await self._update_doc_status(document_id, "failed", str(e))
            await progress.emit(document_id, "failed", 0, str(e))

    async def _update_doc_status(self, document_id: str, status: str, message: str = None):
        try:
            update = {"upload_status": status}
            if message:
                update["error_message"] = message
            await async_db(
                lambda: self.client.table("documents")
                .update(update)
                .eq("id", document_id)
                .execute()
            )
        except Exception as e:
            logger.warning(f"Failed to update doc status: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Book metadata management
    # ──────────────────────────────────────────────────────────────────────────

    async def update_book(
        self, book_id: str, user_id: str, updates: Dict[str, Any]
    ) -> Dict:
        """Update book metadata / visibility. Only owner can update."""
        book = await self.get_book(book_id, user_id)
        if not book:
            raise ValueError("Book not found")
        if book["user_id"] != user_id:
            raise PermissionError("Only the book owner can edit this book")

        allowed = {"title", "author", "description", "cover_url", "tags", "is_public"}
        safe_updates = {k: v for k, v in updates.items() if k in allowed}

        if not safe_updates:
            return book

        if "description" in safe_updates and safe_updates["description"]:
            safe_updates["description"] = safe_updates["description"][
                :settings.BOOK_STORE_MAX_DESCRIPTION
            ]

        def _update():
            return (
                get_supabase_client()
                .table("books")
                .update(safe_updates)
                .eq("id", book_id)
                .execute()
            )

        result = await async_db(_update)
        return result.data[0] if result.data else book

    async def delete_book(self, book_id: str, user_id: str):
        """
        Delete a book from the store.
        Only the original uploader can delete.
        Also cleans up the text file from storage.
        """
        book = await self.get_book(book_id, user_id)
        if not book:
            raise ValueError("Book not found")
        if book["user_id"] != user_id:
            raise PermissionError("Only the book owner can delete this book")

        if book.get("text_path"):
            try:
                def _delete_text():
                    get_supabase_client().storage.from_(
                        settings.BOOK_IMPORT_TEXTS_BUCKET
                    ).remove([book["text_path"]])

                await async_db(_delete_text)
            except Exception as e:
                logger.warning(f"Could not delete text file for book {book_id}: {e}")

        def _delete_book():
            return (
                get_supabase_client()
                .table("books")
                .delete()
                .eq("id", book_id)
                .execute()
            )

        await async_db(_delete_book)
        logger.info(f"Book {book_id} deleted by user {user_id}")


book_service = BookService()
