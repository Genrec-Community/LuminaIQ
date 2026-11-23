"""Notes streamed as they're written: same prompt, same caching and saving as /notes/generate."""

import asyncio

import pytest

from services import notes_service as ns
from services import shared_content


def run(c):
    return asyncio.run(c)


async def collect(gen):
    return [e async for e in gen]


@pytest.fixture
def fakes(monkeypatch):
    state = {"hits": [{"text": "Cells divide by mitosis."}], "cached": None, "stored": [], "saved": [],
             "pieces": ["# Mitosis\n", "Cells ", "divide."], "fallback": "full notes from the retry", "calls": []}

    async def search_passages(project_id, queries, per_query, docs):
        state["calls"].append(("search", list(queries)))
        return state["hits"]

    async def scope_for(project_id, docs):
        return "scope"

    async def lookup(scope, tool, key):
        return state["cached"]

    async def store(scope, tool, key, content, cost):
        state["stored"].append(content)

    async def stream(messages, **kw):
        state["calls"].append(("stream", messages[-1]["content"]))
        for p in state["pieces"]:
            yield p

    async def complete(messages, **kw):
        state["calls"].append(("complete", messages[-1]["content"]))
        return state["fallback"]

    async def save(project_id, user_id, content, note_type, topic=None):
        state["saved"].append(content)
        return {"id": "note-1", "title": note_type}

    import services.retrieval as retrieval
    monkeypatch.setattr(retrieval, "search_passages", search_passages)
    monkeypatch.setattr(shared_content, "scope_for", scope_for)
    monkeypatch.setattr(shared_content, "asset_lookup", lookup)
    monkeypatch.setattr(shared_content, "asset_store", store)
    monkeypatch.setattr(ns.llm_service, "chat_completion_stream", stream)
    monkeypatch.setattr(ns.llm_service, "chat_completion", complete)
    monkeypatch.setattr(ns.notes_service, "save_generated_notes", save)
    return state


def stream_notes(**kw):
    return run(collect(ns.notes_service.generate_notes_stream("p", "Comprehensive Summary", "Mitosis",
                                                             user_id="u", **kw)))


def test_tokens_arrive_then_done_and_the_note_is_saved_and_shared(fakes):
    events = stream_notes()
    assert [e["text"] for e in events if e["type"] == "token"] == fakes["pieces"]
    assert events[-1] == {"type": "done", "note_id": "note-1", "title": "Comprehensive Summary"}
    assert fakes["saved"] == ["# Mitosis\nCells divide."]
    assert fakes["stored"] == ["# Mitosis\nCells divide."]
    # the book's text went into the prompt
    assert "Cells divide by mitosis." in [c for c in fakes["calls"] if c[0] == "stream"][0][1]


def test_shared_book_notes_come_from_the_cache_without_a_model_call(fakes):
    fakes["cached"] = "cached notes"
    events = stream_notes()
    assert events[0] == {"type": "token", "text": "cached notes"}
    assert events[-1]["type"] == "done"
    assert not [c for c in fakes["calls"] if c[0] in ("stream", "complete")]
    assert fakes["stored"] == [] and fakes["saved"] == ["cached notes"]


def test_empty_stream_falls_back_to_the_full_call(fakes):
    fakes["pieces"] = []
    events = stream_notes()
    assert {"type": "replace", "text": "full notes from the retry"} in events
    assert fakes["saved"] == ["full notes from the retry"]


def test_no_passages_gives_the_no_content_message_and_saves_nothing(fakes):
    fakes["hits"] = []
    events = stream_notes()
    assert events == [{"type": "token", "text": ns.NO_CONTENT}, {"type": "done"}]
    assert fakes["saved"] == [] and fakes["stored"] == []


def test_a_model_failure_becomes_an_error_event(fakes, monkeypatch):
    async def broken(messages, **kw):
        raise RuntimeError("provider down")
        yield  # pragma: no cover

    monkeypatch.setattr(ns.llm_service, "chat_completion_stream", broken)
    events = stream_notes()
    assert events[-1]["type"] == "error" and fakes["saved"] == []


def test_a_book_keeps_more_than_one_saved_note(pg_client):
    """0012: the old one-note-per-book constraint made every note after the first fail to save."""
    import uuid
    user = str(uuid.uuid4())
    proj = pg_client.table("projects").insert({"user_id": user, "name": "Bio"}).execute().data[0]["id"]
    for title in ("Summary", "Glossary"):
        pg_client.table("notes").insert({"project_id": proj, "user_id": user, "content": "x", "title": title}).execute()
    rows = pg_client.table("notes").select("title").eq("project_id", proj).execute().data
    assert sorted(r["title"] for r in rows) == ["Glossary", "Summary"]
