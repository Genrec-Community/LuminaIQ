import asyncio
import os
import socket
import sys
import uuid

from config.settings import settings
from services.document_job_service import DocumentJobService
from utils.logger import logger


class DocumentWorkerDisabledError(RuntimeError):
    pass


class DocumentWorkerNotIntegratedError(RuntimeError):
    pass


def ensure_worker_enabled(worker_settings=settings) -> None:
    if not worker_settings.DOCUMENT_JOBS_ENABLED:
        raise DocumentWorkerDisabledError("DOCUMENT_JOBS_ENABLED is false")
    if not worker_settings.DOCUMENT_WORKER_ENABLED:
        raise DocumentWorkerDisabledError("DOCUMENT_WORKER_ENABLED is false")
    raise DocumentWorkerNotIntegratedError(
        "Durable original storage and the document pipeline are not integrated"
    )


async def poll_once(
    service: DocumentJobService, worker_id: str, worker_settings=settings
) -> bool:
    raise DocumentWorkerNotIntegratedError(
        "Refusing to claim jobs before pipeline integration"
    )


async def run_worker(worker_settings=settings, service=None, stop_event=None) -> None:
    ensure_worker_enabled(worker_settings)
    service = service or DocumentJobService()
    stop_event = stop_event or asyncio.Event()
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"

    while not stop_event.is_set():
        claimed = await poll_once(service, worker_id, worker_settings)
        if not claimed:
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=worker_settings.DOCUMENT_JOB_POLL_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                pass


def main() -> int:
    try:
        asyncio.run(run_worker())
    except DocumentWorkerDisabledError as error:
        logger.error(f"Document worker refused to start: {error}")
        return 2
    except DocumentWorkerNotIntegratedError as error:
        logger.error(f"Document worker refused to start: {error}")
        return 3
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
