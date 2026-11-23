"""Product data (events, attribution, consent, feedback, attempts) and the growth analytics on real Postgres."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from db.client import SupabaseClient
from services import product_analytics as pa


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return self.pg.table(name)


@pytest.fixture
def app_db(pg_client, monkeypatch):
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(pg_client))
    for t in ("product_events", "signup_attribution", "consent_records", "feedback", "attempt_responses",
              "assessment_attempts", "data_requests", "user_active_days", "learning_events", "app_users"):
        pg_client.fetch(f"DELETE FROM {t}")
    return pg_client


def run(coro):
    return asyncio.run(coro)


def _ago(days=0):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- pure rules

@pytest.mark.parametrize("data,channel", [
    ({"utm_source": "google", "utm_medium": "cpc"}, "paid"),
    ({"invite_code": "ABC123"}, "school"),
    ({"referral_code": "FRIEND"}, "referral"),
    ({"utm_source": "instagram"}, "social"),
    ({"utm_source": "newsletter"}, "email"),
    ({"referrer_host": "www.google.com"}, "search"),
    ({"referrer_host": "l.instagram.com"}, "social"),
    ({"referrer_host": "someblog.in"}, "referral"),
    ({}, "direct"),
])
def test_channel_rules(data, channel):
    assert pa.channel_for(data) == channel


def test_parental_consent_only_for_minor_levels_and_not_school_accounts():
    assert pa.required_kinds("school", managed=False) == ["terms", "privacy", "parental"]
    assert pa.required_kinds("higher_secondary", managed=False)[-1] == "parental"
    assert pa.required_kinds("ugpg", managed=False) == ["terms", "privacy"]
    assert pa.required_kinds("school", managed=True) == []


def test_props_never_keep_emails():
    assert pa._clean_props({"plan": "scholar", "who": "a@b.com", "n": 3, "nested": {"x": 1}}) == {"plan": "scholar", "n": 3}


# ---------------------------------------------------------------- writes

def test_track_drops_unknown_names_and_strips_queries(app_db):
    n = run(pa.track([{"name": "page_view", "path": "/plans?utm_source=x"}, {"name": "made_up"}],
                     anon_id="anon-1", platform="web"))
    assert n == 1
    row = app_db.fetch("SELECT name, path, anon_id, user_id FROM product_events")[0]
    assert row == {"name": "page_view", "path": "/plans", "anon_id": "anon-1", "user_id": None}


def test_attribution_is_first_touch_and_links_earlier_events(app_db):
    uid = str(uuid.uuid4())
    run(pa.track([{"name": "signup_started"}], anon_id="anon-2"))
    assert run(pa.save_attribution(uid, {"utm_source": "instagram", "referrer": "https://l.instagram.com/x?y=1",
                                         "landing_path": "/?utm_source=instagram", "anon_id": "anon-2"})) is True
    assert run(pa.save_attribution(uid, {"utm_source": "google", "utm_medium": "cpc"})) is False
    a = app_db.fetch("SELECT channel, referrer_host, landing_path FROM signup_attribution WHERE user_id = %s", (uid,))[0]
    assert a == {"channel": "social", "referrer_host": "l.instagram.com", "landing_path": "/"}
    names = {r["name"] for r in app_db.fetch("SELECT name FROM product_events WHERE user_id = %s", (uid,))}
    assert names == {"signup_started", "signup_completed"}


def test_consent_latest_answer_wins_and_versions_matter(app_db):
    uid = str(uuid.uuid4())
    assert run(pa.missing_consent(uid, "school", False)) == ["terms", "privacy", "parental"]
    run(pa.record_consent(uid, "terms", True, "sign_in_notice", ip="1.2.3.4"))
    run(pa.record_consent(uid, "privacy", True, "sign_in_notice"))
    run(pa.record_consent(uid, "parental", True, "guardian_declaration", granted_by="guardian",
                          guardian_name="Parent", guardian_email="p@example.com"))
    assert run(pa.missing_consent(uid, "school", False)) == []
    run(pa.record_consent(uid, "parental", False, "settings", granted_by="guardian"))
    assert run(pa.missing_consent(uid, "school", False)) == ["parental"]
    ip = app_db.fetch("SELECT ip_hash FROM consent_records WHERE kind = 'terms'")[0]["ip_hash"]
    assert ip and "1.2.3.4" not in ip


def test_answer_rating_replaces_earlier_thumbs(app_db):
    uid = str(uuid.uuid4())
    run(pa.record_feedback(uid, "answer_rating", rating=1, target_type="chat_message", target_id="m1"))
    run(pa.record_feedback(uid, "answer_rating", rating=-1, target_type="chat_message", target_id="m1"))
    rows = app_db.fetch("SELECT rating FROM feedback WHERE kind = 'answer_rating'")
    assert rows == [{"rating": -1}]
    with pytest.raises(ValueError):
        run(pa.record_feedback(uid, "nps", rating=11))


def test_attempt_records_score_time_and_responses(app_db):
    uid = str(uuid.uuid4())
    started = (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()
    aid = run(pa.record_attempt(uid, "mcq", project_id=None, source_id=str(uuid.uuid4()), topic="Cells",
                                difficulty="medium", question_count=4, started_at=started,
                                responses=[{"chosen": "A", "correct_answer": "A", "is_correct": True},
                                           {"chosen": "B", "correct_answer": "C", "is_correct": False},
                                           {"chosen": "D", "correct_answer": "D", "is_correct": True},
                                           {"chosen": None, "correct_answer": "A", "is_correct": False}]))
    a = app_db.fetch("SELECT score_pct, answered_count, correct_count, duration_seconds FROM assessment_attempts WHERE id = %s", (aid,))[0]
    assert a["score_pct"] == 50 and a["answered_count"] == 3 and a["correct_count"] == 2
    assert 230 <= a["duration_seconds"] <= 250
    assert len(app_db.fetch("SELECT 1 FROM attempt_responses WHERE attempt_id = %s", (aid,))) == 4
    assert app_db.fetch("SELECT name FROM product_events WHERE user_id = %s", (uid,)) == [{"name": "quiz_completed"}]


def test_data_request_is_not_duplicated(app_db):
    uid = str(uuid.uuid4())
    first = run(pa.request_data(uid, "delete"))
    again = run(pa.request_data(uid, "delete"))
    assert first["id"] == again["id"] and first["status"] == "pending"


# ---------------------------------------------------------------- dashboard sections

def test_growth_sections(app_db):
    from services import analytics_report
    from services.usage_service import _tz
    today = datetime.now(_tz()).date()
    old, new = str(uuid.uuid4()), str(uuid.uuid4())
    app_db.table("app_users").insert([{"id": old, "email": "o@example.com", "created_at": _ago(20)},
                                      {"id": new, "email": "n@example.com", "created_at": _ago(1)}]).execute()
    app_db.table("user_active_days").insert([{"user_id": old, "day": (today - timedelta(days=20)).isoformat()},
                                             {"user_id": old, "day": today.isoformat()},
                                             {"user_id": new, "day": today.isoformat()}]).execute()
    project = app_db.table("projects").insert({"user_id": old, "name": "Bio"}).execute().data[0]["id"]
    app_db.table("learning_events").insert({"user_id": old, "project_id": project, "topic": "Cells", "kind": "mcq", "correct": True,
                                            "created_at": _ago(19)}).execute()
    run(pa.save_attribution(old, {"utm_source": "instagram"}))
    run(pa.track([{"name": "quiz_started"}, {"name": "quiz_started"}], user_id=old))
    for score_started in ((0, 10), (1, 5)):
        right = score_started[0]
        run(pa.record_attempt(old, "mcq", project_id=None, source_id=None, topic="Cells", difficulty=None,
                              question_count=2, started_at=_ago(score_started[1]),
                              responses=[{"chosen": "A", "is_correct": bool(right)}, {"chosen": "A", "is_correct": True}]))
    run(pa.record_feedback(old, "nps", rating=10))
    run(pa.record_feedback(new, "nps", rating=3))
    run(pa.record_feedback(old, "answer_rating", rating=1, target_type="chat_message", target_id="m"))

    r = run(analytics_report.report(30))
    inv = r["investor"]
    assert inv["learners"] == 2 and inv["mau"] == 2
    assert inv["retention"]["d7"] == {"eligible": 1, "returned": 1, "rate": 1.0}
    assert inv["activation"]["cohort"] == 1 and inv["activation"]["rate"] == 1.0
    assert len(inv["monthly"]) == 12
    ch = {c["channel"]: c for c in r["acquisition"]["channels"]}
    assert ch["social"]["signups"] == 1 and ch["unknown"]["signups"] == 1
    steps = {s["step"]: s["people"] for s in r["product_funnel"]["steps"]}
    assert steps["quiz_started"] == 1 and steps["quiz_completed"] == 1 and steps["signup_completed"] == 1
    a = r["assessments"]
    assert a["attempts"] == 2 and a["completion_rate"] == 1.0
    assert a["improvement"] == {"learner_topics": 1, "avg_gain_points": 50.0, "improved_share": 1.0}
    f = r["feedback"]
    assert f["nps"] == {"responses": 2, "score": 0} and f["ratings"]["helpful_rate"] == 1.0


# ---------------------------------------------------------------- API

@pytest.fixture
def api(app_db):
    from fastapi.testclient import TestClient
    from api.deps import get_current_user
    from main import app
    uid = str(uuid.uuid4())
    app_db.table("user_settings").insert({"user_id": uid, "settings": {"studyLevel": "school"}}).execute()
    app.dependency_overrides[get_current_user] = lambda: {"id": uid, "email": "x@x.com", "managed": False}
    yield TestClient(app, raise_server_exceptions=False), uid
    app.dependency_overrides.clear()


def test_track_works_without_signing_in(api, app_db):
    c, _ = api
    r = c.post("/api/v1/events/track", json={"anon_id": "a1", "platform": "web",
                                             "events": [{"name": "page_view", "path": "/"}]},
               headers={"Authorization": ""})
    assert r.status_code == 204
    assert app_db.fetch("SELECT count(*) AS n FROM product_events")[0]["n"] == 1


def test_consent_flow_for_a_school_learner(api, app_db):
    c, uid = api
    assert c.get("/api/v1/events/consent").json()["missing"] == ["terms", "privacy", "parental"]
    assert c.post("/api/v1/events/consent", json={"kind": "parental"}).status_code == 400
    for kind in ("terms", "privacy"):
        assert c.post("/api/v1/events/consent", json={"kind": kind}).status_code == 200
    ok = c.post("/api/v1/events/consent", json={"kind": "parental", "method": "guardian_declaration",
                                                "guardian_name": "Meena", "guardian_email": "meena@example.com"})
    assert ok.status_code == 200
    assert c.get("/api/v1/events/consent").json()["missing"] == []
    assert app_db.fetch("SELECT granted_by FROM consent_records WHERE kind = 'parental'")[0]["granted_by"] == "guardian"


def test_feedback_and_data_request_endpoints(api):
    c, _ = api
    assert c.post("/api/v1/events/feedback", json={"kind": "answer_rating", "rating": 1,
                                                   "target_type": "chat_message", "target_id": "m9"}).status_code == 200
    assert c.post("/api/v1/events/feedback", json={"kind": "answer_rating", "rating": 5}).status_code == 400
    assert c.post("/api/v1/events/data-request", json={"kind": "export"}).json()["status"] == "pending"
