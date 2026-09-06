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
    - clone_document_vectors() for instant book imports (no re-embedding)
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds

    # Connection pool and timeout settings for multi-user load
    ASYNC_TIMEOUT = 120        # Longer timeout for batch embedding upserts
    SYNC_TIMEOUT = 30          # Shorter timeout for search queries (user-facing)
    GRPC_OPTIONS = {
        "grpc.max_send_message_length": 64 * 1024 * 1024,   # 64MB
        "grpc.max_receive_message_length": 64 * 1024 * 1024, # 64MB
    }

    def __init__(self):
        self._async_client_instance = None
        self._sync_client_instance = None
        self._inference_client_instance = None

    @property
    def inference_client(self):
        """
        Qdrant Cloud Inference client (server-side embeddings).

        Opt-in via settings.QDRANT_CLOUD_INFERENCE. Embeddings are generated
        inside Qdrant Cloud using settings.QDRANT_EMBED_MODEL — no local
        model, no Azure/OpenAI key. Per Qdrant docs, collection vector size
        must match the model output (384 for all-minilm-l6-v2).
        """
        if self._inference_client_instance is not None:
            return self._inference_client_instance
        self._inference_client_instance = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=self.ASYNC_TIMEOUT,
            cloud_inference=True,
        )
        logger.info(
            "[QdrantService] Initialized Cloud Inference client "
            f"| model={settings.QDRANT_EMBED_MODEL}"
        )
        return self._inference_client_instance

    @property
    def async_client(self):
        if self._async_client_instance is not None:
            return self._async_client_instance
            
        kwargs = {
            "url": settings.QDRANT_URL,
            "api_key": settings.QDRANT_API_KEY,
            "timeout": self.ASYNC_TIMEOUT,
        }

        self._async_client_instance = AsyncQdrantClient(**kwargs)
        logger.info(
            f"[QdrantService] Initialized with AsyncQdrantClient | "
            f"async_timeout={self.ASYNC_TIMEOUT}s"
        )
        return self._async_client_instance
        
    @property
    def _sync_client(self):
        if self._sync_client_instance is not None:
            return self._sync_client_instance
            
        self._sync_client_instance = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=self.SYNC_TIMEOUT,
        )
        logger.info(f"[QdrantService] Initialized Sync QdrantClient | sync_timeout={self.SYNC_TIMEOUT}s")
        return self._sync_client_instance

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
                logger.info(f"Created collection: {collection_name} (dim={vector_size})")
            else:
                # Guard: refuse to mix embedding dimensions in one collection.
                # Happens when switching models (e.g. Azure 1536-dim ->
                # Inference 384-dim). Recreate the collection to re-embed.
                try:
                    info = await self.async_client.get_collection(collection_name)
                    params = info.config.params.vectors
                    existing_size = getattr(params, "size", None)
                    if existing_size is not None and existing_size != vector_size:
                        raise RuntimeError(
                            f"Collection '{collection_name}' has dim={existing_size} "
                            f"but current embedding model produces dim={vector_size}. "
                            f"Delete/recreate the collection to re-embed with the new model."
                        )
                except RuntimeError:
                    raise
                except Exception:
                    pass  # best-effort check; upsert will surface real errors
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

    async def upsert_texts(
        self,
        collection_name: str,
        chunks: List[str],
        metadata: List[Dict[str, Any]],
    ):
        """
        Upsert raw texts using Qdrant Cloud Inference (server-side embeddings).

        No client-side vectors needed — Qdrant generates them with
        settings.QDRANT_EMBED_MODEL. Requires QDRANT_CLOUD_INFERENCE=true
        and a reachable Qdrant Cloud cluster. Collection dim must match the
        model output (384 for all-minilm-l6-v2).
        """
        from qdrant_client.models import Document

        # Payload indexes are collection-level: ensure filtered search
        # (document_id/chunk_id) works on inference-written collections too.
        await self._ensure_indexes(collection_name)

        model = settings.QDRANT_EMBED_MODEL
        points = []
        for chunk, meta in zip(chunks, metadata):
            point = PointStruct(
                id=str(uuid4()),
                vector=Document(text=chunk, model=model),
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

        await self.inference_client.upsert(
            collection_name=collection_name, points=points
        )
        logger.info(
            f"[CloudInference] Upserted {len(points)} chunks to {collection_name}"
        )

    async def search_by_text(
        self,
        collection_name: str,
        query_text: str,
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search using Qdrant Cloud Inference (raw query text, server-side
        embedding). Same payload shape as search().
        """
        from qdrant_client.models import Document

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
                await self.inference_client.query_points(
                    collection_name=collection_name,
                    query=Document(
                        text=query_text, model=settings.QDRANT_EMBED_MODEL
                    ),
                    limit=limit,
                    query_filter=query_filter,
                )
            ).points
        except Exception as e:
            if "Not found: Collection" in str(e) or "doesn't exist" in str(e):
                logger.warning(
                    f"Collection {collection_name} not found during search. Returning empty."
                )
                return []
            logger.error(f"Error searching (cloud inference): {str(e)}")
            raise

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
        logger.info(f"[CloudInference] Found {len(hits)} results in {collection_name}")
        return hits

    async def search_auto(
        self,
        collection_name: str,
        query_text: str,
        limit: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Provider-aware search (single entry point for all callers).

        - QDRANT_CLOUD_INFERENCE=true → server-side embeddings
          (search_by_text, no local model — Render-friendly).
        - Otherwise → client-side embedding API (Azure/OpenAI fallback).

        IMPORTANT: a collection must be written and read with the SAME
        model — different models may share 384 dims but live in different
        vector spaces. Recreate collections when switching providers.
        """
        if settings.QDRANT_CLOUD_INFERENCE:
            return await self.search_by_text(
                collection_name=collection_name,
                query_text=query_text,
                limit=limit,
                filter_conditions=filter_conditions,
            )
        from services.embedding_service import embedding_service

        query_vector = await embedding_service.generate_embedding(query_text)
        return await self.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            filter_conditions=filter_conditions,
        )

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
                if "metadata" in new_payload and isinstance(new_payload["metadata"], dict):
                    new_payload["metadata"] = dict(new_payload["metadata"])
                    new_payload["metadata"]["document_id"] = target_document_id
                    new_payload["metadata"]["document_name"] = target_document_name

                cloned_points.append(
                    PointStruct(
                        id=str(uuid4()),   # New UUID — avoids ID collisions across projects
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
