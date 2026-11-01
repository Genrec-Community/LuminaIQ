"""Conversation memory: rolling summaries, memory facts, level gating, settings, pruning (real Postgres)."""

import asyncio
import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from db.client import SupabaseClient
from services import memory


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
    user = str(uuid.uuid4())
    pid = pg_client.table("projects").insert({"user_id": user, "name": "Physics"}).execute().data[0]["id"]
    other = pg_client.table("projects").insert({"user_id": user, "name": "Chem"}).execute().data[0]["id"]
    state = {"settings": {}, "llm": [], "facts_reply": '{"add": [], "update": [], "delete": []}'}

    async def get_settings(uid):
        return state["settings"]
    monkeypatch.setattr("services.user_data_service.user_data.get_settings", get_settings)

    async def llm(messages, **kw):
        system, user_msg = messages[0]["content"], messages[-1]["content"]
        state["llm"].append(system[:30])
        if system.startswith("You keep a running summary"):
            # A faithful fake summariser: keeps the previous summary and every line marked KEY
            prev = user_msg.split("Current summary:\n", 1)[1].split("\n\nNew messages:", 1)[0]
            keys = re.findall(r"KEY[^\n]*", user_msg.split("New messages:", 1)[1])
            return "\n".join(x for x in [prev if prev != "(none yet)" else "", *keys] if x)
        return state["facts_reply"]
    monkeypatch.setattr("services.llm_service.llm_service.chat_completion", llm)

    t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def add_turns(n, start=0, fact_at=None):
        rows = []
        for i in range(start, start + n):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"turn {i}"
            if i == fact_at:
                content = "KEY: my board exam is on 12 March and I mix up speed and velocity"
            rows.append({"project_id": pid, "role": role, "content": content,
                         "created_at": (t0 + timedelta(minutes=i)).isoformat()})
        pg_client.table("chat_messages").insert(rows).execute()

    return {"pg": pg_client, "user": user, "pid": pid, "other": other, "state": state, "add_turns": add_turns}


def test_hundred_turn_chat_remembers_turn_three(env):
    # The job runs every ~10 messages as the chat grows
    for start in range(0, 100, 10):
        env["add_turns"](10, start=start, fact_at=3 if start == 0 else None)
        run(memory.refresh(env["pid"], env["user"], "higher_secondary"))
    summary, recent = run(memory.chat_context(env["pid"]))
    assert "12 March" in summary and "speed and velocity" in summary
    assert memory.KEEP_RECENT <= len(recent) <= memory.MAX_RECENT
    assert recent[-1]["content"] == "turn 99"
    # no gap: the first recent turn comes straight after the summarised ones
    row = env["pg"].fetch("SELECT covered_count FROM chat_summaries WHERE project_id = %s", (env["pid"],))[0]
    assert recent[0]["content"] == f"turn {row['covered_count']}"


def test_short_chats_are_not_summarised(env):
    env["add_turns"](12)
    assert run(memory.refresh(env["pid"], env["user"], "ugpg")) == {"summarised": 0}
    assert run(memory.maybe_refresh(env["pid"], env["user"], "ugpg")) is False
    summary, recent = run(memory.chat_context(env["pid"]))
    assert summary == "" and len(recent) == 12


def test_facts_are_extracted_for_class_11_and_up_only(env):
    env["state"]["facts_reply"] = json.dumps({"add": [{"kind": "goal", "content": "Board exam on 12 March"}]})
    env["add_turns"](20)
    run(memory.refresh(env["pid"], env["user"], "school"))
    assert run(memory.list_memories(env["user"])) == []          # Class 5-10: no automatic facts
    env["pg"].fetch("DELETE FROM chat_summaries")
    run(memory.refresh(env["pid"], env["user"], "higher_secondary"))
    facts = run(memory.list_memories(env["user"]))
    assert [(f["kind"], f["content"], f["source"]) for f in facts] == [("goal", "Board exam on 12 March", "chat")]


def test_auto_memory_can_be_switched_off(env):
    env["state"]["settings"] = {"autoMemory": False}
    env["state"]["facts_reply"] = json.dumps({"add": [{"kind": "fact", "content": "Likes cricket"}]})
    env["add_turns"](20)
    run(memory.refresh(env["pid"], env["user"], "ugpg"))
    assert run(memory.list_memories(env["user"])) == []


def test_facts_dedupe_update_and_delete(env):
    a = run(memory.add_memory(env["user"], "Likes cricket examples", kind="interest"))
    b = run(memory.add_memory(env["user"], "Exam in May", kind="goal"))
    env["state"]["facts_reply"] = json.dumps({
        "add": [{"kind": "interest", "content": "likes cricket examples!"}, {"kind": "fact", "content": "Uses NCERT"}],
        "update": [{"id": b["id"], "content": "Exam moved to June"}], "delete": [a["id"], "not-an-id"]})
    env["add_turns"](20)
    run(memory.refresh(env["pid"], env["user"], "ugpg"))
    assert sorted(f["content"] for f in run(memory.list_memories(env["user"]))) == ["Exam moved to June", "Uses NCERT"]


def test_cap_drops_least_recently_used(env, monkeypatch):
    monkeypatch.setattr(memory, "MAX_MEMORIES", 3)
    for i in range(5):
        run(memory.add_memory(env["user"], f"fact {i}"))
    assert len(run(memory.list_memories(env["user"]))) == 3


def test_prompt_facts_rank_by_relevance_and_respect_across_books(env):
    run(memory.add_memory(env["user"], "Struggles with organic chemistry naming", kind="struggle",
                          project_id=env["other"], source="chat"))
    run(memory.add_memory(env["user"], "Wants answers with diagrams", kind="preference"))
    run(memory.add_memory(env["user"], "Confuses speed and velocity", kind="struggle",
                          project_id=env["pid"], source="chat"))
    chosen = run(memory.for_prompt(env["user"], env["pid"], "what is velocity?", across_books=True, limit=2))
    assert [c["content"] for c in chosen] == ["Wants answers with diagrams", "Confuses speed and velocity"]
    local = run(memory.for_prompt(env["user"], env["pid"], "organic chemistry naming", across_books=False))
    assert "Struggles with organic chemistry naming" not in [c["content"] for c in local]
    assert "Wants answers with diagrams" in [c["content"] for c in local]       # typed-in facts apply everywhere


def test_clear_all_and_pruning(env):
    from utils.job_queue import housekeeping
    run(memory.add_memory(env["user"], "old fact"))
    run(memory.add_memory(env["user"], "fresh fact"))
    env["pg"].fetch("UPDATE user_memories SET last_used_at = now() - interval '7 months' WHERE content = 'old fact'")
    assert housekeeping(env["pg"])["memories"] == 1
    assert [f["content"] for f in run(memory.list_memories(env["user"]))] == ["fresh fact"]
    env["add_turns"](20)
    run(memory.refresh(env["pid"], env["user"], "ugpg"))
    assert run(memory.clear_all(env["user"])) == {"memories": 1, "summaries": 1}
    assert env["pg"].fetch("SELECT count(*) AS n FROM chat_messages WHERE project_id = %s", (env["pid"],))[0]["n"] == 20


def test_settings_defaults(env):
    assert run(memory.settings_for(env["user"])) == {"across_books": True, "auto": True}
    env["state"]["settings"] = {"memoryAcrossBooks": False}
    assert run(memory.settings_for(env["user"]))["across_books"] is False
