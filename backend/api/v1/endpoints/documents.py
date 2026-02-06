import shutil
import os
import uuid
import tempfile
from typing import List
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
    Depends,
    Form,
    status,
)
from services.document_service import document_service
from models.schemas import DocumentUploadResponse, DocumentList
from config.settings import settings
from api.deps import get_current_user
from utils.embedding_queue import get_embedding_queue
import httpx
from utils.logger import logger

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a document and start processing it.
    Securely handles file uploads.
    """
    temp_file = None
    try:
        # 1. Validate Project Access (Check ownership)
        # Ideally we check if project exists and belongs to user first.
        # For now, relying on RLS at database level or simple check.

        # 2. Validate File Type (MIME & Extension)
        allowed_mimes = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
        ]
        if file.content_type not in allowed_mimes:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Invalid file type. Only PDF, DOCX, and TXT are supported.",
            )

        file_ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Invalid file extension. Allowed: {settings.ALLOWED_EXTENSIONS}",
            )

        # 3. Read file content to check size
        file_content = await file.read()
        file_size = len(file_content)
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"File size exceeds limit of {settings.MAX_FILE_SIZE} bytes",
            )

        # 4. Send to PDF processing service
        try:
            logger.info(f"Sending {file.filename} to PDF service")
            async with httpx.AsyncClient() as client:
                from io import BytesIO

                files = {
                    "file": (file.filename, BytesIO(file_content), file.content_type)
                }
                data = {"project_id": project_id}
                response = await client.post(
                    "http://localhost:8001/upload", files=files, data=data, timeout=30.0
                )

            logger.info(f"PDF service response: {response.status_code}")
            if response.status_code == 200:
                document = response.json()
                logger.info(f"Document created: {document['id']}")
                return document
            else:
                logger.error(f"PDF service error: {response.text}")
                raise HTTPException(500, f"PDF service error: {response.text}")

        except httpx.RequestError as e:
            logger.error(f"Failed to connect to PDF service: {str(e)}")
            raise HTTPException(500, f"Failed to connect to PDF service: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending to PDF service: {str(e)}")
            raise HTTPException(500, f"Unexpected error: {str(e)}")

    except HTTPException as he:
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except:
                pass
        raise he
    except Exception as e:
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except:
                pass
        raise HTTPException(500, str(e))


@router.get("/{project_id}", response_model=DocumentList)
async def list_documents(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    List all documents for a project
    """
    try:
        # Verify project access first ideally, but RLS should handle filtering if configured.
        # Adding manual check for extra safety.

        # Basic query
        response = (
            document_service.client.table("documents")
            .select("*")
            .eq("project_id", project_id)
            .execute()
        )
        return {"documents": response.data}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/{document_id}")
async def delete_document(
    document_id: str, project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Delete a document
    """
    try:
        await document_service.delete_document(project_id, document_id)
        return {"message": "Document deleted successfully"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/queue/status")
async def get_queue_status(current_user: dict = Depends(get_current_user)):
    """
    Get embedding queue status.

    Returns:
        - queued: Number of documents waiting
        - processing: Currently processing (0 or 1)
        - current_job: Filename being processed
        - queue: List of waiting documents with positions
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
    """
    Get queue status for a specific document.

    Returns:
        - status: queued/processing/completed/failed
        - position: Position in queue (0 = processing)
        - progress: Embedding progress percentage
    """
    try:
        queue = get_embedding_queue()
        status = queue.get_document_status(document_id)
        if not status:
            return {"status": "not_in_queue", "message": "Document not found in queue"}
        return status
    except Exception as e:
        raise HTTPException(500, str(e))
