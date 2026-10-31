"""Answer assembly: prompt order, excerpts with pages, grounding note, stream protocol, fallbacks."""

import asyncio
import json

import pytest

from services import rag_service as rs
from services.retrieval import Passage, RetrievalResult


def run(c):
    return asyncio.run(c)


def test_prompt_order_and_excerpts():
    passages = [Passage("Leaves make food.", "d1", 4, "Ch 1 › Plants"), Passage("Roots take water.", "d1", None)]
    msgs = rs.build_messages("What do leaves do?", passages, True,
                             [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
                             "Student Name: Asha\n\n=== OUTSIDE THE BOOK ===\nrule")
    system = msgs[0]["content"]
    assert system.startswith(rs.BASE_PROMPT)                       # fixed prefix first (prompt caching)
    assert system.index("Student Name: Asha") < system.index("[Excerpt 1, page 4 — Ch 1 › Plants]")
    assert "[Excerpt 2]\nRoots take water." in system and "loosely related" not in system
    assert [m["role"] for m in msgs[1:]] == ["user", "assistant", "user"] and msgs[-1]["content"] == "What do leaves do?"


def test_weak_matches_are_flagged_and_none_found_is_said():
    weak = rs.build_messages("q", [Passage("x", "d", 1)], False, [], None)[0]["content"]
    assert "loosely related" in weak
    none = rs.build_messages("q", [], False, [], None)[0]["content"]
    assert "(none found for this question)" in none and "(not set yet)" in none


@pytest.fixture
def svc(monkeypatch):
    s = rs.RAGService.__new__(rs.RAGService)

    async def names(ids):
        return {"d1": "Biology.pdf"}

    async def retrieve(project_id, question, history=None, document_ids=None, top_n=6, deep=False):
        return RetrievalResult(query=question, passages=[Passage("Leaves make food.", "d1", 4)], grounded=True,
                               best_similarity=0.8)

    monkeypatch.setattr(s, "_doc_names", names)
    monkeypatch.setattr(rs.retrieval, "retrieve", retrieve)
    return s


def test_stream_sends_text_then_sources_with_pages(svc, monkeypatch):
    seen = {}

    async def stream(messages, **kw):
        seen.update(kw)
        for p in ["Leaves ", "make food [1](1)."]:
            yield p

    monkeypatch.setattr(rs.llm_service, "chat_completion_stream", stream)

    async def collect():
        return [c async for c in svc.get_answer_stream("p", "q", deep=True)]

    out = run(collect())
    assert "".join(out[:-1]) == "Leaves make food [1](1)."
    sources = json.loads(out[-1].split("__SOURCES__:")[1])
    assert sources == [{"doc_id": "d1", "doc_name": "Biology.pdf", "chunk_text": "Leaves make food.", "page": 4}]
    assert seen["deep"] is True


def test_stream_error_is_friendly_and_still_ends_with_sources(svc, monkeypatch):
    async def broken(messages, **kw):
        raise RuntimeError("Error code: 401 - invalid_api_key")
        yield  # pragma: no cover

    monkeypatch.setattr(rs.llm_service, "chat_completion_stream", broken)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(rs.asyncio, "sleep", lambda s: real_sleep(0))

    async def collect():
        return [c async for c in svc.get_answer_stream("p", "q")]

    out = run(collect())
    assert "rejected its API key" in out[0] and out[-1].startswith("\n\n__SOURCES__:")


def test_unindexed_book_answers_from_stored_text(monkeypatch):
    s = rs.RAGService.__new__(rs.RAGService)

    async def retrieve(*a, **k):
        return RetrievalResult(query="q", passages=[], grounded=False, best_similarity=0)

    async def no_chunks(pid):
        return 0

    async def stored(pid, q, limit, docs):
        return [{"text": "From stored text.", "document_id": "d9"}]

    monkeypatch.setattr(rs.retrieval, "retrieve", retrieve)
    monkeypatch.setattr(rs.retrieval, "_project_has_chunks", no_chunks)
    monkeypatch.setattr(rs.retrieval, "_stored_text_passages", stored)
    passages, grounded = run(s._retrieve("p", "q", [], None, False))
    assert passages[0].text == "From stored text." and grounded is True


def test_indexed_but_irrelevant_is_not_grounded(monkeypatch):
    s = rs.RAGService.__new__(rs.RAGService)

    async def retrieve(*a, **k):
        return RetrievalResult(query="q", passages=[], grounded=False, best_similarity=0)

    async def has(pid):
        return 1

    monkeypatch.setattr(rs.retrieval, "retrieve", retrieve)
    monkeypatch.setattr(rs.retrieval, "_project_has_chunks", has)
    assert run(s._retrieve("p", "q", [], None, False)) == ([], False)
