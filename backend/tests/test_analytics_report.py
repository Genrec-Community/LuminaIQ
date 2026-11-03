"""The admin analytics dashboard numbers (real Postgres, its own fresh database)."""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from db.client import SupabaseClient


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return self.pg.table(name)


@pytest.fixture(scope="module")
def fresh_pg():
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg
    from db.migrate import migrate
    from db.pg import PgClient

    name = f"lumina_analytics_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = base.rsplit("/", 1)[0] + "/" + name
    migrate(url)
    client = PgClient(url, max_size=4)
    yield client
    client.close()
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def _ago(days=0, hours=0):
    return (datetime.now(timezone.utc) - timedelta(days=days, hours=hours)).isoformat()


@pytest.fixture(scope="module")
def seeded(fresh_pg):
    """A (new, school level, studies and pays), B (signed up last period, back today), C (new, did nothing)."""
    from services.usage_service import _tz
    pg = fresh_pg
    a, b, c = (str(uuid.uuid4()) for _ in range(3))
    today = datetime.now(_tz()).date()
    t = pg.table
    t("app_users").insert([
        {"id": a, "email": "asha@example.com", "created_at": _ago(3)},
        {"id": b, "email": "ben@example.com", "created_at": _ago(40)},
        {"id": c, "email": "cara@example.com", "created_at": _ago(0, 1)},
    ]).execute()
    t("user_active_days").insert([
        {"user_id": a, "day": (today - timedelta(days=3)).isoformat()},
        {"user_id": a, "day": today.isoformat()},
        {"user_id": b, "day": (today - timedelta(days=40)).isoformat()},
        {"user_id": b, "day": today.isoformat()},
        {"user_id": c, "day": today.isoformat()},
    ]).execute()
    t("user_settings").insert({"user_id": a, "settings": {"studyLevel": "school"}}).execute()
    project = t("projects").insert({"user_id": a, "name": "Biology"}).execute().data[0]["id"]
    t("documents").insert([
        {"project_id": project, "filename": "bio.pdf", "upload_status": "completed"},
        {"project_id": project, "filename": "bad.pdf", "upload_status": "failed"},
    ]).execute()
    thread = t("chat_threads").insert({"project_id": project, "user_id": a, "title": "Cells"}).execute().data[0]["id"]
    t("chat_messages").insert([
        {"project_id": project, "thread_id": thread, "role": "user", "content": "What is a cell?"},
        {"project_id": project, "thread_id": thread, "role": "assistant", "content": "A cell is…"},
    ]).execute()
    events = [(True, 0.3, 0.5), (True, 0.5, 0.7), (False, 0.7, 0.6)]
    t("learning_events").insert([
        {"user_id": a, "project_id": project, "topic": "Cells", "kind": "mcq", "source": "quiz",
         "correct": ok, "p_known_before": before, "p_known_after": after}
        for ok, before, after in events
    ]).execute()
    t("payments").insert({"user_id": a, "kind": "subscription", "plan": "scholar", "amount_paise": 29900,
                          "currency": "INR", "status": "paid"}).execute()
    t("user_plans").insert({"user_id": a, "plan": "scholar", "status": "active", "source": "razorpay",
                            "billing_cycle": "monthly", "current_period_end": _ago(-20)}).execute()
    t("ai_calls").insert([
        {"user_id": a, "feature": "chat", "kind": "llm", "model": "m", "role": "small",
         "cost_usd": 0.02, "latency_ms": 900},
        {"user_id": a, "feature": "quiz", "kind": "llm", "model": "m", "role": "small",
         "cost_usd": 0.01, "latency_ms": 1500, "ok": False},
    ]).execute()
    t("jobs").insert([
        {"kind": "index_document", "status": "done", "finished_at": _ago()},
        {"kind": "index_document", "status": "failed", "attempts": 3},
    ]).execute()
    t("safety_events").insert({"user_id": a, "level": "school", "category": "off_topic"}).execute()
    return {"a": a, "b": b, "c": c}


@pytest.fixture
def report(fresh_pg, seeded, monkeypatch):
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(fresh_pg))
    from services import analytics_report
    return asyncio.run(analytics_report.report(30))


def test_overview_growth_and_money(report):
    o = report["overview"]
    assert o["total_users"] == 3
    assert o["new_users"]["value"] == 2 and o["new_users"]["previous"] == 1
    assert o["active_users"]["value"] == 3 and o["active_users"]["previous"] == 1
    assert o["dau"] == 3 and o["mau"] == 3
    assert o["questions"]["value"] == 3 and abs(o["accuracy"] - 0.6667) < 1e-4
    assert o["chat_questions"]["value"] == 1 and o["documents"]["value"] == 2
    assert o["revenue_inr"]["value"] == 299 and o["paying_users"] == 1
    assert abs(o["ai_cost_usd"]["value"] - 0.03) < 1e-6
    assert len(report["daily"]) == 30
    assert sum(d["signups"] for d in report["daily"]) == 2
    assert report["daily"][-1]["active"] == 3


def test_funnel_follows_new_signups(report):
    f = {s["step"]: s["users"] for s in report["funnel"]}
    assert f == {"signed_up": 2, "chose_level": 1, "added_book": 1, "book_ready": 1, "asked": 1,
                 "practised": 1, "came_back": 1, "paid": 1}
    assert report["funnel"][1]["of_signups"] == 0.5


def test_retention_cohorts(report):
    r = report["retention"]
    assert len(r) == 8 and sum(w["users"] for w in r) == 3
    assert r[-1]["weeks"][1] is None          # this week's cohort has no "week 1" yet
    for w in r:
        if w["users"]:
            assert w["weeks"][0] is not None and w["weeks"][0] > 0


def test_learning_and_levels(report):
    le = report["learning"]
    assert le["answers"] == 3 and le["learners"] == 1
    assert abs(le["mastery_points"] - 40.0) < 0.01     # +20 +20, the drop doesn't count
    school = next(r for r in le["by_level"] if r["level"] == "school")
    assert school["answers"] == 3 and school["active"] == 1
    not_set = next(r for r in le["by_level"] if r["level"] == "not_set")
    assert not_set["users"] == 2
    top = report["engagement"]["top_learners"][0]
    assert top["email"] == "asha@example.com" and top["answers"] == 3 and top["chat_questions"] == 1
    assert report["engagement"]["practice"][0]["source"] == "quiz"


def test_revenue_and_health(report):
    rv = report["revenue"]
    assert rv["mrr_inr"] == 299 and rv["new_payers"] == 1
    assert rv["subscriptions"][0]["plan"] == "scholar"
    h = report["health"]
    job = h["jobs"][0]
    assert job["kind"] == "index_document" and job["failed"] == 1 and job["failure_rate"] == 0.5
    assert h["documents"]["failed"] == 1 and h["documents"]["failure_rate"] == 0.5
    assert h["ai"]["errors"] == 1 and h["ai"]["error_rate"] == 0.5
    assert h["safety"] == [{"level": "school", "category": "off_topic", "count": 1}]


def test_no_chat_text_in_report(report):
    import json
    blob = json.dumps(report)
    assert "What is a cell" not in blob and "A cell is" not in blob


def test_active_day_recorded_once_per_day(fresh_pg, monkeypatch):
    from api import deps
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(fresh_pg))
    u = str(uuid.uuid4())
    deps._seen.clear()
    asyncio.run(deps._remember_user(u, "new@example.com"))
    asyncio.run(deps._remember_user(u, "new@example.com"))
    rows = fresh_pg.fetch("SELECT day FROM user_active_days WHERE user_id = %s", (u,))
    assert len(rows) == 1
