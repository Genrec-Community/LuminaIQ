"""The memory API, app state, and memory reaching chat and quizzes (real Postgres)."""

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import access
from api.deps import get_current_user
from db.client import SupabaseClient


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return self.pg.table(name)

    def rpc(self, name, params=None):
        return self.pg.rpc(name, params)


def run(c):
    return asyncio.run(c)


@pytest.fixture
def world(pg_client, monkeypatch):
    app_client = AppOnPg(pg_client)
    monkeypatch.setattr(SupabaseClient, "_instance", app_client)
    # Services that kept a client from import time talk to this test database too
    from services.mcq_service import mcq_service
    from services.user_data_service import user_data
    monkeypatch.setattr(user_data, "client", app_client)
    monkeypatch.setattr(mcq_service, "client", app_client)
    access.clear_cache()
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    pa = pg_client.table("projects").insert({"user_id": a, "name": "Physics"}).execute().data[0]["id"]
    pb = pg_client.table("projects").insert({"user_id": b, "name": "B"}).execute().data[0]["id"]
    for u, level in ((a, "higher_secondary"), (b, "school")):
        pg_client.table("user_settings").insert({"user_id": u, "settings": {"studyLevel": level}}).execute()
    return {"pg": pg_client, "a": a, "b": b, "pa": pa, "pb": pb}


def client_for(user_id):
    from main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id, "email": "x@x.com", "managed": False}
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    from main import app
    app.dependency_overrides.clear()


def test_view_add_edit_delete_and_clear(world):
    c = client_for(world["a"])
    body = c.get("/api/v1/memory").json()
    assert body["memories"] == [] and body["settings"] == {"across_books": True, "auto": True}
    assert body["auto_memory_available"] is True
    m = c.post("/api/v1/memory", json={"content": "Exam on 12 March", "kind": "goal"}).json()
    assert c.patch(f"/api/v1/memory/{m['id']}", json={"content": "Exam on 14 March"}).json()["content"] == "Exam on 14 March"
    assert [x["content"] for x in c.get("/api/v1/memory").json()["memories"]] == ["Exam on 14 March"]
    assert c.delete(f"/api/v1/memory/{m['id']}").json() == {"deleted": True}
    assert c.delete("/api/v1/memory/not-a-uuid").status_code == 404
    c.post("/api/v1/memory", json={"content": "Likes cricket"})
    assert c.delete("/api/v1/memory").json()["memories"] == 1
    assert c.get("/api/v1/memory").json()["memories"] == []


def test_one_student_cannot_touch_anothers_memory(world):
    m = client_for(world["a"]).post("/api/v1/memory", json={"content": "secret goal"}).json()
    other = client_for(world["b"])
    assert other.get("/api/v1/memory").json()["memories"] == []
    assert other.patch(f"/api/v1/memory/{m['id']}", json={"content": "hacked"}).status_code == 404
    assert other.delete(f"/api/v1/memory/{m['id']}").status_code == 404
    assert other.delete(f"/api/v1/memory/summaries/{world['pa']}").status_code == 404
    assert world["pg"].fetch("SELECT content FROM user_memories WHERE id = %s", (m["id"],))[0]["content"] == "secret goal"


def test_school_students_see_automatic_memory_is_off(world):
    assert client_for(world["b"]).get("/api/v1/memory").json()["auto_memory_available"] is False


def test_memory_settings_are_saved(world):
    c = client_for(world["a"])
    assert c.put("/api/v1/memory/settings", json={"across_books": False}).json() == {"across_books": False, "auto": True}
    assert world["pg"].fetch("SELECT settings FROM user_settings WHERE user_id = %s",
                             (world["a"],))[0]["settings"]["memoryAcrossBooks"] is False


def test_app_state_merges_and_removes_keys(world):
    c = client_for(world["a"])
    assert c.get("/api/v1/user-data/state").json()["state"] == {}
    c.patch("/api/v1/user-data/state", json={"state": {"lastProject": world["pa"], "lastView": "quiz"}})
    c.patch("/api/v1/user-data/state", json={"state": {"lastView": "chat", "quiz:x": {"index": 3}}})
    assert c.get("/api/v1/user-data/state").json()["state"] == {
        "lastProject": world["pa"], "lastView": "chat", "quiz:x": {"index": 3}}
    c.patch("/api/v1/user-data/state", json={"state": {"quiz:x": None}})
    assert "quiz:x" not in c.get("/api/v1/user-data/state").json()["state"]
    assert c.patch("/api/v1/user-data/state", json={"state": {"big": "x" * 70000}}).status_code == 413
    assert client_for(world["b"]).get("/api/v1/user-data/state").json()["state"] == {}


