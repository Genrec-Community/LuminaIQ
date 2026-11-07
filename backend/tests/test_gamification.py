"""Phase 7: XP for learning only, daily caps, no farming, kind streaks, adaptive daily goal (real Postgres)."""

import asyncio
import uuid
from datetime import date, timedelta

import pytest

from db.client import SupabaseClient
from services import daily_goal
from services import gamification_service as g


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
    from services.user_data_service import user_data
    monkeypatch.setattr(user_data, "client", app)
    monkeypatch.setattr(g.gamification, "client", app)
    user = str(uuid.uuid4())
    pid = pg_client.table("projects").insert({"user_id": user, "name": "Physics"}).execute().data[0]["id"]
    return {"pg": pg_client, "user": user, "pid": pid}


def total(env):
    rows = env["pg"].fetch("SELECT total_xp FROM user_gamification WHERE user_id = %s", (env["user"],))
    return rows[0]["total_xp"] if rows else 0


# ---------------------------------------------------------------- rules

def test_fixed_awards_and_daily_cap(env):
    got = [g.award_tx(env["pg"], env["user"], "mistake_fixed", dedupe_key=f"fixed:{i}") for i in range(8)]
    paid = [r["xp_earned"] for r in got if r]
    assert paid == [15] * 6 and sum(paid) == g.DAILY_CAPS["mistake_fixed"]
    assert total(env) == 90
    # the next day the cap starts again
    tomorrow = g.local_today() + timedelta(days=1)
    assert g.award_tx(env["pg"], env["user"], "mistake_fixed", dedupe_key="fixed:99", today=tomorrow)["xp_earned"] == 15


def test_the_same_achievement_is_never_paid_twice(env):
    assert g.award_tx(env["pg"], env["user"], "exam_plan_step", dedupe_key="plan:p:Optics")["xp_earned"] == 10
    assert g.award_tx(env["pg"], env["user"], "exam_plan_step", dedupe_key="plan:p:Optics") is None
    assert total(env) == 10


def test_mastery_gain_is_capped_per_day(env):
    a = g.award_tx(env["pg"], env["user"], "mastery_gain", xp=120)
    b = g.award_tx(env["pg"], env["user"], "mastery_gain", xp=80)
    assert a["xp_earned"] == 120 and b["xp_earned"] == 30
    assert g.award_tx(env["pg"], env["user"], "mastery_gain", xp=10) is None


def test_unknown_kinds_and_zero_xp(env):
    with pytest.raises(ValueError):
        g.award_tx(env["pg"], env["user"], "chat")
    assert g.award_tx(env["pg"], env["user"], "mastery_gain", xp=0) is None


def test_clicking_around_earns_nothing(env):
    for activity in ("chat", "notes", "quiz", "pomodoro", "knowledge_graph", "sprint") * 10:
        out = run(g.gamification.award_xp(env["user"], activity, {"score": 100, "num_questions": 20}))
        assert out["xp_earned"] == 0
    assert total(env) == 0


def test_level_up_and_badges(env):
    out = g.award_tx(env["pg"], env["user"], "mastery_gain", xp=70)
    assert out["leveled_up"] and out["level"] == 2
    assert {b["id"] for b in out["new_badges"]} == {"first_gain"}


# ---------------------------------------------------------------- streaks

def test_streak_continues_freezes_once_a_week_and_welcomes_back():
    d = date(2026, 11, 2)   # a Monday
    s = dict(g.DEFAULT_STATS)
    g.update_streak(s, d)
    g.update_streak(s, d + timedelta(days=1))
    assert s["streak_days"] == 2
    out = g.update_streak(s, d + timedelta(days=3))          # missed one day: the week's freeze covers it
    assert out["freeze_used"] and s["streak_days"] == 3
    out = g.update_streak(s, d + timedelta(days=5))          # another miss in the same week: restart
    assert not out["freeze_used"] and s["streak_days"] == 1 and not out["comeback"]
    out = g.update_streak(s, d + timedelta(days=10))         # a real break: comeback bonus, not a scolding
    assert out["comeback"] and s["streak_days"] == 1 and s["best_streak"] == 3


def test_comeback_bonus_is_paid_with_the_first_learning_after_a_break(env):
    old = g.local_today() - timedelta(days=6)
    g.award_tx(env["pg"], env["user"], "mastery_gain", xp=5, today=old)
    out = g.award_tx(env["pg"], env["user"], "mastery_gain", xp=5)
    assert [e["kind"] for e in out["events"]] == ["mastery_gain", "comeback"] and out["xp_earned"] == 25


