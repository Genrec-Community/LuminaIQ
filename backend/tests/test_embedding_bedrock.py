"""Bedrock embeddings: Titan (one text per call) and Cohere (batched), with the configured dimension."""
import asyncio

import pytest

from config.settings import settings
from services.embedding_service import EmbeddingService


@pytest.fixture
def bedrock(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "bedrock")
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 4)
    svc = EmbeddingService()
    calls = []

    def fake_invoke(body):
        calls.append(body)
        if "texts" in body:
            return {"embeddings": {"float": [[float(len(t))] * 4 for t in body["texts"]]}}
        return {"embedding": [float(len(body["inputText"]))] * 4, "inputTextTokenCount": 3}

    monkeypatch.setattr(svc, "_bedrock_invoke", fake_invoke)
    return svc, calls


def test_titan_one_call_per_text_in_order(bedrock, monkeypatch):
    svc, calls = bedrock
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
    out = asyncio.run(svc.generate_embeddings(["a", "bbb", ""]))
    assert [v[0] for v in out] == [1.0, 3.0, 1.0]       # empty text becomes one space
    assert len(calls) == 3 and all(c["dimensions"] == 4 for c in calls)


def test_cohere_batches(bedrock, monkeypatch):
    svc, calls = bedrock
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "global.cohere.embed-v4:0")
    out = asyncio.run(svc.generate_embeddings(["xy", "z"]))
    assert [v[0] for v in out] == [2.0, 1.0]
    assert len(calls) == 1 and calls[0]["output_dimension"] == 4


def test_wrong_dimension_is_an_error(bedrock, monkeypatch):
    svc, _ = bedrock
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 8)
    with pytest.raises(ValueError):
        asyncio.run(svc.generate_embeddings(["a"]))
