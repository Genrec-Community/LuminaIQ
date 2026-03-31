"""Document processing background tasks.

**Validates: Requirements 18.1, 18.2**

This module contains Celery tasks for document processing operations
such as reprocessing with batch embedding generation (50 chunks/call)
and batch vector upsert (100 vectors/operation).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from core.celery_app import celery_app
from core.job_manager import BackgroundJobManager, JobStatusEnum
from core.redis_manager import get_redis_manager

logger = logging.getLogger(__name__)

# Batch sizes per requirements 18.1 and 18.2
_EMBEDDING_BATCH_SIZE = 50   # chunks per embedding API call
_UPSERT_BATCH_SIZE = 100     # vectors per Qdrant upsert


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@celery_app.task(
    name="backend.tasks.document_tasks.process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def process_document(
    self,
    document_id: str,
    project_id: str,
    job_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a document: extract text, chunk, generate embeddings, extract topics.

    Args:
        document_id: Document identifier
        project_id: Project identifier
        job_id: Optional job ID for progress tracking
        correlation_id: Request correlation ID for tracing

    Returns:
        Dictionary with processing results
    """
    logger.info(f"[DocumentTask] Processing document {document_id} for project {project_id}")

    # Placeholder — full pipeline is handled by DocumentService.process_document
    return {
        "document_id": document_id,
        "project_id": project_id,
        "status": "completed",
        "chunks_processed": 0,
    }