# ---------------------------------------------------------------- XP follows learning

def _answers(engine, user, pid, topic, results):
    events = [{"topic": topic, "correct": c, "kind": "mcq", "source": "quiz"} for c in results]
    run(engine.record(user, pid, events))


def test_xp_tracks_mastery_gains(env):
    from services.learning_engine import LearningEngine, effective_mastery
    engine = LearningEngine()
    strong, weak = env["user"], str(uuid.uuid4())
    pid2 = env["pg"].table("projects").insert({"user_id": weak, "name": "Physics"}).execute().data[0]["id"]
    _answers(engine, strong, env["pid"], "Kinematics", [True] * 8)
    _answers(engine, weak, pid2, "Kinematics", [True, False] * 4)
    xp = lambda u: env["pg"].fetch("SELECT COALESCE(sum(xp),0) AS n FROM xp_events WHERE user_id = %s AND kind = "
                                   "'mastery_gain'", (u,))[0]["n"]
    assert xp(strong) > xp(weak)
    row = env["pg"].fetch("SELECT * FROM topic_mastery WHERE user_id = %s", (strong,))[0]
    gained = round((effective_mastery(row) - effective_mastery({"p_known": 0.15, "attempts": 0})) * 100)
    assert abs(xp(strong) - gained) <= 2           # XP is the mastery rise, in points
    # getting answers wrong never pays
    before = xp(weak)
    _answers(engine, weak, pid2, "Kinematics", [False] * 5)
    assert xp(weak) == before


# ---------------------------------------------------------------- daily goal

def test_goal_size_follows_level_pace_and_exam():
    assert daily_goal.size_goal("school", 0, None)["target"] == 10
    assert daily_goal.size_goal("higher_secondary", 0, None)["target"] == 20
    assert daily_goal.size_goal("ugpg", 40, None)["target"] > daily_goal.size_goal("ugpg", 5, None)["target"]
    assert daily_goal.size_goal("school", 0, 2)["target"] == 15
    assert daily_goal.size_goal("school", 0, 10)["target"] == 12
    # an unusually busy week counts at most double the level's base, so goals don't explode
    assert daily_goal.size_goal("research", 500, 1)["target"] == round((0.6 * 10 + 0.4 * 20) * 1.5)
    assert daily_goal.size_goal("higher_secondary", 500, 1)["target"] == daily_goal.MAX_TARGET
    assert daily_goal.size_goal("general", 0.1, None)["target"] >= daily_goal.MIN_TARGET


def test_goal_is_fixed_for_the_day_and_pays_once(env):
    goal = run(daily_goal.today(env["user"], "school"))
    assert goal["target"] == 10 and goal["progress"] == 0 and not goal["completed"]
    rows = [{"user_id": env["user"], "project_id": env["pid"], "topic": "Optics", "kind": "mcq", "correct": True}
            for _ in range(10)]
    env["pg"].table("learning_events").insert(rows).execute()
    done = run(daily_goal.today(env["user"], "research"))     # level changes don't resize today's goal
    assert done["target"] == 10 and done["completed"] and done["progress"] == 10
    run(daily_goal.today(env["user"]))
    paid = env["pg"].fetch("SELECT count(*) AS n FROM xp_events WHERE user_id = %s AND kind = 'daily_goal'",
                           (env["user"],))[0]["n"]
    assert paid == 1


def test_state_has_style_goal_and_recent_events(env, monkeypatch):
    async def eff(uid):
        return {"level": "research", "tools": [], "class_id": None}
    monkeypatch.setattr("services.levels.effective_for", eff)
    since = env["pg"].fetch("SELECT now() AS t")[0]["t"]
    g.award_tx(env["pg"], env["user"], "mistake_fixed", dedupe_key="fixed:a")
    state = run(g.gamification.get_gamification(env["user"], str(since)))
    assert state["style"] == "milestones" and state["total_xp"] == 15 and state["streak_days"] == 1
    assert [e["kind"] for e in state["events"]] == ["mistake_fixed"]
    assert state["daily_goal"]["target"] == daily_goal.BASE["research"]
    assert g.style_for("school") == "playful" and g.style_for("higher_secondary") == "exam"
    assert g.style_for("ugpg") == g.style_for("general") == "quiet"


def test_goal_created_in_the_background_uses_the_learners_level(env, monkeypatch):
    async def eff(uid):
        return {"level": "higher_secondary", "tools": [], "class_id": None}
    monkeypatch.setattr("services.levels.effective_for", eff)
    assert run(daily_goal.today(env["user"]))["target"] == daily_goal.BASE["higher_secondary"]