def test_chat_prompt_carries_summary_weak_topics_and_memories(world, monkeypatch):
    from api.v1.endpoints import chat
    pg, a, pa = world["pg"], world["a"], world["pa"]
    now = datetime.now(timezone.utc).isoformat()
    pg.table("topic_mastery").insert({"user_id": a, "project_id": pa, "topic": "Kinematics", "p_known": 0.2,
                                      "attempts": 5, "correct": 1, "stability_days": 30, "last_seen": now,
                                      "updated_at": now}).execute()
    pg.table("user_memories").insert({"user_id": a, "kind": "interest", "content": "Likes cricket examples"}).execute()
    pg.table("chat_summaries").insert({"project_id": pa, "user_id": a, "summary": "Earlier they asked about friction.",
                                       "covered_until": "2026-01-01T00:00:00+00:00", "covered_count": 40}).execute()
    pg.table("chat_messages").insert({"project_id": pa, "role": "user", "content": "recent turn"}).execute()

    async def ctx(user_id):
        return "Student name: Asha"
    monkeypatch.setattr(chat, "get_user_context_string", ctx)
    req = SimpleNamespace(project_id=pa, message="explain velocity with an example", hints=None,
                          system_prompt=None, selected_documents=None, deep=False)

    async def go():
        history, user_context, save_task, eff = await chat._prepare_chat(req, a)
        await save_task
        return history, user_context
    history, user_context = run(go())
    assert "Earlier they asked about friction." in user_context
    assert "Finding hard: Kinematics" in user_context and "Likes cricket examples" in user_context
    assert user_context.index("Student name") < user_context.index("WHAT YOU KNOW") < user_context.index("HOW TO ANSWER")
    assert history[-1]["content"] == "recent turn"


def test_quiz_without_topic_targets_the_weakest_and_wrong_answers_are_remembered(world, monkeypatch):
    from services import shared_content
    from services.mcq_service import mcq_service
    pg, a, pa = world["pg"], world["a"], world["pa"]
    now = datetime.now(timezone.utc).isoformat()
    for topic, p in (("Optics", 0.9), ("Kinematics", 0.15), ("Waves", 0.4)):
        pg.table("topic_mastery").insert({"user_id": a, "project_id": pa, "topic": topic, "p_known": p, "attempts": 5,
                                          "correct": 2, "stability_days": 30, "last_seen": now,
                                          "updated_at": now}).execute()
    asked = []

    async def make(project_id, topic, n, docs, difficulty, level):
        asked.append(topic)
        return [{"question": "Is speed a vector?", "options": [{"option": "A", "text": "No"}, {"option": "B", "text": "Yes"}],
                 "correct_answer": "A", "explanation": "Speed has no direction."}]

    async def draw(user_id, scope, tool, topic, level, n, make_fn, variant=""):
        return await make_fn(n), n
    monkeypatch.setattr(mcq_service, "make_questions", make)
    monkeypatch.setattr(shared_content, "draw", draw)
    queued = []

    async def enqueue(kind, payload, **kw):
        queued.append(kind)
    monkeypatch.setattr("services.jobs.enqueue", enqueue)

    test = run(mcq_service.generate_mcq(pa, None, 1, None, "medium", user_id=a, level="higher_secondary"))
    assert asked == ["Kinematics"] and test["topic"] == "Kinematics"
    run(mcq_service.submit_test(test["test_id"], {0: "B"}, user_id=a))
    rows = pg.fetch("SELECT topic, wrong_answer, correct_answer FROM learner_mistakes WHERE user_id = %s", (a,))
    assert rows == [{"topic": "Kinematics", "wrong_answer": "Yes", "correct_answer": "No"}] and queued == ["tag_mistakes"]
    run(mcq_service.submit_test(test["test_id"], {0: "A"}, user_id=a))
    assert pg.fetch("SELECT fixed_at FROM learner_mistakes WHERE user_id = %s", (a,))[0]["fixed_at"] is not None


def test_teachers_have_no_route_to_chats_or_memory():
    """Owner decision 13: teachers see progress, never chats or memory notes."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    teacher_code = (root / "services/institution_service.py").read_text() + \
        (root / "api/v1/endpoints/institutions.py").read_text()
    for table in ("chat_messages", "chat_summaries", "user_memories", "app_state"):
        assert table not in teacher_code
