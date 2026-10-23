"""
Real-Time Progress Manager for Document Processing.

Uses asyncio.Queue per document to push SSE events to connected clients.
Supports multiple subscribers per document (e.g., multiple browser tabs).
Auto-cleans up after document processing completes.

With several backend instances, the app may be connected to one that isn't
processing the document. So the latest event is also saved on the document row
(documents.progress, throttled), and subscribers fall back to reading it.
"""

import asyncio
import time
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

    PERSIST_EVERY = 2.5   # seconds between DB writes per document (stage changes always write)
    POLL_EVERY = 3.0      # seconds between DB reads when nothing arrives locally

    def __init__(self):
        # document_id -> list of asyncio.Queue (one per subscriber)
        self._subscribers: Dict[str, list] = {}
        self._lock = asyncio.Lock()
        self._persisted: Dict[str, tuple] = {}  # document_id -> (monotonic time, stage)
        self._tasks: set = set()

    def _persist(self, document_id: str, event: "ProgressEvent"):
        """Save the latest event on the document row (fire and forget, throttled)."""
        last = self._persisted.get(document_id)
        now = time.monotonic()
        terminal = event.stage in ("completed", "failed")
        if last and last[1] == event.stage and now - last[0] < self.PERSIST_EVERY and not terminal:
            return
        self._persisted[document_id] = (now, event.stage)
        if terminal:
            self._persisted.pop(document_id, None)
        payload = {"stage": event.stage, "progress": event.progress, "message": event.message, "ts": event.timestamp}

        async def write():
            try:
                from db.client import get_supabase_client, async_db
                client = get_supabase_client()
                await async_db(lambda: client.table("documents").update({"progress": payload}).eq("id", document_id).execute())
            except Exception as e:  # column missing or DB hiccup: the live stream still works
                logger.debug(f"[ProgressManager] persist skipped: {e}")

        task = asyncio.get_event_loop().create_task(write())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _read_saved(self, document_id: str):
        """Latest saved progress and status for a document (any instance's work)."""
        try:
            from db.client import get_supabase_client, async_db
            client = get_supabase_client()
            res = await async_db(lambda: client.table("documents").select("upload_status, progress, error_message").eq("id", document_id).limit(1).execute())
            return res.data[0] if res.data else None
        except Exception as e:
            logger.debug(f"[ProgressManager] read skipped: {e}")
            return None

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
        self._persist(document_id, event)

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

        last_saved_ts = None
        quiet_since = time.monotonic()
        try:
            while True:
                try:
                    # Events from this instance arrive instantly
                    event = await asyncio.wait_for(queue.get(), timeout=self.POLL_EVERY)
                    quiet_since = time.monotonic()
                    yield event

                    # Stop after terminal events
                    if event.stage in ("completed", "failed"):
                        return

                except asyncio.TimeoutError:
                    # Nothing locally: the document may be processed by another instance
                    row = await self._read_saved(document_id)
                    if row:
                        status = row.get("upload_status")
                        saved = row.get("progress") or {}
                        if status in ("completed", "ready"):
                            yield ProgressEvent(stage="completed", progress=100, message=saved.get("message") or "Done")
                            return
                        if status in ("failed", "error"):
                            yield ProgressEvent(stage="failed", progress=0, message=row.get("error_message") or saved.get("message") or "Processing failed")
                            return
                        if saved.get("ts") and saved.get("ts") != last_saved_ts:
                            last_saved_ts = saved["ts"]
                            quiet_since = time.monotonic()
                            yield ProgressEvent(stage=saved.get("stage", "processing"), progress=int(saved.get("progress") or 0),
                                                message=saved.get("message", ""), timestamp=saved["ts"])
                            continue
                    if time.monotonic() - quiet_since >= 25:
                        quiet_since = time.monotonic()
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
