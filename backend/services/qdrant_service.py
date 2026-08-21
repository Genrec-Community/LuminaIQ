from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    HasIdCondition,
    Range,
    PayloadSchemaType,
)
from config.settings import settings
from typing import List, Dict, Any, Optional
from uuid import uuid4
from utils.logger import logger
from utils.embedding_scheduler import embedding_point_id


class QdrantService:
    """
    Qdrant vector database service with ASYNC client for non-blocking operations.

    Features:
    - AsyncQdrantClient for all direct operations (non-blocking event loop)
    - Sync client retained only for LangChain VectorStore compatibility
    - Embedding writes are retried by EmbeddingBatchScheduler
    - Longer timeout for large batch operations
    - clone_document_vectors() for instant book imports (no re-embedding)
    """

    # Connection pool and timeout settings for multi-user load
    ASYNC_TIMEOUT = 120  # Longer timeout for batch embedding upserts
    GRPC_OPTIONS = {
        "grpc.max_send_message_length": 64 * 1024 * 1024,  # 64MB
        "grpc.max_receive_message_length": 64 * 1024 * 1024,  # 64MB
    }

    def __init__(self):
        # Async client for all direct operations — does NOT block the event loop
        # Initialize async client using default REST or whatever qdrant_client defaults to
        kwargs = {
            "url": settings.QDRANT_URL,
            "api_key": settings.QDRANT_API_KEY,
            "timeout": self.ASYNC_TIMEOUT,
        }

        self.async_client = AsyncQdrantClient(**kwargs)
        logger.info(
            f"[QdrantService] Initialized with AsyncQdrantClient | "
            f"async_timeout={self.ASYNC_TIMEOUT}s"
        )

    async def create_collection(
        self, collection_name: str, vector_size: int = settings.EMBEDDING_DIMENSION
    ):
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
        if not (len(chunks) == len(embeddings) == len(metadata)):
            raise ValueError(
                "Chunk, embedding, and metadata counts must match before Qdrant upsert"
            )

        points = []
        for chunk, embedding, meta in zip(chunks, embeddings, metadata):
            document_id = meta.get("document_id")
            chunk_id = meta.get("chunk_id")
            point_id = (
                embedding_point_id(collection_name, document_id, chunk_id)
                if document_id is not None and chunk_id is not None
                else str(uuid4())
            )
            point = PointStruct(
                id=point_id,
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

        await self.async_client.upsert(collection_name=collection_name, points=points)
        logger.info(f"Upserted {len(points)} chunks to {collection_name}")

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
                results = (
                    await self.async_client.query_points(
                        collection_name=collection_name,
                        query=query_vector,
                        limit=limit,
                        query_filter=query_filter,
                    )
                ).points
            except Exception as search_err:
                if "Index required" in str(search_err):
                    logger.warning(
                        f"Index missing for {collection_name}, attempting to fix..."
                    )
                    await self._ensure_indexes(collection_name)
                    results = (
                        await self.async_client.query_points(
                            collection_name=collection_name,
                            query=query_vector,
                            limit=limit,
                            query_filter=query_filter,
                        )
                    ).points
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
                        "document_name": result.payload.get("document_name"),
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

    async def delete_vectors(
        self,
        collection_name: str,
        document_id: str,
        raise_on_error: bool = False,
    ):
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
            if raise_on_error:
                raise

    async def delete_vectors_except(
        self,
        collection_name: str,
        document_id: str,
        keep_ids: List[str],
    ):
        """Remove legacy and stale points after a complete replacement succeeds."""
        from qdrant_client.models import FilterSelector

        await self.async_client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id", match=MatchValue(value=document_id)
                        )
                    ],
                    must_not=[HasIdCondition(has_id=keep_ids)],
                )
            ),
        )
        logger.info(
            f"Removed legacy/stale vectors for document {document_id} "
            f"from {collection_name}"
        )

    async def clone_document_vectors(
        self,
        source_collection: str,
        target_collection: str,
        source_document_id: str,
        target_document_id: str,
        target_document_name: str,
        batch_size: int = 100,
    ) -> int:
        """
        Clone all Qdrant vectors for a document from one collection to another.

        Used by book imports to skip re-embedding: vectors are copied from the
        original uploader's project collection into the importer's project collection,
        with document_id / document_name payload rewritten to the new document's IDs.

        This reduces book import time from ~2-5 minutes to ~2-5 seconds.

        Returns:
            Number of vectors cloned (0 if source collection/document is missing).
        """
        scroll_filter = Filter(
            must=[
                FieldCondition(
                    key="document_id", match=MatchValue(value=source_document_id)
                )
            ]
        )

        total_cloned = 0
        offset = None  # Qdrant scroll pagination token

        while True:
            try:
                points, next_offset = await self.async_client.scroll(
                    collection_name=source_collection,
                    scroll_filter=scroll_filter,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )
            except Exception as e:
                if "Not found: Collection" in str(e) or "doesn't exist" in str(e):
                    logger.warning(
                        f"[VectorClone] Source collection {source_collection} not found "
                        f"— falling back to re-embedding"
                    )
                    return 0
                raise

            if not points:
                break

            cloned_points = []
            for p in points:
                new_payload = dict(p.payload)
                new_payload["document_id"] = target_document_id
                new_payload["document_name"] = target_document_name
                # Also rewrite nested metadata dict if present
                if "metadata" in new_payload and isinstance(
                    new_payload["metadata"], dict
                ):
                    new_payload["metadata"] = dict(new_payload["metadata"])
                    new_payload["metadata"]["document_id"] = target_document_id
                    new_payload["metadata"]["document_name"] = target_document_name

                cloned_points.append(
                    PointStruct(
                        id=str(
                            uuid4()
                        ),  # New UUID — avoids ID collisions across projects
                        vector=p.vector,
                        payload=new_payload,
                    )
                )

            await self.async_client.upsert(
                collection_name=target_collection,
                points=cloned_points,
            )
            total_cloned += len(cloned_points)
            logger.info(
                f"[VectorClone] {total_cloned} vectors cloned "
                f"({source_collection}/{source_document_id} -> "
                f"{target_collection}/{target_document_id})"
            )

            if next_offset is None:
                break
            offset = next_offset

        logger.info(
            f"[VectorClone] Complete: {total_cloned} vectors in "
            f"{target_collection}/{target_document_id}"
        )
        return total_cloned


qdrant_service = QdrantService()
