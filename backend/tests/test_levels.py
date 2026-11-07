"""Learner levels and tool policies: platform defaults, class narrowing, locking, caching."""

import asyncio
import uuid

import pytest

from db.client import SupabaseClient
from services import levels
from services.tools_catalog import DEFAULT_TOOLS, LEVELS, TOOLS


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return self.pg.table(name)

    def rpc(self, name, params=None):
        return self.pg.rpc(name, params)


@pytest.fixture
def pg(pg_client, monkeypatch):
    with pg_client.pool.connection() as conn:
        conn.execute("TRUNCATE level_tool_policies, level_settings, class_tool_policies, user_settings, "
                     "institutions, institution_members, institution_classes, class_members CASCADE")
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(pg_client))
    from utils import cache
    monkeypatch.setattr(cache, "_cache", cache.Cache(cache.MemoryBackend()))
    return pg_client


def run(c):
    return asyncio.run(c)


def set_level(pg, user, level):
    pg.table("user_settings").upsert({"user_id": user, "settings": {"studyLevel": level}},
                                     on_conflict="user_id").execute()


def make_class(pg, level=None, **cols):
    inst = pg.table("institutions").insert({"name": "School", "teacher_code": uuid.uuid4().hex[:8],
                                          "owner_user_id": str(uuid.uuid4())}).execute().data[0]
    cls = pg.table("institution_classes").insert({"institution_id": inst["id"], "name": "8-B",
                                                  "invite_code": uuid.uuid4().hex[:8], "level": level,
                                                  **cols}).execute().data[0]
    return inst, cls


def enrol(pg, inst, cls, user):
    pg.table("institution_members").insert({"institution_id": inst["id"], "user_id": user, "role": "student"}).execute()
    pg.table("class_members").insert({"class_id": cls["id"], "user_id": user}).execute()


def test_catalog_is_consistent():
    assert set(LEVELS) == {"school", "higher_secondary", "ugpg", "research", "general"}
    for level in LEVELS:
        assert set(DEFAULT_TOOLS[level]) <= set(TOOLS)


def test_defaults_per_level(pg):
    user = str(uuid.uuid4())
    set_level(pg, user, "school")
    eff = run(levels.effective_for(user))
    assert eff["level"] == "school" and not eff["locked"] and not eff["needs_level"]
    assert "quiz" in eff["tools"] and "leaderboard" in eff["tools"]
    assert "deep" not in eff["tools"] and "bookstore" not in eff["tools"]
    assert eff["hint_mode"] == "student_choice" and eff["hints_default"] is False and eff["outside_book"] is True
    set_level(pg, user, "research")
    run(levels.forget(user))
    eff = run(levels.effective_for(user))
    assert "deep" in eff["tools"] and "leaderboard" not in eff["tools"]


def test_platform_override(pg):
    user = str(uuid.uuid4())
    set_level(pg, user, "school")
    run(levels.save_level_policy("school", {"lab": False, "deep": True}, hints_default=True, outside_book=False))
    eff = run(levels.effective_for(user))
    assert "lab" not in eff["tools"] and "deep" in eff["tools"]
    assert eff["hints_default"] is True and eff["outside_book"] is False


def test_class_narrows_tools(pg):
    user = str(uuid.uuid4())
    inst, cls = make_class(pg, level="school", hint_mode="always_on", allow_outside_book=False)
    enrol(pg, inst, cls, user)
    run(levels.save_class_policy(cls["id"], {"quiz": False}))
    eff = run(levels.effective_for(user))
    assert "quiz" not in eff["tools"] and "notes" in eff["tools"]
    assert eff["hint_mode"] == "always_on" and eff["outside_book"] is False and eff["class_id"] == cls["id"]


def test_class_cannot_enable_platform_disabled_tool(pg):
    user = str(uuid.uuid4())
    inst, cls = make_class(pg, level="school")
    enrol(pg, inst, cls, user)
    run(levels.save_class_policy(cls["id"], {"deep": True}))
    assert "deep" not in run(levels.effective_for(user))["tools"]


def test_student_takes_class_level_and_is_locked(pg):
    user = str(uuid.uuid4())
    set_level(pg, user, "research")
    inst, cls = make_class(pg, level="school")
    enrol(pg, inst, cls, user)
    eff = run(levels.effective_for(user))
    assert eff["level"] == "school" and eff["locked"] is True


def test_student_without_class_level_uses_own(pg):
    user = str(uuid.uuid4())
    set_level(pg, user, "higher_secondary")
    inst, cls = make_class(pg, level=None)
    enrol(pg, inst, cls, user)
    eff = run(levels.effective_for(user))
    assert eff["level"] == "higher_secondary" and eff["locked"] is False


def test_no_level_needs_level(pg):
    eff = run(levels.effective_for(str(uuid.uuid4())))
    assert eff["needs_level"] is True and eff["level"] is None
    assert "chat" in eff["tools"]     # still usable (general defaults) until they choose


def test_policy_change_clears_cache(pg):
    user = str(uuid.uuid4())
    set_level(pg, user, "ugpg")
    assert "notes" in run(levels.effective_for(user))["tools"]
    run(levels.save_level_policy("ugpg", {"notes": False}))
    assert "notes" not in run(levels.effective_for(user))["tools"]


def test_set_own_level(pg):
    user = str(uuid.uuid4())
    run(levels.set_own_level(user, "school"))
    assert run(levels.effective_for(user))["level"] == "school"
    with pytest.raises(ValueError):
        run(levels.set_own_level(user, "kindergarten"))
