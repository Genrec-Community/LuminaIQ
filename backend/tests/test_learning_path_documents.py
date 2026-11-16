"""Learning path per book: choosing one document shows only its topics, and
rebuilding one book's graph leaves the other books' edges alone."""

import asyncio

from services.knowledge_graph_service import KnowledgeGraph
from tests.fake_supabase import FakeClient

P = "proj-1"


def _service():
    db = FakeClient()
    db.tables["documents"] = [
        {"id": "ss", "project_id": P, "filename": "Social.pdf", "upload_status": "completed",
         "topics": ["World War I", "World War II"], "created_at": "2026-01-01"},
        {"id": "ma", "project_id": P, "filename": "Maths.pdf", "upload_status": "completed",
         "topics": ["Sets", "Relations", "Functions"], "created_at": "2026-01-02"},
    ]
    db.tables["topic_relations"] = [
        {"project_id": P, "from_topic": "World War I", "to_topic": "World War II",
         "relation_type": "prerequisite", "weight": 0.9},
        {"project_id": P, "from_topic": "Sets", "to_topic": "Relations",
         "relation_type": "prerequisite", "weight": 0.9},
    ]
    kg = KnowledgeGraph.__new__(KnowledgeGraph)
    kg.client = db
    return kg, db


def test_path_for_one_document_has_only_its_topics():
    kg, _ = _service()
    path = asyncio.run(kg.generate_learning_path(P, document_ids=["ma"]))
    assert [i["topic"] for i in path] == ["Sets", "Relations", "Functions"]
    assert {i["document_id"] for i in path} == {"ma"}
    assert {i["document"] for i in path} == {"Maths.pdf"}


def test_path_for_all_documents_tags_each_topic_with_its_book():
    kg, _ = _service()
    path = asyncio.run(kg.generate_learning_path(P))
    assert len(path) == 5
    by_doc = {i["topic"]: i["document_id"] for i in path}
    assert by_doc["World War I"] == "ss" and by_doc["Functions"] == "ma"


def test_scoped_rebuild_keeps_other_books_edges(monkeypatch):
    kg, db = _service()

    async def no_llm(project_id, batch, all_topics):
        return [{"project_id": P, "from_topic": "Relations", "to_topic": "Functions",
                 "relation_type": "prerequisite", "weight": 0.8}]

    monkeypatch.setattr(kg, "_generate_relationships_for_batch", no_llm)
    asyncio.run(kg._build_graph_locked(P, ["Sets", "Relations", "Functions"], True, scoped=True))
    pairs = {(e["from_topic"], e["to_topic"]) for e in db.tables["topic_relations"]}
    assert pairs == {("World War I", "World War II"), ("Relations", "Functions")}


def test_full_rebuild_still_replaces_everything(monkeypatch):
    kg, db = _service()

    async def no_llm(project_id, batch, all_topics):
        return []

    monkeypatch.setattr(kg, "_generate_relationships_for_batch", no_llm)
    asyncio.run(kg._build_graph_locked(P, ["Sets", "Relations"], True))
    assert db.tables["topic_relations"] == []
