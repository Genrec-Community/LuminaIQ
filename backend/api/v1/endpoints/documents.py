import os
import asyncio
import tempfile
from typing import List, Optional
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    Depends,
    Form,
    status,
)
from pydantic import BaseModel
from services.document_service import document_service
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service
from models.schemas import DocumentUploadResponse, DocumentList
from config.settings import settings
from api.deps import get_current_user
from utils.embedding_queue import get_embedding_queue
from utils.logger import logger
from db.client import async_db, get_supabase_client
from services.usage_service import usage, metered

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None
    limit: int = 10


class SearchResult(BaseModel):
    text: str
    document_id: str
    document_name: Optional[str] = None
    chunk_id: Optional[int] = None
    score: float


async def _start_processing(
    current_user: dict, project_id: str, temp_path: str, filename: str, content_type: str,
    file_size: int, is_public: bool = False, book_title: Optional[str] = None,
    book_author: Optional[str] = None, book_description: Optional[str] = None,
    book_tags: Optional[str] = None,
) -> dict:
    """Create the document record and process the file at temp_path in the background."""
    # 3. Create document record in Supabase
    doc_data = {
        "project_id": project_id,
        "filename": filename,
        "file_type": content_type,
        "file_size": file_size,
        "upload_status": "pending",
        "user_id": current_user.get("id"),
    }

    response = await async_db(
        lambda: get_supabase_client()
        .table("documents")
        .insert(doc_data)
        .execute()
    )

    if not response.data:
        raise HTTPException(500, "Failed to create document record")

    document = response.data[0]
    document_id = document["id"]

    # 4. Start CONCURRENT background processing
    # asyncio.create_task = truly parallel (vs Starlette BackgroundTasks which are serial)
    book_meta = None
    if is_public:
        book_meta = {
            "title": book_title or filename,
            "author": book_author,
            "description": book_description,
            "tags": [t.strip() for t in (book_tags or "").split(",") if t.strip()],
            "file_size": file_size,
            "file_type": content_type,
            "user_id": current_user.get("id"),
        }

    task = asyncio.create_task(
        document_service.process_document(
            document_id=document_id,
            project_id=project_id,
            file_path=temp_path,
            filename=filename,
            user_id=current_user.get("id"),
            book_meta=book_meta,
        )
    )

    # Ensure background task errors are always logged (not silently swallowed)
    def _log_task_exception(t):
        if t.cancelled():
            logger.warning(f"Background processing cancelled for {filename}")
        elif t.exception():
            logger.error(
                f"Background processing FAILED for {filename}: {t.exception()}"
            )

    task.add_done_callback(_log_task_exception)

    logger.info(
        f"Document {filename} upload started, processing in background "
        f"(public={is_public})"
    )

    return document


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    is_public: bool = Form(False),
    book_title: Optional[str] = Form(None),
    book_author: Optional[str] = Form(None),
    book_description: Optional[str] = Form(None),
    book_tags: Optional[str] = Form(None),  # comma-separated string from frontend
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a document and start processing.

    UNIFIED FLOW:
    1. Validate file type & size
    2. Save to temp file (memory efficient for large files)
    3. Create document DB record
    4. Background: extract text → save .txt to Supabase texts/ bucket → chunk → embed → topics → knowledge graph
    5. If is_public=True: create a book record in the books table
    6. Real-time SSE progress via /api/v1/progress/{document_id}

    NOTE: Raw original files are NOT stored in Supabase Storage.
    Only the extracted .txt is stored (10-50x smaller than PDFs).
    """
    metered(current_user, "upload")
    await usage.check_books(current_user["id"])
    temp_path = None
    try:
        # 1. Validate File Type
        allowed_mimes = [
            # Document formats
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/html",
            "text/markdown",
            # Image formats — processed via Azure Computer Vision OCR
            "image/jpeg",
            "image/png",
            "image/bmp",
            "image/tiff",
            "image/gif",
            "image/webp",
            # Some browsers send these for JPEG
            "image/jpg",
            "image/x-png",
        ]
        if file.content_type not in allowed_mimes:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Invalid file type. Supported: PDF, DOCX, TXT, HTML, MD (documents) "
                "and JPEG, PNG, BMP, TIFF, GIF, WebP (images — processed via OCR).",
            )

        file_ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid file extension. Allowed: {settings.ALLOWED_EXTENSIONS}",
            )

        # 2. Stream to temp file (memory-efficient for large files)
        os.makedirs("temp", exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file_ext}", dir="temp"
        )

        file_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > settings.MAX_FILE_SIZE:
                temp_file.close()
                os.unlink(temp_file.name)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"This file is larger than the {settings.MAX_FILE_SIZE // (1024 * 1024)} MB upload limit.",
                )
            temp_file.write(chunk)

        temp_file.close()
        temp_path = temp_file.name

        # 3-4. Create the record and start background processing
        return await _start_processing(
            current_user, project_id, temp_path, file.filename, file.content_type, file_size,
            is_public, book_title, book_author, book_description, book_tags,
        )

    except HTTPException:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        raise
    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(500, str(e))


UPLOADS_BUCKET = "uploads"

_UPLOAD_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


class StorageUploadRequest(BaseModel):
    project_id: str
    storage_path: str
    filename: str
    is_public: bool = False
    book_title: Optional[str] = None
    book_author: Optional[str] = None
    book_description: Optional[str] = None
    book_tags: Optional[str] = None


class UploadUrlRequest(BaseModel):
    project_id: str
    filename: str
    size: int


def upload_object_path(user_id: str, project_id: str, filename: str, size: int) -> str:
    """Stable per file (name + size), so a re-picked file resumes the same upload."""
    import re
    import unicodedata

    name = unicodedata.normalize("NFKD", filename)
    name = re.sub(r"[^\w.-]+", "_", name)[-120:]
    return f"{user_id}/{project_id}/{size}-{name}"


async def create_signed_upload(path: str) -> str:
    """A short-lived token that lets the browser upload this one object (any login method)."""
    import httpx

    base = settings.SUPABASE_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base}/storage/v1/object/upload/sign/{UPLOADS_BUCKET}/{path}",
            headers={"Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                     "apikey": settings.SUPABASE_SERVICE_KEY, "x-upsert": "true"},
            json={},
        )
    if resp.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't prepare the upload ({resp.status_code}).")
    url = resp.json().get("url", "")
    from urllib.parse import parse_qs, urlparse

    token = (parse_qs(urlparse(url).query).get("token") or [""])[0]
    if not token:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't prepare the upload (no token).")
    return token


@router.post("/upload-url")
async def get_upload_url(request: UploadUrlRequest, current_user: dict = Depends(get_current_user)):
    """
    Permission for the browser to upload one book straight to storage
    (resumable), without needing a Supabase session in the browser: email
    logins go through this API and have none.
    """
    metered(current_user, "upload")
    await usage.check_books(current_user["id"])
    ext = os.path.splitext(request.filename)[1].lower().lstrip(".")
    if ext not in _UPLOAD_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Supported files: PDF, DOCX and TXT.")
    if request.size <= 0 or request.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"This file is larger than the {settings.MAX_FILE_SIZE // (1024 * 1024)} MB upload limit.",
        )
    path = upload_object_path(current_user["id"], request.project_id, request.filename, request.size)
    token = await create_signed_upload(path)
    return {"bucket": UPLOADS_BUCKET, "path": path, "token": token}


@router.post("/upload-from-storage")
async def upload_from_storage(
    request: StorageUploadRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Process a file the browser uploaded straight to Supabase Storage (resumable,
    in chunks; survives a page refresh). The file must be in the user's own
    folder of the private "uploads" bucket. It is streamed here, processed like
    a normal upload, and removed from the bucket.
    """
    import httpx

    metered(current_user, "upload")
    await usage.check_books(current_user["id"])

    path = request.storage_path.strip("/")
    if not path.startswith(f"{current_user['id']}/") or ".." in path:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That upload doesn't belong to you.")
    file_ext = os.path.splitext(request.filename)[1].lower().lstrip(".")
    if file_ext not in _UPLOAD_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Supported files: PDF, DOCX and TXT.")

    url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{UPLOADS_BUCKET}/{path}"
    headers = {"Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}", "apikey": settings.SUPABASE_SERVICE_KEY}
    os.makedirs("temp", exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}", dir="temp")
    temp_path = temp_file.name
    file_size = 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=20)) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                if resp.status_code == 404:
                    raise HTTPException(status.HTTP_404_NOT_FOUND, "The upload wasn't found. Please upload the file again.")
                if resp.status_code >= 400:
                    raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't fetch the upload ({resp.status_code}).")
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    file_size += len(chunk)
                    if file_size > settings.MAX_FILE_SIZE:
                        raise HTTPException(
                            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"This file is larger than the {settings.MAX_FILE_SIZE // (1024 * 1024)} MB upload limit.",
                        )
                    temp_file.write(chunk)
        temp_file.close()

        document = await _start_processing(
            current_user, request.project_id, temp_path, request.filename, _UPLOAD_TYPES[file_ext], file_size,
            request.is_public, request.book_title, request.book_author, request.book_description, request.book_tags,
        )
    except HTTPException:
        temp_file.close()
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    except Exception as e:
        temp_file.close()
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        logger.error(f"Upload-from-storage error: {e}")
        raise HTTPException(500, str(e))

    # The file is now on this server (the original PDF is kept by processing); free the bucket
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.request("DELETE", f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{UPLOADS_BUCKET}",
                                 headers=headers, json={"prefixes": [path]})
    except Exception as e:
        logger.debug(f"Could not remove {path} from {UPLOADS_BUCKET}: {e}")
    return document


