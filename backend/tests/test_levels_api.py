"""Level and tool endpoints: learners, platform admins and institution admins."""

import uuid

import pytest
from fastapi.testclient import TestClient

from api.deps import get_current_user
from db.client import SupabaseClient
from tests.test_levels import AppOnPg, enrol, make_class, set_level

USER = {"id": str(uuid.uuid4()), "email": "kid@example.com", "managed": False}


@pytest.fixture
def env(pg_client, monkeypatch):
    with pg_client.pool.connection() as conn:
        conn.execute("TRUNCATE level_tool_policies, level_settings, class_tool_policies, user_settings, "
                     "user_roles, institutions, institution_members, institution_classes, class_members CASCADE")
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(pg_client))
    from utils import cache, rate_limit
    monkeypatch.setattr(cache, "_cache", cache.Cache(cache.MemoryBackend()))
    monkeypatch.setattr(rate_limit, "_counter", rate_limit.MemoryCounter())
    from services.institution_service import institutions
    monkeypatch.setattr(institutions, "client", AppOnPg(pg_client), raising=False)
    if hasattr(institutions, "_members"):
        institutions._members.clear()
    from main import app
    user = dict(USER, id=str(uuid.uuid4()))
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app, raise_server_exceptions=False), pg_client, user
    app.dependency_overrides.clear()


def test_catalog_and_me(env):
    client, pg, user = env
    cat = client.get("/api/v1/levels/catalog").json()
    assert [l["key"] for l in cat["levels"]][0] == "school" and any(t["key"] == "quiz" for t in cat["tools"])
    me = client.get("/api/v1/levels/me").json()
    assert me["needs_level"] is True
    me = client.put("/api/v1/levels/me", json={"level": "school"}).json()
    assert me["level"] == "school" and me["level_label"] == "Class 5–10" and "deep" not in me["tools"]
    assert client.put("/api/v1/levels/me", json={"level": "toddler"}).status_code == 400


def test_locked_student_cannot_change_level(env):
    client, pg, user = env
    inst, cls = make_class(pg, level="school")
    enrol(pg, inst, cls, user["id"])
    res = client.put("/api/v1/levels/me", json={"level": "research"})
    assert res.status_code == 403


def test_disabled_tool_returns_403(env):
    client, pg, user = env
    set_level(pg, user["id"], "school")
    pg.table("level_tool_policies").insert({"level": "school", "tool": "quiz", "enabled": False}).execute()
    res = client.post("/api/v1/mcq/generate", json={"project_id": str(uuid.uuid4()), "topic": "x"})
    # the ownership guard answers first for a project that isn't theirs; use their own project
    project = pg.table("projects").insert({"user_id": user["id"], "name": "B"}).execute().data[0]
    res = client.post("/api/v1/mcq/generate", json={"project_id": project["id"], "topic": "x", "num_questions": 3})
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "tool_disabled"


def test_deep_mode_needs_deep_tool(env):
    client, pg, user = env
    set_level(pg, user["id"], "school")   # school: deep is off by default
    project = pg.table("projects").insert({"user_id": user["id"], "name": "B"}).execute().data[0]
    res = client.post("/api/v1/chat/message", json={"project_id": project["id"], "message": "hi", "deep": True})
    assert res.status_code == 403 and res.json()["detail"]["tool"] == "deep"


def test_platform_admin_updates_level(env, monkeypatch):
    client, pg, user = env
    assert client.get("/api/v1/platform/levels").status_code == 403
    from config.settings import settings
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", user["email"])
    levels_out = client.get("/api/v1/platform/levels").json()
    school = next(l for l in levels_out["levels"] if l["key"] == "school")
    assert "deep" not in school["tools"]
    res = client.put("/api/v1/platform/levels/school", json={"tools": {"deep": True}, "hints_default": True})
    assert res.status_code == 200 and "deep" in res.json()["tools"] and res.json()["hints_default"] is True
    assert client.put("/api/v1/platform/levels/school", json={"tools": {"teleport": True}}).status_code == 400


def test_only_institution_admin_changes_class_settings(env):
    client, pg, user = env
    inst, cls = make_class(pg, level="school")
    url = f"/api/v1/institutions/classes/{cls['id']}/settings"
    pg.table("institution_members").insert({"institution_id": inst["id"], "user_id": user["id"], "role": "teacher"}).execute()
    assert client.put(url, json={"tools": {"quiz": False}}).status_code == 403
    pg.table("institution_members").update({"role": "admin"}).eq("user_id", user["id"]).execute()
    from services.institution_service import institutions
    if hasattr(institutions, "forget"):
        institutions.forget(user_id=user["id"])
    res = client.put(url, json={"tools": {"quiz": False}, "hint_mode": "always_on", "level": "higher_secondary"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["level"] == "higher_secondary" and body["hint_mode"] == "always_on" and "quiz" not in body["tools"]
    assert client.put(url, json={"hint_mode": "sometimes"}).status_code == 400
    other_inst, other_cls = make_class(pg, level="school")
    assert client.get(f"/api/v1/institutions/classes/{other_cls['id']}/settings").status_code == 404


def test_chat_prompt_carries_level_and_safety_short_circuits(env, monkeypatch):
    client, pg, user = env
    set_level(pg, user["id"], "school")
    project = pg.table("projects").insert({"user_id": user["id"], "name": "B"}).execute().data[0]
    seen = {}

    async def fake_answer(**kw):
        seen.update(kw)
        return {"answer": "Plants make food from light.", "sources": []}

    from services.rag_service import rag_service
    monkeypatch.setattr(rag_service, "get_answer", fake_answer)
    res = client.post("/api/v1/chat/message", json={"project_id": project["id"], "message": "What is photosynthesis?",
                                                    "hints": True})
    assert res.status_code == 200, res.text
    assert "Class 5-10" in seen["user_context"] and "HINTS FIRST" in seen["user_context"]
    assert "SAFETY" in seen["user_context"]

    seen.clear()
    res = client.post("/api/v1/chat/message", json={"project_id": project["id"], "message": "I want to die"})
    assert res.status_code == 200 and "14416" in res.json()["answer"]
    assert seen == {}     # no AI call
    events = pg.table("safety_events").select("category, user_id").execute().data
    assert events == [{"category": "distress", "user_id": user["id"]}]
    saved = pg.table("chat_messages").select("role, content").eq("project_id", project["id"]).execute().data
    assert any(m["role"] == "assistant" and "14416" in m["content"] for m in saved)
