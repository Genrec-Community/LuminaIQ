from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List
from services.document_service import document_service
from config.settings import settings
from utils.logger import logger

router = APIRouter()


class WebhookPayload(BaseModel):
    """
    Payload from PDF service containing chunks directly.

    OPTIMIZED FLOW: Chunks are sent directly in the request body,
    eliminating the need for document_chunks table in Supabase.
    """

    document_id: str
    project_id: str
    filename: str
    chunks: List[str]
    secret: str


class WebhookResponse(BaseModel):
    status: str
    message: str


@router.post("/document-ready", response_model=WebhookResponse)
async def document_ready_webhook(
    payload: WebhookPayload, background_tasks: BackgroundTasks
):
    """
    Webhook endpoint called by PDF service with document chunks.

    OPTIMIZED ARCHITECTURE:
    - Chunks are sent directly in the request body (no Supabase fetch)
    - Embedding generation runs in background task
    - Returns immediately to PDF service

    Flow: PDF Service → [chunks in body] → Backend → Qdrant
    """
    try:
        # Verify webhook secret
        expected_secret = getattr(settings, "WEBHOOK_SECRET", "supersecretwebhook")
        if payload.secret != expected_secret:
            logger.warning(f"Invalid webhook secret for document {payload.document_id}")
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

        chunk_count = len(payload.chunks)
        logger.info(
            f"Received {chunk_count} chunks for document {payload.document_id} ({payload.filename})"
        )

        # Process chunks in background task for faster response
        background_tasks.add_task(
            document_service.process_chunks_direct,
            document_id=payload.document_id,
            project_id=payload.project_id,
            filename=payload.filename,
            chunks=payload.chunks,
        )

        return {
            "status": "success",
            "message": f"Started embedding generation for {chunk_count} chunks",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
