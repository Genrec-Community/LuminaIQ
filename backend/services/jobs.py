"""
Background job handlers and the helpers that queue them.

Heavy work (reading and indexing an uploaded book, cloning a bookstore book,
re-indexing) runs on a worker, never in the request. The web process only
queues a job. Importing this module registers the handlers.
"""

import asyncio
import os
import tempfile
from typing import Any, Dict, Optional

from db.client import async_db, get_supabase_client
from utils import job_queue as q
from utils.logger import logger
from utils.worker import HOST, handler

STAGING_BUCKET = "documents"     # the existing originals bucket; staged files live under _staging/
STAGING_PREFIX = "_staging"


async def enqueue(kind: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    pg = get_supabase_client().pg
    return await async_db(lambda: q.enqueue(pg, kind, payload, **kwargs))


# --------------------------------------------------------------------------- documents

async def stage_upload(document_id: str, temp_path: str, filename: str) -> Dict[str, Any]:
    """
    Make an uploaded file reachable from any worker: copy it to storage. If that
    fails (storage down, file over the size limit), the job is pinned to this
    host, where the temp file is.
    """
    ext = os.path.splitext(filename)[1].lower() or ".bin"
    path = f"{STAGING_PREFIX}/{document_id}{ext}"
    try:
        with open(temp_path, "rb") as f:
            data = f.read()

        def _upload():
            get_supabase_client().storage.from_(STAGING_BUCKET).upload(
                file=data, path=path, file_options={"upsert": "true"})

        await async_db(_upload)
        return {"staged": f"{STAGING_BUCKET}/{path}"}
    except Exception as e:
        logger.warning(f"[Jobs] staging {filename} failed, pinning the job to {HOST}: {e}")
        return {"local_path": temp_path, "pinned_host": HOST}


async def queue_document_processing(*, document_id: str, project_id: str, temp_path: str,
                                    filename: str, user_id: str,
                                    book_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = await stage_upload(document_id, temp_path, filename)
    pinned = source.pop("pinned_host", None)
    if source.get("staged") and os.path.exists(temp_path):
        os.unlink(temp_path)   # the worker reads the staged copy
    payload = {"document_id": document_id, "project_id": project_id, "filename": filename,
               "user_id": user_id, "book_meta": book_meta, **source}
    return await enqueue("process_document", payload, user_id=user_id or None,
                         dedupe_key=f"process_document:{document_id}", pinned_host=pinned)


@handler("process_document")
async def handle_process_document(job: Dict[str, Any]) -> Dict[str, Any]:
    from services.document_service import document_service

    p = job["payload"]
    staged = p.get("staged")
    if staged:
        bucket, path = staged.split("/", 1)
        data = await async_db(lambda: get_supabase_client().storage.from_(bucket).download(path))
        os.makedirs("temp", exist_ok=True)
        fd, file_path = tempfile.mkstemp(suffix=os.path.splitext(path)[1], dir="temp")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    else:
        file_path = p["local_path"]
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"upload file is gone: {file_path}")

    await document_service.process_document(
        document_id=p["document_id"], project_id=p["project_id"], file_path=file_path,
        filename=p["filename"], user_id=p.get("user_id") or "", book_meta=p.get("book_meta"),
    )
    if staged:
        try:
            await async_db(lambda: get_supabase_client().storage.from_(bucket).remove([path]))
        except Exception as e:
            logger.debug(f"[Jobs] staged copy not removed: {e}")
    return {"document_id": p["document_id"]}


@handler("reindex_document")
async def handle_reindex_document(job: Dict[str, Any]) -> Dict[str, Any]:
    from services.document_service import document_service

    doc = job["payload"]["document"]
    await document_service._reindex_from_storage(doc)
    return {"document_id": doc["id"]}


# --------------------------------------------------------------------------- book store

@handler("book_clone")
async def handle_book_clone(job: Dict[str, Any]) -> Dict[str, Any]:
    from services.book_service import book_service

    p = job["payload"]
    await book_service._background_clone(
        book=p["book"], document_id=p["document_id"], project_id=p["project_id"],
        doc_filename=p["doc_filename"], source_text_path=p.get("source_text_path"),
    )
    return {"document_id": p["document_id"]}