@router.get("/{project_id}", response_model=DocumentList)
async def list_documents(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """List all documents for a project"""
    try:
        response = await async_db(
            lambda: document_service.client.table("documents")
            .select("*")
            .eq("project_id", project_id)
            .execute()
        )
        return {"documents": response.data}
    except Exception as e:
        raise HTTPException(500, str(e))


async def _owned_document(project_id: str, document_id: str, user_id: str) -> dict:
    """The document, if it belongs to one of this user's projects (else 404)."""
    client = get_supabase_client()
    project = await async_db(lambda: client.table("projects").select("user_id")
                             .eq("id", project_id).limit(1).execute())
    if not project.data or project.data[0]["user_id"] != user_id:
        raise HTTPException(404, "Document not found")
    doc = await async_db(lambda: client.table("documents")
                         .select("id, project_id, filename, file_type, file_url, text_storage_path")
                         .eq("id", document_id).eq("project_id", project_id).limit(1).execute())
    if not doc.data:
        raise HTTPException(404, "Document not found")
    return doc.data[0]


@router.get("/{project_id}/{document_id}/url")
async def get_document_url(
    project_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    How to show a document in the reader:
      {"kind": "pdf", "url": <signed URL>}  - the original PDF is stored
      {"kind": "text"}                      - no original (older uploads, other file
                                              types): the reader shows the full text
                                              from GET /{project_id}/{document_id}/text
    """
    doc = await _owned_document(project_id, document_id, current_user["id"])
    supabase = get_supabase_client()
    EXPIRY = 3600 * 6

    # Where the original lives: recorded at upload (class copies point at the
    # teacher's file), else the legacy conventions
    candidates = []
    if doc.get("file_url") and "/" in doc["file_url"]:
        bucket, path = doc["file_url"].split("/", 1)
        candidates.append((bucket, path))
    candidates += [("documents", f"{project_id}/{document_id}.pdf"), ("documents", f"{project_id}/{document_id}")]

    def _try_signed():
        for bucket, path in candidates:
            try:
                result = supabase.storage.from_(bucket).create_signed_url(path, EXPIRY)
                if isinstance(result, dict):
                    url = result.get("signedURL") or result.get("signed_url")
                    if url:
                        return url
            except Exception:
                continue
        return None

    url = await async_db(_try_signed)
    if url:
        return {"kind": "pdf", "url": url, "filename": doc["filename"]}
    return {"kind": "text", "filename": doc["filename"]}


@router.get("/{project_id}/{document_id}/text")
async def get_document_text(
    project_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Full extracted text, for reading documents that have no stored original."""
    doc = await _owned_document(project_id, document_id, current_user["id"])
    text = await document_service.load_stored_text({**doc, "project_id": project_id})
    if not text:
        raise HTTPException(404, "This document's text isn't available.")
    return {"filename": doc["filename"], "text": text}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str, project_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete a document"""
    try:
        await document_service.delete_document(project_id, document_id)
        return {"message": "Document deleted successfully"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/queue/status")
async def get_queue_status(current_user: dict = Depends(get_current_user)):
    """
    Get embedding queue status and current concurrency limits.

    Returns:
        - queued: Number of documents waiting
        - processing: Currently processing
        - limits: Currently active concurrency limits
    """
    try:
        queue = get_embedding_queue()
        return queue.get_queue_stats()
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/queue/{document_id}")
async def get_document_queue_status(
    document_id: str, current_user: dict = Depends(get_current_user)
):
    """Get queue status for a specific document."""
    try:
        queue = get_embedding_queue()
        doc_status = queue.get_document_status(document_id)
        if not doc_status:
            return {"status": "not_in_queue", "message": "Document not found in queue"}
        return doc_status
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{project_id}/search")
async def search_documents(
    project_id: str,
    request: SearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Semantic search across documents in a project."""
    try:
        # Vector search, or the stored text when the index is unavailable
        from services.retrieval import search_passages
        results = (await search_passages(
            project_id, [request.query], per_query=request.limit,
            document_ids=request.document_ids or None,
        ))[:request.limit]

        # Get document names from the database for richer results
        doc_names = {}
        if results:
            doc_ids = list(
                set(r.get("document_id") for r in results if r.get("document_id"))
            )
            if doc_ids:
                try:
                    docs_response = await async_db(
                        lambda: document_service.client.table("documents")
                        .select("id, filename")
                        .in_("id", doc_ids)
                        .execute()
                    )
                    for doc in docs_response.data:
                        doc_names[doc["id"]] = doc["filename"]
                except Exception as e:
                    logger.warning(f"Could not fetch document names: {e}")

        # Format results
        search_results = []
        for result in results:
            doc_id = result.get("document_id")
            search_results.append(
                {
                    "text": result.get("text", ""),
                    "document_id": doc_id,
                    "document_name": doc_names.get(doc_id, "Unknown"),
                    "chunk_id": result.get("chunk_id"),
                    "score": result.get("score", 0),
                }
            )

        return {"results": search_results, "query": request.query}

    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(500, f"Search failed: {str(e)}")
