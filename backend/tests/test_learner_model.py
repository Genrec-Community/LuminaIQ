"""Learner model: weak/strong topics, mistakes and misconceptions, and the prompt block (real Postgres)."""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from db.client import SupabaseClient
from services import context_builder, learner_model as lm


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return self.pg.table(name)


def run(c):
    return asyncio.run(c)


@pytest.fixture
def env(pg_client, monkeypatch):
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(pg_client))
    queued = []

    async def enqueue(kind, payload, **kw):
        queued.append((kind, payload))
    monkeypatch.setattr("services.jobs.enqueue", enqueue)
    user = str(uuid.uuid4())
    pid = pg_client.table("projects").insert({"user_id": user, "name": "Physics"}).execute().data[0]["id"]
    other = pg_client.table("projects").insert({"user_id": user, "name": "Chem"}).execute().data[0]["id"]
    now = datetime.now(timezone.utc).isoformat()

    def mastery(project, topic, p, attempts=4):
        pg_client.table("topic_mastery").insert({
            "user_id": user, "project_id": project, "topic": topic, "p_known": p, "attempts": attempts,
            "correct": int(attempts * p), "stability_days": 30, "last_seen": now, "updated_at": now}).execute()

    return {"pg": pg_client, "user": user, "pid": pid, "other": other, "mastery": mastery, "queued": queued}


def test_weak_and_strong_topics(env):
    m = env["mastery"]
    m(env["pid"], "Kinematics", 0.2)
    m(env["pid"], "Optics", 0.95)
    m(env["pid"], "Waves", 0.4)
    m(env["pid"], "Barely tried", 0.1, attempts=1)
    m(env["other"], "Organic naming", 0.1)
    snap = run(lm.snapshot(env["user"], env["pid"], across_books=True))
    assert [t for t, _ in snap.weak] == ["Kinematics", "Waves"]
    assert [t for t, _ in snap.strong] == ["Optics"]
    assert [t for t, _ in snap.other_books_weak] == ["Organic naming"]
    assert run(lm.snapshot(env["user"], env["pid"], across_books=False)).other_books_weak == []
    assert run(lm.weak_topics(env["user"], env["pid"], limit=1))[0][0] == "Kinematics"


def test_mistakes_are_recorded_tagged_and_fixed(env, monkeypatch):
    ids = run(lm.record_mistakes(env["user"], env["pid"], "Motion", [
        {"question": "Unit of velocity?", "wrong_answer": "m", "correct_answer": "m/s"},
        {"question": "Is speed a vector?", "wrong_answer": "Yes", "correct_answer": "No"}]))
    assert len(ids) == 2 and env["queued"] == [("tag_mistakes", {"ids": ids})]

    async def llm(messages, **kw):
        assert "Unit of velocity?" in messages[-1]["content"]
        return '["mixes up distance and velocity units", ""]'
    monkeypatch.setattr("services.llm_service.llm_service.chat_completion", llm)
    assert run(lm.tag_mistakes(ids)) == 2
    snap = run(lm.snapshot(env["user"], env["pid"]))
    tags = {m["question"]: m["misconception"] for m in snap.mistakes}
    assert tags == {"Unit of velocity?": "mixes up distance and velocity units", "Is speed a vector?": ""}

    assert run(lm.mark_fixed(env["user"], env["pid"], ["Unit of velocity?"])) == 1
    assert [m["question"] for m in run(lm.snapshot(env["user"], env["pid"])).mistakes] == ["Is speed a vector?"]


def test_mistakes_from_other_books_follow_the_setting(env):
    run(lm.record_mistakes(env["user"], env["other"], "Naming", [{"question": "Name CH4", "wrong_answer": "Ethane",
                                                                    "correct_answer": "Methane"}]))
    assert len(run(lm.snapshot(env["user"], env["pid"], across_books=True)).mistakes) == 1
    assert run(lm.snapshot(env["user"], env["pid"], across_books=False)).mistakes == []


def test_learner_block_contents_and_budget():
    snap = lm.Snapshot(weak=[("Kinematics", 0.2)], strong=[("Optics", 0.9)],
                       mistakes=[{"topic": "Motion", "wrong_answer": "m", "correct_answer": "m/s",
                                  "misconception": "unit confusion"}])
    block = context_builder.learner_block(snap, [{"content": "Likes cricket examples"}], "They asked about friction.", 900)
    assert "Finding hard: Kinematics (20%)" in block and "Comfortable with: Optics" in block
    assert "likely: unit confusion" in block and "Likes cricket examples" in block
    assert block.index("They asked about friction") < block.index("Finding hard")   # the chat summary comes first
    tight = context_builder.learner_block(snap, [{"content": "x" * 2000}], "s" * 4000, 200)
    assert context_builder.tokens(tight) <= 215
    assert context_builder.learner_block(lm.Snapshot(), [], "", 900) == ""
