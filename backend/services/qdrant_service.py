from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
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
    Qdrant vector database service with retry logic for reliability.

    Features:
    - Automatic retry with exponential backoff for transient failures
    - Longer timeout for large batch operations
    - Graceful handling of timeouts and connection errors
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds

    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=120,  # Increased from 60 for large batches
        )

    async def create_collection(self, collection_name: str, vector_size: int = 1024):
        """Create a new collection and ensure indexes exist"""
        try:
            collections = self.client.get_collections().collections
            exists = any(col.name == collection_name for col in collections)

            if not exists:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Created collection: {collection_name}")
            else:
                logger.info(f"Collection already exists: {collection_name}")

            # Always ensure indexes exist (fix for existing collections missing indexes)
            await self._ensure_indexes(collection_name)

        except Exception as e:
            logger.error(f"Error creating collection: {str(e)}")
            raise

    async def _ensure_indexes(self, collection_name: str):
        """Create payload indexes if they don't exist"""
        try:
            # Document ID index (Keyword)
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="document_id",
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
            )

            # Chunk ID index (Integer)
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="chunk_id",
                field_schema=PayloadSchemaType.INTEGER,
                wait=True,
            )
            logger.info(f"Verified/Created indexes for {collection_name}")
        except Exception as e:
            # Ignore if already exists (API might raise error)
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
        Insert chunks into collection with automatic retry on failure.

        Handles transient errors like timeouts and connection issues
        with exponential backoff retry.
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
                self.client.upsert(collection_name=collection_name, points=points)
                logger.info(f"Upserted {len(points)} chunks to {collection_name}")
                return
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if it's a retryable error
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
                    delay = self.RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Qdrant upsert failed (attempt {attempt + 1}/{self.MAX_RETRIES}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Non-retryable or last attempt
                    logger.error(f"Error upserting chunks: {str(e)}")
                    raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error

    def get_vector_store(self, collection_name: str):
        """Get LangChain VectorStore instance with proper metadata mapping"""
        return QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embedding=embedding_service.embeddings,
            content_payload_key="text",  # Our payload uses 'text' not 'page_content'
            metadata_payload_key="metadata",  # We'll store metadata nested now
        )

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors"""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            query_filter = None
            if filter_conditions and "document_ids" in filter_conditions:
                # Create OR condition if multiple document IDs, or single check
                # Qdrant 'match' value takes a single value. To match multiple, we use 'should' (OR) logic
                # or 'match' with 'any' keyword if supported, but let's stick to standard Filter structure.

                should_conditions = [
                    FieldCondition(key="document_id", match=MatchValue(value=doc_id))
                    for doc_id in filter_conditions["document_ids"]
                ]

                if should_conditions:
                    query_filter = Filter(should=should_conditions)

            try:
                # Use client.query_points which works for dense vector search in newer Qdrant clients
                results = self.client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                    query_filter=query_filter,
                ).points
            except Exception as search_err:
                # Auto-heal missing index error
                if "Index required" in str(search_err):
                    logger.warning(
                        f"Index missing for {collection_name}, attempting to fix..."
                    )
                    await self._ensure_indexes(collection_name)
                    # Retry search
                    results = self.client.query_points(
                        collection_name=collection_name,
                        query=query_vector,
                        limit=limit,
                        query_filter=query_filter,
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
        # Re-implement using client scroll as before
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
                points, _ = self.client.scroll(
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
                    points, _ = self.client.scroll(
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
        """Delete vectors for a specific document"""
        try:
            from qdrant_client.models import FilterSelector

            self.client.delete(
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
            # Don't raise, allowing deletion flow to continue even if vector deletion fails (e.g. if collection missing)


qdrant_service = QdrantService()
