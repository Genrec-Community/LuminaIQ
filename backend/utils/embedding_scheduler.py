import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional
from uuid import NAMESPACE_URL, uuid5

from config.settings import settings
from utils.logger import logger


class EmbeddingResultError(ValueError):
    """The provider returned an unusable result for a valid batch request."""


@dataclass
class BatchFailure:
    batch_number: int
    error: Exception


class EmbeddingBatchError(RuntimeError):
    def __init__(self, failures: List[BatchFailure], total_batches: int):
        self.failures = failures
        self.total_batches = total_batches
        first = failures[0]
        super().__init__(
            f"Embedding failed for {len(failures)}/{total_batches} batches; "
            f"batch {first.batch_number}: {first.error}"
        )


def embedding_point_id(collection_name: str, document_id: str, chunk_id: int) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"luminaiq:{collection_name}:{document_id}:{chunk_id}",
        )
    )


def _status_code(error: Exception) -> Optional[int]:
    code = getattr(error, "status_code", None)
    if code is None:
        response = getattr(error, "response", None)
        code = getattr(response, "status_code", None)
    return code if isinstance(code, int) else None


def is_transient_embedding_error(error: Exception) -> bool:
    if isinstance(error, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
        return True

    if _status_code(error) in {408, 409, 429, 500, 502, 503, 504}:
        return True

    error_type = type(error).__name__.lower()
    if any(
        name in error_type
        for name in (
            "ratelimit",
            "apitimeout",
            "apiconnection",
            "internalserver",
            "readtimeout",
            "writetimeout",
            "connecttimeout",
            "connecterror",
            "pooltimeout",
            "networkerror",
            "remoteprotocol",
            "responsehandling",
        )
    ):
        return True

    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "429",
            "too many requests",
            "rate limit",
            "timeout",
            "timed out",
            "connection",
            "unavailable",
            "connection reset",
            "connection refused",
            "broken pipe",
            "temporary failure",
            "name resolution",
            "server disconnected",
            "temporarily unavailable",
            "service unavailable",
        )
    )


class EmbeddingBatchScheduler:
    """Owns batch execution, retries, validation, and progress within one worker."""

    def __init__(
        self,
        max_embedding_calls: int,
        max_db_operations: int,
        max_retries: int,
        max_retry_delay_s: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ):
        self.max_embedding_calls = max(1, max_embedding_calls)
        self.max_db_operations = max(1, max_db_operations)
        self.max_retries = max(0, max_retries)
        self.max_retry_delay_s = max(0.0, max_retry_delay_s)
        self.sleep = sleep
        self.jitter = jitter
        self._loop = None
        self._embed_semaphore = None
        self._db_semaphore = None
        self._document_locks = {}

    def _ensure_loop_resources(self):
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop = loop
            self._embed_semaphore = asyncio.Semaphore(self.max_embedding_calls)
            self._db_semaphore = asyncio.Semaphore(self.max_db_operations)
            self._document_locks = {}

    async def process(
        self,
        chunks: List[str],
        batch_size: int,
        embed_batch: Callable[[List[str]], Awaitable[List[List[float]]]],
        write_batch: Callable[
            [int, List[str], List[List[float]]], Awaitable[None]
        ],
        on_progress: Optional[Callable[[int, int], Awaitable[None]]] = None,
        label: str = "document",
        document_key: Optional[str] = None,
        finalize: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> None:
        if not chunks:
            return
        if batch_size <= 0:
            raise ValueError("Embedding batch size must be positive")

        self._ensure_loop_resources()
        if document_key is not None:
            lock = self._document_locks.setdefault(document_key, asyncio.Lock())
            async with lock:
                return await self.process(
                    chunks=chunks,
                    batch_size=batch_size,
                    embed_batch=embed_batch,
                    write_batch=write_batch,
                    on_progress=on_progress,
                    label=label,
                    finalize=finalize,
                )

        total_batches = (len(chunks) + batch_size - 1) // batch_size
        worker_count = min(self.max_embedding_calls, total_batches)
        next_batch = 0
        completed = 0
        index_lock = asyncio.Lock()
        progress_lock = asyncio.Lock()
        failures: List[BatchFailure] = []

        async def claim_batch():
            nonlocal next_batch
            async with index_lock:
                if next_batch >= total_batches:
                    return None
                batch_index = next_batch
                next_batch += 1
                start = batch_index * batch_size
                return batch_index, start, chunks[start : start + batch_size]

        async def worker():
            nonlocal completed
            while True:
                claimed = await claim_batch()
                if claimed is None:
                    return
                batch_index, start_index, batch = claimed
                try:
                    embeddings = await self._embed_with_retry(
                        batch, embed_batch, batch_index, label
                    )
                    if len(embeddings) != len(batch):
                        raise EmbeddingResultError(
                            "embedding count "
                            f"{len(embeddings)} does not match chunk count {len(batch)}"
                        )

                    await self._call_with_retry(
                        lambda: self._call_database(
                            lambda: write_batch(start_index, batch, embeddings)
                        ),
                        batch_index,
                        label,
                        "Qdrant write",
                    )

                    async with progress_lock:
                        completed += 1
                        if on_progress:
                            await on_progress(completed, total_batches)
                except Exception as error:
                    failures.append(BatchFailure(batch_index + 1, error))

        await asyncio.gather(*(worker() for _ in range(worker_count)))

        if failures:
            raise EmbeddingBatchError(failures, total_batches)
        if finalize:
            await self._call_with_retry(
                lambda: self._call_database(finalize),
                total_batches - 1,
                label,
                "Qdrant finalize",
            )

    async def _embed_with_retry(
        self,
        batch: List[str],
        embed_batch: Callable[[List[str]], Awaitable[List[List[float]]]],
        batch_index: int,
        label: str,
    ) -> List[List[float]]:
        return await self._call_with_retry(
            lambda: self._call_embedding_provider(embed_batch, batch),
            batch_index,
            label,
            "embedding request",
        )

    async def _call_embedding_provider(self, embed_batch, batch):
        async with self._embed_semaphore:
            return await embed_batch(batch)

    async def _call_database(self, operation):
        async with self._db_semaphore:
            return await operation()

    async def _call_with_retry(
        self,
        operation: Callable[[], Awaitable],
        batch_index: int,
        label: str,
        operation_name: str,
    ):
        for attempt in range(self.max_retries + 1):
            try:
                return await operation()
            except Exception as error:
                if not is_transient_embedding_error(error):
                    raise
                if attempt >= self.max_retries:
                    raise

                base_delay = min(2**attempt, self.max_retry_delay_s)
                delay = base_delay * self.jitter(0.75, 1.0)
                logger.warning(
                    f"[{label}] Batch {batch_index + 1} {operation_name} failed; "
                    f"retry {attempt + 1}/{self.max_retries} in {delay:.1f}s: {error}"
                )
                await self.sleep(delay)

        raise RuntimeError(f"{operation_name} retry loop exited unexpectedly")


_embedding_scheduler = None


def get_embedding_scheduler() -> EmbeddingBatchScheduler:
    global _embedding_scheduler
    if _embedding_scheduler is None:
        _embedding_scheduler = EmbeddingBatchScheduler(
            max_embedding_calls=settings.MAX_GLOBAL_EMBEDDINGS,
            max_db_operations=settings.MAX_GLOBAL_DB_OPERATIONS,
            max_retries=settings.EMBEDDING_MAX_RETRIES,
            max_retry_delay_s=settings.EMBEDDING_MAX_RETRY_DELAY_S,
        )
    return _embedding_scheduler
