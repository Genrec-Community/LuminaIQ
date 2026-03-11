from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
    PayloadSchemaType,
)
from config.settings import settings
from typing import List, Dict, Any, Optional
from uuid import uuid4
from utils.logger import logger
from services.embedding_service import embedding_service
import asyncio


class QdrantService:
    """
    Qdrant vector database service with ASYNC client for non-blocking operations.

    Features:
    - AsyncQdrantClient for all direct operations (non-blocking event loop)
    - Sync client retained only for LangChain VectorStore compatibility
    - Automatic retry with exponential backoff for transient failures
    - Longer timeout for large batch operations
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds

    # Connection pool and timeout settings for multi-user load
    ASYNC_TIMEOUT = 120        # Longer timeout for batch embedding upserts
    SYNC_TIMEOUT = 30          # Shorter timeout for search queries (user-facing)
    GRPC_OPTIONS = {
        "grpc.max_send_message_length": 64 * 1024 * 1024,   # 64MB
        "grpc.max_receive_message_length": 64 * 1024 * 1024, # 64MB
        "grpc.keepalive_time_ms": 30000,                     # 30s keepalive
        "grpc.keepalive_timeout_ms": 10000,                   # 10s timeout
    }

    def __init__(self):
        # Async client for all direct operations — does NOT block the event loop
        self.async_client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=self.ASYNC_TIMEOUT,
            grpc_options=self.GRPC_OPTIONS,
        )
        # Sync client kept ONLY for LangChain QdrantVectorStore compatibility
        self._sync_client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=self.SYNC_TIMEOUT,
            grpc_options=self.GRPC_OPTIONS,
        )
        logger.info(
            f"[QdrantService] Initialized with AsyncQdrantClient | "
            f"async_timeout={self.ASYNC_TIMEOUT}s, sync_timeout={self.SYNC_TIMEOUT}s"
        )

    async def create_collection(self, collection_name: str, vector_size: int = settings.EMBEDDING_DIMENSION):
        """Create a new collection and ensure indexes exist (fully async)"""
        try:
            collections = await self.async_client.get_collections()
            exists = any(col.name == collection_name for col in collections.collections)

            if not exists:
                await self.async_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Created collection: {collection_name}")
            else:
                logger.info(f"Collection already exists: {collection_name}")

            # Always ensure indexes exist
            await self._ensure_indexes(collection_name)

        except Exception as e:
            logger.error(f"Error creating collection: {str(e)}")
            raise

    async def _ensure_indexes(self, collection_name: str):
        """Create payload indexes if they don't exist (async)"""
        try:
            await self.async_client.create_payload_index(
                collection_name=collection_name,
                field_name="document_id",
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
            )
            await self.async_client.create_payload_index(
                collection_name=collection_name,
                field_name="chunk_id",
                field_schema=PayloadSchemaType.INTEGER,
                wait=True,
            )
            logger.info(f"Verified/Created indexes for {collection_name}")
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.warning(f"Index creation warning: {e}")

    async def upsert_chunks(
        self,
        collection_name: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]],
    ):
        """
        Insert chunks into collection with automatic retry (fully async).

        No longer blocks the event loop — other user requests can be served
        while upserts are in progress.
        """
        points = []
        for i, (chunk, embedding, meta) in enumerate(zip(chunks, embeddings, metadata)):
            point = PointStruct(
                id=str(uuid4()),
                vector=embedding,
                payload={
                    "text": chunk,
                    "metadata": {
                        "document_id": meta.get("document_id"),
                        "document_name": meta.get("document_name"),
                        "chunk_id": meta.get("chunk_id"),
                    },
                    "document_id": meta.get("document_id"),
                    "document_name": meta.get("document_name"),
                    "chunk_id": meta.get("chunk_id"),
                },
            )
            points.append(point)

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                await self.async_client.upsert(collection_name=collection_name, points=points)
                logger.info(f"Upserted {len(points)} chunks to {collection_name}")
                return
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_retryable = any(
                    x in error_str
                    for x in [
                        "timeout",
                        "timed out",
                        "connection",
                        "temporary",
                        "unavailable",
                        "reset",
                        "broken pipe",
                    ]
                )

                if is_retryable and attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Qdrant upsert failed (attempt {attempt + 1}/{self.MAX_RETRIES}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Error upserting chunks: {str(e)}")
                    raise

        if last_error:
            raise last_error

    def get_vector_store(self, collection_name: str):
        """Get LangChain VectorStore instance (uses sync client for LangChain compat)"""
        return QdrantVectorStore(
            client=self._sync_client,
            collection_name=collection_name,
            embedding=embedding_service.embeddings,
            content_payload_key="text",
            metadata_payload_key="metadata",
        )

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors (fully async — non-blocking)"""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            query_filter = None
            if filter_conditions and "document_ids" in filter_conditions:
                should_conditions = [
                    FieldCondition(key="document_id", match=MatchValue(value=doc_id))
                    for doc_id in filter_conditions["document_ids"]
                ]
                if should_conditions:
                    query_filter = Filter(should=should_conditions)

            try:
                results = (await self.async_client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                    query_filter=query_filter,
                )).points
            except Exception as search_err:
                if "Index required" in str(search_err):
                    logger.warning(
                        f"Index missing for {collection_name}, attempting to fix..."
                    )
                    await self._ensure_indexes(collection_name)
                    results = (await self.async_client.query_points(
                        collection_name=collection_name,
                        query=query_vector,
                        limit=limit,
                        query_filter=query_filter,
                    )).points
                else:
                    raise search_err

            hits = []
            for result in results:
                hits.append(
                    {
                        "id": result.id,
                        "score": result.score,
                        "text": result.payload.get("text", ""),
                        "document_id": result.payload.get("document_id"),
                        "chunk_id": result.payload.get("chunk_id"),
                    }
                )

            logger.info(f"Found {len(hits)} results in {collection_name}")
            return hits

        except Exception as e:
            if "Not found: Collection" in str(e) or "doesn't exist" in str(e):
                logger.warning(
                    f"Collection {collection_name} not found during search. Returning empty."
                )
                return []
            logger.error(f"Error searching: {str(e)}")
            raise

    async def get_initial_chunks(
        self, collection_name: str, document_id: str, limit: int = 10
    ) -> List[str]:
        """Get initial chunks for a document (fully async)"""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id", match=MatchValue(value=document_id)
                    ),
                    FieldCondition(key="chunk_id", range=Range(gte=0, lt=limit)),
                ]
            )

            try:
                points, _ = await self.async_client.scroll(
                    collection_name=collection_name,
                    scroll_filter=query_filter,
                    limit=limit,
                    with_payload=True,
                )
            except Exception as scroll_err:
                if "Index required" in str(scroll_err):
                    logger.warning(
                        f"Index missing for {collection_name} during scroll, attempting to fix..."
                    )
                    await self._ensure_indexes(collection_name)
                    points, _ = await self.async_client.scroll(
                        collection_name=collection_name,
                        scroll_filter=query_filter,
                        limit=limit,
                        with_payload=True,
                    )
                else:
                    raise scroll_err

            sorted_points = sorted(points, key=lambda p: p.payload.get("chunk_id", 0))
            return [p.payload.get("text", "") for p in sorted_points]
        except Exception as e:
            if "Not found: Collection" in str(e) or "doesn't exist" in str(e):
                return []
            logger.error(f"Error getting initial chunks: {str(e)}")
            return []

    async def delete_vectors(self, collection_name: str, document_id: str):
        """Delete vectors for a specific document (fully async)"""
        try:
            from qdrant_client.models import FilterSelector

            await self.async_client.delete(
                collection_name=collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="document_id", match=MatchValue(value=document_id)
                            )
                        ]
                    )
                ),
            )
            logger.info(
                f"Deleted vectors for document {document_id} from {collection_name}"
            )

        except Exception as e:
            logger.error(f"Error deleting vectors: {str(e)}")


qdrant_service = QdrantService()
