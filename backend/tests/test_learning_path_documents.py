"""Learning path per book: picking a book only filters the one optimal path.
Its topics and their order are exactly those of the all-books path."""

import asyncio

from services.knowledge_graph_service import KnowledgeGraph
from tests.fake_supabase import FakeClient

P = "proj-1"


def _service():
    db = FakeClient()
    db.tables["documents"] = [
        {"id": "ss", "project_id": P, "filename": "Social.pdf", "upload_status": "completed",
         "topics": ["World War I", "World War II", "Statistics of war"], "created_at": "2026-01-01"},
        {"id": "ma", "project_id": P, "filename": "Maths.pdf", "upload_status": "completed",
         "topics": ["Sets", "Relations", "Functions", "Averages"], "created_at": "2026-01-02"},
    ]
    edge = lambda a, b, w=0.9: {"project_id": P, "from_topic": a, "to_topic": b,
                               "relation_type": "prerequisite", "weight": w}
    db.tables["topic_relations"] = [
        edge("World War I", "World War II"),
        edge("Sets", "Relations"),
        edge("Relations", "Functions"),
        # A cross-book edge: Averages must come before the Social topic that uses it.
        edge("Averages", "Statistics of war"),
    ]
    kg = KnowledgeGraph.__new__(KnowledgeGraph)
    kg.client = db
    return kg


def test_one_book_is_the_all_books_path_filtered_in_the_same_order():
    kg = _service()
    full = asyncio.run(kg.generate_learning_path(P))
    for doc in ("ma", "ss"):
        only = asyncio.run(kg.generate_learning_path(P, document_ids=[doc]))
        assert [i["topic"] for i in only] == [i["topic"] for i in full if i["document_id"] == doc]
        assert {i["document_id"] for i in only} == {doc}


def test_all_books_path_tags_each_topic_with_its_book():
    kg = _service()
    path = asyncio.run(kg.generate_learning_path(P))
    assert len(path) == 7
    by_doc = {i["topic"]: (i["document_id"], i["document"]) for i in path}
    assert by_doc["World War I"] == ("ss", "Social.pdf")
    assert by_doc["Functions"] == ("ma", "Maths.pdf")


def test_unknown_document_gives_an_empty_path():
    kg = _service()
    assert asyncio.run(kg.generate_learning_path(P, document_ids=["nope"])) == []
