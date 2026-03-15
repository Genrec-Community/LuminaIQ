"""
SSE endpoint for real-time document processing progress.

Frontend connects via EventSource to receive live updates
during PDF extraction, chunking, embedding, and post-processing.

Note: EventSource API doesn't support custom headers, so auth
token is passed via query parameter instead of Authorization header.
"""

import json
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jose import jwt, JWTError
from config.settings import settings
from utils.progress_manager import get_progress_manager
from utils.logger import logger

router = APIRouter()


async def _verify_token(token: str) -> dict:
    """Verify JWT token from query parameter (EventSource can't send headers)"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return {"id": user_id, "email": payload.get("email")}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


@router.get("/{document_id}")
async def stream_document_progress(
    document_id: str,
    token: str = Query(..., description="JWT auth token (EventSource can't send headers)"),
):
    """
    SSE endpoint for real-time document processing progress.

    Events are JSON objects with:
    - stage: extracting | chunking | embedding | topics | graph | completed | failed
    - progress: 0-100 (percentage)
    - message: Human-readable status

    Usage (frontend):
        const es = new EventSource(`/api/v1/progress/${docId}?token=...`);
        es.onmessage = (e) => {
            const data = JSON.parse(e.data);
            updateProgressBar(data.progress);
        };
    """
    # Authenticate via query param
    await _verify_token(token)

    progress_manager = get_progress_manager()

    async def event_generator():
        async for event in progress_manager.subscribe(document_id):
            if event.stage == "keepalive":
                yield ": keepalive\n\n"
            else:
                data = json.dumps({
                    "stage": event.stage,
                    "progress": event.progress,
                    "message": event.message,
                    "timestamp": event.timestamp,
                })
                yield f"data: {data}\n\n"

                # Stop streaming on terminal events
                if event.stage in ("completed", "failed"):
                    return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
