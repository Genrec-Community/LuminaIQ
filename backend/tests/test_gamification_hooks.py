"""Phase 7 hooks and views: mistakes fixed, reviews on time, plan steps, sync, leaderboard, teacher view."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api import access
from api.deps import get_current_user
from db.client import SupabaseClient
from services import teacher_insights as ti


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
def env(pg_client, monkeypatch):
    app = AppOnPg(pg_client)
    monkeypatch.setattr(SupabaseClient, "_instance", app)
    from services.gamification_service import gamification
    from services.learning_service import spaced_repetition
    from services.user_data_service import user_data
    for obj in (user_data, gamification, spaced_repetition):
        monkeypatch.setattr(obj, "client", app)
    from utils.cache import get_cache
    access.clear_cache()
    user = str(uuid.uuid4())
    pid = pg_client.table("projects").insert({"user_id": user, "name": "Physics"}).execute().data[0]["id"]
    yield {"pg": pg_client, "user": user, "pid": pid, "app": app}
    from main import app as fastapi_app
    fastapi_app.dependency_overrides.clear()


def xp(env, kind, user=None):
    return env["pg"].fetch("SELECT COALESCE(sum(xp), 0) AS n FROM xp_events WHERE user_id = %s AND kind = %s",
                           (user or env["user"], kind))[0]["n"]


def client_for(user_id):
    from main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id, "email": "x@x.com", "managed": False}
    return TestClient(app, raise_server_exceptions=False)


def test_fixing_a_mistake_pays_once(env, monkeypatch):
    from services import learner_model

    async def enqueue(*a, **k):
        return None
    monkeypatch.setattr("services.jobs.enqueue", enqueue)
    run(learner_model.record_mistakes(env["user"], env["pid"], "Motion",
                                      [{"question": "Is speed a vector?", "wrong_answer": "Yes", "correct_answer": "No"}]))
    run(learner_model.mark_fixed(env["user"], env["pid"], ["Is speed a vector?"]))
    run(learner_model.mark_fixed(env["user"], env["pid"], ["Is speed a vector?"]))   # already fixed
    assert xp(env, "mistake_fixed") == 15


def test_reviews_pay_only_when_due_and_once_a_day(env):
    from services.learning_service import spaced_repetition
    t = env["pg"].table
    due = t("review_cards").insert({"user_id": env["user"], "project_id": env["pid"], "topic": "Optics",
                                    "question": "q", "answer": "a",
                                    "next_review": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}
                                   ).execute().data[0]["id"]
    early = t("review_cards").insert({"user_id": env["user"], "project_id": env["pid"], "topic": "Optics",
                                      "question": "q2", "answer": "a",
                                      "next_review": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()}
                                     ).execute().data[0]["id"]
    run(spaced_repetition.record_review(due, 4))
    run(spaced_repetition.record_review(early, 5))       # not due yet: no XP for cramming the same card
    run(spaced_repetition.record_review(due, 4))         # now not due anymore
    assert xp(env, "review_on_time") == 4


def test_plan_steps_pay_once_per_topic(env):
    c = client_for(env["user"])
    body = lambda topics: {"project_id": env["pid"], "completed_topics": topics}
    assert c.put("/api/v1/user-data/progress", json=body(["Optics"])).status_code == 200
    c.put("/api/v1/user-data/progress", json=body([]))              # untick
    c.put("/api/v1/user-data/progress", json=body(["Optics", "Waves"]))   # retick + a new one
    assert xp(env, "exam_plan_step") == 20


def test_sync_returns_new_xp_but_grants_nothing(env):
    from services.gamification_service import award_tx
    c = client_for(env["user"])
    since = c.get("/api/v1/user-data/gamification").json()["server_time"]
    award_tx(env["pg"], env["user"], "mistake_fixed", dedupe_key="fixed:z")
    out = c.post("/api/v1/user-data/gamification/award-xp", json={"activity_type": "quiz", "since": since,
                                                                  "meta": {"score": 100, "num_questions": 50}}).json()
    assert [e["kind"] for e in out["events"]] == ["mistake_fixed"] and out["xp_earned"] == 15
    assert out["total_xp"] == 15        # the quiz claim itself added nothing


def test_class_leaderboard(env):
    t = env["pg"].table
    owner = str(uuid.uuid4())
    inst = t("institutions").insert({"name": "S", "owner_user_id": owner, "teacher_code": uuid.uuid4().hex[:6]}
                                    ).execute().data[0]["id"]
    cls = t("institution_classes").insert({"institution_id": inst, "name": "8A", "invite_code": uuid.uuid4().hex[:6],
                                           "level": "school"}).execute().data[0]["id"]
    other = str(uuid.uuid4())
    for uid, name in ((env["user"], "Asha Rao"), (other, "Ravi Kumar")):
        t("class_members").insert({"class_id": cls, "user_id": uid}).execute()
        t("institution_members").insert({"institution_id": inst, "user_id": uid, "role": "student",
                                         "display_name": name}).execute()
    from services.gamification_service import award_tx
    award_tx(env["pg"], other, "mastery_gain", xp=40)
    award_tx(env["pg"], env["user"], "mastery_gain", xp=25)
    board = client_for(env["user"]).get("/api/v1/user-data/leaderboard").json()
    assert board["enabled"] and [(r["name"], r["xp"], r["me"]) for r in board["rows"]] == [
        ("Ravi", 40, False), ("Asha", 25, True)]
    # the institution switches it off for the class
    t("class_tool_policies").insert({"class_id": cls, "tool": "leaderboard", "enabled": False}).execute()
    run(__import__("services.levels", fromlist=["forget"]).forget(env["user"]))
    assert client_for(env["user"]).get("/api/v1/user-data/leaderboard").json() == {"enabled": False, "rows": []}


def test_individual_learners_have_no_leaderboard(env):
    assert client_for(env["user"]).get("/api/v1/user-data/leaderboard").json()["enabled"] is False


# ---------------------------------------------------------------- teacher view

def test_judge_reasons():
    now = datetime.now(timezone.utc)
    assert ti.judge(None, 0, 0, 0, "", now)[0]["detail"] == "Hasn't started practising yet"
    assert ti.judge(now - timedelta(days=9), 0, 0, 0, "", now)[0]["detail"] == "No practice for 9 days"
    assert [r["reason"] for r in ti.judge(now, 12, -0.3, 4, "Optics", now)] == ["falling", "mistakes"]
    assert "mostly on Optics" in ti.judge(now, 12, 0, 4, "Optics", now)[0]["detail"]
    assert ti.judge(now, 12, 0.2, 1, "", now) == []


def test_stuck_signals_from_learning_data(env):
    t = env["pg"].table
    busy, idle = env["user"], str(uuid.uuid4())
    pid_idle = t("projects").insert({"user_id": idle, "name": "P"}).execute().data[0]["id"]
    t("learning_events").insert([{"user_id": busy, "project_id": env["pid"], "topic": "Optics", "kind": "mcq",
                                  "correct": False, "p_known_before": 0.6, "p_known_after": 0.5} for _ in range(3)]
                                ).execute()
    t("learner_mistakes").insert([{"user_id": busy, "project_id": env["pid"], "topic": "Optics",
                                   "question": f"q{i}"} for i in range(3)]).execute()
    out = run(ti.stuck_signals([(busy, env["pid"]), (idle, pid_idle)]))
    assert [r["reason"] for r in out[(busy, env["pid"])]] == ["falling", "mistakes"]
    assert [r["reason"] for r in out[(idle, pid_idle)]] == ["inactive"]
