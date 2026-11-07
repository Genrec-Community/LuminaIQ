"""Several chats per book ("New chat"), real Postgres."""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import access
from api.deps import get_current_user
from db.client import SupabaseClient
from services import chat_threads


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
    from services.user_data_service import user_data
    monkeypatch.setattr(user_data, "client", app_client)
    access.clear_cache()
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    pa = pg_client.table("projects").insert({"user_id": a, "name": "Physics"}).execute().data[0]["id"]
    pb = pg_client.table("projects").insert({"user_id": b, "name": "B"}).execute().data[0]["id"]
    yield {"pg": pg_client, "a": a, "b": b, "pa": pa, "pb": pb}
    from main import app
    app.dependency_overrides.clear()


def client_for(user_id):
    from main import app
    app.dependency_overrides[get_current_user] = lambda: {"id": user_id, "email": "x@x.com", "managed": False}
    return TestClient(app, raise_server_exceptions=False)


def ask(world, user, project, message, thread_id=None):
    """What the chat endpoints do before calling the model: pick the chat, save the question."""
    from api.v1.endpoints import chat

    async def go():
        req = SimpleNamespace(project_id=project, message=message, hints=None, system_prompt=None,
                              selected_documents=None, deep=False, thread_id=thread_id)
        history, _, save_task, _ = await chat._prepare_chat(req, user)
        await save_task
        await chat._save_reply(req, asyncio.sleep(0), f"answer to {message}")
        return req.thread_id, history
    return run(go())


def test_title_from_first_question():
    assert chat_threads.title_from("What is inertia?") == "What is inertia?"
    assert chat_threads.title_from("[Tutor Mode: Socratic]\n\nWhy is the sky blue") == "Why is the sky blue"
    long = chat_threads.title_from("Explain " + "very " * 30 + "long question")
    assert long.endswith("…") and len(long) <= chat_threads.TITLE_CHARS + 1


def test_new_chat_keeps_conversations_apart(world):
    c = client_for(world["a"])
    first, _ = ask(world, world["a"], world["pa"], "What is inertia?")
    ask(world, world["a"], world["pa"], "and mass?")                     # no thread given: the latest chat
    new = c.post("/api/v1/chat/threads", json={"project_id": world["pa"]}).json()
    assert new["title"] == "New chat"
    second, history = ask(world, world["a"], world["pa"], "Explain Ohm's law", thread_id=new["id"])
    assert second == new["id"] and history == []                          # the new chat starts empty
    threads = c.get(f"/api/v1/chat/threads/{world['pa']}").json()["threads"]
    assert [t["title"] for t in threads] == ["Explain Ohm's law", "What is inertia?"]
    assert [t["message_count"] for t in threads] == [2, 4]
    old = c.get(f"/api/v1/chat/history/{world['pa']}", params={"thread_id": first}).json()
    assert [m["content"] for m in old] == ["What is inertia?", "answer to What is inertia?", "and mass?",
                                           "answer to and mass?"]
    latest = c.get(f"/api/v1/chat/history/{world['pa']}").json()
    assert latest[0]["content"] == "Explain Ohm's law"


def test_rename_and_delete(world):
    c = client_for(world["a"])
    tid, _ = ask(world, world["a"], world["pa"], "What is inertia?")
    assert c.patch(f"/api/v1/chat/threads/{tid}", json={"title": "Inertia notes"}).json()["title"] == "Inertia notes"
    assert c.delete(f"/api/v1/chat/threads/{tid}").json() == {"deleted": True}
    assert c.get(f"/api/v1/chat/threads/{world['pa']}").json()["threads"] == []
    assert world["pg"].fetch("SELECT count(*) AS n FROM chat_messages WHERE thread_id = %s", (tid,))[0]["n"] == 0


def test_other_students_cannot_reach_a_chat(world):
    tid, _ = ask(world, world["a"], world["pa"], "secret question")
    other = client_for(world["b"])
    assert other.get(f"/api/v1/chat/threads/{world['pa']}").status_code == 404
    assert other.patch(f"/api/v1/chat/threads/{tid}", json={"title": "x"}).status_code == 404
    assert other.delete(f"/api/v1/chat/threads/{tid}").status_code == 404
    assert other.post("/api/v1/chat/threads", json={"project_id": world["pa"]}).status_code == 404
    # a thread from another book can't be used with this book
    with pytest.raises(Exception):
        ask(world, world["b"], world["pb"], "hi", thread_id=tid)
    assert other.get(f"/api/v1/chat/history/{world['pb']}", params={"thread_id": tid}).status_code == 404
