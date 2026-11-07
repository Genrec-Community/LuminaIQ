"""Pre-filling a class book's pools (PREGENERATE_SHARED)."""

import asyncio
from types import SimpleNamespace

from services import jobs, shared_content


def test_fills_quiz_and_flashcard_pools_per_topic(monkeypatch):
    calls = []

    async def scope_for(project_id, docs):
        return shared_content.Scope(roots=["root"], by_doc={"d": "root"})

    async def draw(user_id, scope, tool, topic, level, n, make, variant=""):
        calls.append((user_id, tool, topic, level, n))
        return [], 3

    class Q:
        def select(self, *a): return self
        def eq(self, *a): return self
        def limit(self, *a): return self
        def execute(self): return SimpleNamespace(data=[{"topics": ["Cells", "Tissues"]}])

    monkeypatch.setattr(shared_content, "scope_for", scope_for)
    monkeypatch.setattr(shared_content, "draw", draw)
    monkeypatch.setattr(jobs, "get_supabase_client", lambda: SimpleNamespace(table=lambda name: Q()))
    out = asyncio.run(jobs.handle_pregenerate_shared(
        {"payload": {"project_id": "p", "document_id": "d", "level": "school"}}))
    assert out == {"topics": 2, "generated": 12}
    assert {(c[1], c[2]) for c in calls} == {("quiz", "Cells"), ("flashcards", "Cells"),
                                            ("quiz", "Tissues"), ("flashcards", "Tissues")}
    assert all(c[0] is None and c[3] == "school" for c in calls)


def test_personal_books_are_skipped(monkeypatch):
    async def scope_for(project_id, docs):
        return None
    monkeypatch.setattr(shared_content, "scope_for", scope_for)
    out = asyncio.run(jobs.handle_pregenerate_shared({"payload": {"project_id": "p", "document_id": "d"}}))
    assert "skipped" in out
