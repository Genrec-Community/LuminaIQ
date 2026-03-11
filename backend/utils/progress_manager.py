"""
Real-Time Progress Manager for Document Processing.

Uses asyncio.Queue per document to push SSE events to connected clients.
Supports multiple subscribers per document (e.g., multiple browser tabs).
Auto-cleans up after document processing completes.
"""

import asyncio
from typing import Dict, AsyncGenerator, Optional
from dataclasses import dataclass, field
from datetime import datetime
from utils.logger import logger


@dataclass
class ProgressEvent:
    """A single progress update event"""
    stage: str          # extracting, chunking, embedding, topics, graph, completed, failed
    progress: int       # 0-100
    message: str = ""   # Human-readable status message
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ProgressManager:
    """
    Manages real-time progress updates for document processing.

    Usage:
        # In document_service (producer):
        progress_manager.emit(doc_id, "embedding", 45, "Processing batch 9/20...")

        # In SSE endpoint (consumer):
        async for event in progress_manager.subscribe(doc_id):
            yield f"data: {event}\\n\\n"
    """

    def __init__(self):
        # document_id -> list of asyncio.Queue (one per subscriber)
        self._subscribers: Dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def emit(self, document_id: str, stage: str, progress: int, message: str = ""):
        """
        Emit a progress event to all subscribers of a document.

        Args:
            document_id: The document being processed
            stage: Current processing stage
            progress: 0-100 percentage
            message: Human-readable status
        """
        event = ProgressEvent(stage=stage, progress=progress, message=message)

        async with self._lock:
            queues = self._subscribers.get(document_id, [])

        # Send to all subscribers (non-blocking)
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event if queue is full (subscriber is slow)
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

        # Auto-cleanup on terminal states
        if stage in ("completed", "failed"):
            # Give subscribers a moment to receive the final event
            asyncio.get_event_loop().call_later(5.0, self._cleanup_sync, document_id)

    async def subscribe(self, document_id: str) -> AsyncGenerator[ProgressEvent, None]:
        """
        Subscribe to progress events for a document.

        Yields ProgressEvent objects until the document processing completes or fails.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        async with self._lock:
            if document_id not in self._subscribers:
                self._subscribers[document_id] = []
            self._subscribers[document_id].append(queue)

        logger.info(f"[ProgressManager] Subscriber added for document {document_id}")

        try:
            while True:
                try:
                    # Wait for events with a timeout to allow cleanup
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event

                    # Stop after terminal events
                    if event.stage in ("completed", "failed"):
                        return

                except asyncio.TimeoutError:
                    # Send a keepalive ping
                    yield ProgressEvent(stage="keepalive", progress=-1, message="")

        finally:
            # Unsubscribe
            async with self._lock:
                queues = self._subscribers.get(document_id, [])
                if queue in queues:
                    queues.remove(queue)
                if not queues and document_id in self._subscribers:
                    del self._subscribers[document_id]

            logger.info(f"[ProgressManager] Subscriber removed for document {document_id}")

    def _cleanup_sync(self, document_id: str):
        """Synchronous cleanup callback (called from call_later)"""
        if document_id in self._subscribers:
            # Only clean up if no active subscribers remain
            if not self._subscribers[document_id]:
                del self._subscribers[document_id]

    def get_subscriber_count(self, document_id: str) -> int:
        """Get number of active subscribers for a document"""
        return len(self._subscribers.get(document_id, []))


# Singleton instance
_progress_manager: Optional[ProgressManager] = None


def get_progress_manager() -> ProgressManager:
    """Get the global progress manager instance"""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager
