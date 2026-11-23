"""EMBEDDING_PROVIDER=none: books still index (no vectors) and nothing calls an embedding API."""
import asyncio

import pytest

from config.settings import settings
from services import indexing, vector_store
from services.embedding_service import EmbeddingsOff, embedding_service


def test_indexing_without_embeddings(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "none")
    stored = {}

    async def existing(hashes):
        list(hashes)
        return {}

    async def replace(project_id, document_id, chunks, vectors):
        stored["vectors"] = vectors
        return len(chunks)

    async def boom(*a, **k):
        raise AssertionError("embedding API called")

    monkeypatch.setattr(vector_store, "existing_vectors", existing)
    monkeypatch.setattr(vector_store, "replace_document_chunks", replace)
    monkeypatch.setattr(embedding_service, "_embed_batch", boom)
    n = asyncio.run(indexing.index_text("p", "d", "Book", "# Cells\n\nCells are the units of life. " * 40))
    assert n > 0 and stored["vectors"] and all(v is None for v in stored["vectors"])


def test_query_embedding_raises_so_search_uses_keywords(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "none")
    with pytest.raises(EmbeddingsOff):
        asyncio.run(embedding_service.generate_embeddings(["x"]))