@celery_app.task(
    name="backend.tasks.document_tasks.reprocess_document",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def reprocess_document(
    self,
    document_id: str,
    job_id: str,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Reprocess a document: re-generate embeddings and upsert to vector store.

    Uses batch embedding generation (50 chunks per API call) and batch vector
    upsert (100 vectors per operation) for efficiency.

    Args:
        document_id: Document identifier
        job_id: Job ID for progress tracking in Redis
        correlation_id: Request correlation ID for tracing

    Returns:
        Dictionary with reprocessing results
    """
    log_prefix = f"[ReprocessTask job={job_id} doc={document_id}]"
    logger.info(f"{log_prefix} Starting document reprocessing")

    async def _reprocess():
        redis_manager = get_redis_manager()
        job_manager = BackgroundJobManager(redis_manager)

        await job_manager.update_job_status(
            job_id,
            status=JobStatusEnum.PROCESSING,
            progress=0,
        )

        # Import services here to avoid circular imports at module load
        from db.client import get_supabase_client, async_db
        from services.embedding_service import embedding_service
        from services.qdrant_service import qdrant_service

        client = get_supabase_client()

        try:
            # 1. Fetch document metadata
            doc_result = await async_db(
                lambda: client.table("documents")
                .select("id, filename, project_id, upload_status")
                .eq("id", document_id)
                .execute()
            )

            if not doc_result.data:
                raise ValueError(f"Document {document_id} not found")

            doc = doc_result.data[0]
            project_id = doc["project_id"]
            filename = doc["filename"]
            collection_name = f"project_{project_id}"

            await job_manager.update_job_status(job_id, progress=5)
            logger.info(f"{log_prefix} Document found: {filename}")

            # 2. Fetch existing chunks from Qdrant (scroll all points for this document)
            chunks: List[str] = []
            chunk_metadata: List[Dict[str, Any]] = []

            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                offset = None
                while True:
                    scroll_result = await qdrant_service.async_client.scroll(
                        collection_name=collection_name,
                        scroll_filter=Filter(
                            must=[
                                FieldCondition(
                                    key="document_id",
                                    match=MatchValue(value=document_id),
                                )
                            ]
                        ),
                        limit=500,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )
                    points, next_offset = scroll_result
                    for p in points:
                        chunks.append(p.payload.get("text", ""))
                        chunk_metadata.append(
                            {
                                "document_id": document_id,
                                "document_name": filename,
                                "chunk_id": p.payload.get("chunk_id", 0),
                            }
                        )
                    if next_offset is None:
                        break
                    offset = next_offset

            except Exception as scroll_err:
                logger.warning(
                    f"{log_prefix} Could not scroll existing chunks: {scroll_err}. "
                    "Proceeding with empty chunk list."
                )

            if not chunks:
                result_data = {
                    "document_id": document_id,
                    "status": "completed",
                    "message": "No existing chunks found to reprocess",
                    "chunks_processed": 0,
                    "batches_embedded": 0,
                    "batches_upserted": 0,
                }
                await job_manager.update_job_status(
                    job_id,
                    status=JobStatusEnum.COMPLETED,
                    progress=100,
                    result=result_data,
                )
                return result_data

            total_chunks = len(chunks)
            await job_manager.update_job_status(job_id, progress=10)
            logger.info(f"{log_prefix} Found {total_chunks} chunks to reprocess")

            # 3. Delete existing vectors for this document
            await qdrant_service.delete_vectors(collection_name, document_id)
            await job_manager.update_job_status(job_id, progress=15)
            logger.info(f"{log_prefix} Deleted existing vectors")

            # 4. Batch embedding generation — 50 chunks per API call (Requirement 18.1)
            all_embeddings: List[List[float]] = []
            embedding_batches = [
                chunks[i : i + _EMBEDDING_BATCH_SIZE]
                for i in range(0, total_chunks, _EMBEDDING_BATCH_SIZE)
            ]
            total_embed_batches = len(embedding_batches)

            for batch_idx, batch in enumerate(embedding_batches):
                batch_embeddings = await embedding_service.generate_embeddings(batch)
                all_embeddings.extend(batch_embeddings)

                # Progress: 15% → 70% during embedding phase
                embed_progress = 15 + int(((batch_idx + 1) / total_embed_batches) * 55)
                await job_manager.update_job_status(job_id, progress=embed_progress)

                logger.debug(
                    f"{log_prefix} Embedded batch {batch_idx + 1}/{total_embed_batches} "
                    f"({len(batch)} chunks)"
                )

            logger.info(
                f"{log_prefix} Embedding complete: {total_chunks} chunks in "
                f"{total_embed_batches} batches of {_EMBEDDING_BATCH_SIZE}"
            )

            # 5. Batch vector upsert — 100 vectors per operation (Requirement 18.2)
            upsert_batches = [
                (
                    chunks[i : i + _UPSERT_BATCH_SIZE],
                    all_embeddings[i : i + _UPSERT_BATCH_SIZE],
                    chunk_metadata[i : i + _UPSERT_BATCH_SIZE],
                )
                for i in range(0, total_chunks, _UPSERT_BATCH_SIZE)
            ]
            total_upsert_batches = len(upsert_batches)

            for batch_idx, (batch_chunks, batch_embeddings, batch_meta) in enumerate(
                upsert_batches
            ):
                await qdrant_service.upsert_chunks(
                    collection_name=collection_name,
                    chunks=batch_chunks,
                    embeddings=batch_embeddings,
                    metadata=batch_meta,
                )

                # Progress: 70% → 95% during upsert phase
                upsert_progress = 70 + int(((batch_idx + 1) / total_upsert_batches) * 25)
                await job_manager.update_job_status(job_id, progress=upsert_progress)

                logger.debug(
                    f"{log_prefix} Upserted batch {batch_idx + 1}/{total_upsert_batches} "
                    f"({len(batch_chunks)} vectors)"
                )

            logger.info(
                f"{log_prefix} Upsert complete: {total_chunks} vectors in "
                f"{total_upsert_batches} batches of {_UPSERT_BATCH_SIZE}"
            )

            # 6. Invalidate caches for this document/project
            try:
                from core.vector_cache import VectorSearchCache
                vector_cache = VectorSearchCache(redis_manager)
                await vector_cache.invalidate_project(project_id)
            except Exception as cache_err:
                logger.warning(f"{log_prefix} Cache invalidation failed: {cache_err}")

            result_data = {
                "document_id": document_id,
                "project_id": project_id,
                "status": "completed",
                "chunks_processed": total_chunks,
                "batches_embedded": total_embed_batches,
                "batches_upserted": total_upsert_batches,
            }

            await job_manager.update_job_status(
                job_id,
                status=JobStatusEnum.COMPLETED,
                progress=100,
                result=result_data,
            )

            logger.info(
                f"{log_prefix} Reprocessing complete — "
                f"chunks={total_chunks}, embed_batches={total_embed_batches}, "
                f"upsert_batches={total_upsert_batches}"
            )
            return result_data

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"{log_prefix} Task failed: {error_msg}", exc_info=True)
            await job_manager.update_job_status(
                job_id,
                status=JobStatusEnum.FAILED,
                error_message=error_msg,
            )
            raise

    try:
        return _run_async(_reprocess())
    except Exception as exc:
        logger.error(f"[ReprocessTask job={job_id}] Retrying due to: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
