"""Per-user rate limits on the expensive endpoints."""

import asyncio
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.deps import get_current_user
from utils import rate_limit as rl


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(rl, "_counter", rl.MemoryCounter())
    monkeypatch.setattr(rl.settings, "RATE_LIMITS_ENABLED", True)
    monkeypatch.setattr(rl.settings, "RATE_LIMIT_CHAT_PER_MIN", 3)
    app = FastAPI()

    @app.post("/chat", dependencies=[Depends(rl.rate_limit("chat"))])
    async def chat():
        return {"ok": True}

    user = {"id": "u1"}
    app.dependency_overrides[get_current_user] = lambda: user
    return app, user


def test_rate_limit_returns_429_with_retry_after(app):
    a, _ = app
    c = TestClient(a)
    assert [c.post("/chat").status_code for _ in range(3)] == [200, 200, 200]
    res = c.post("/chat")
    assert res.status_code == 429
    assert 0 < int(res.headers["retry-after"]) <= 60
    assert "too fast" in res.json()["detail"]["message"].lower()


def test_rate_limit_is_per_user(app):
    a, user = app
    c = TestClient(a)
    for _ in range(3):
        c.post("/chat")
    assert c.post("/chat").status_code == 429
    user["id"] = "u2"
    assert c.post("/chat").status_code == 200


def test_rate_limit_disabled(app, monkeypatch):
    a, _ = app
    monkeypatch.setattr(rl.settings, "RATE_LIMITS_ENABLED", False)
    c = TestClient(a)
    assert all(c.post("/chat").status_code == 200 for _ in range(10))


def test_postgres_counter_is_shared(pg_client):
    async def go():
        one, two = rl.PostgresCounter(pg_client), rl.PostgresCounter(pg_client)
        key = f"chat:{uuid.uuid4()}"
        assert await one.hit(key, 60) == 1
        assert await two.hit(key, 60) == 2
    asyncio.run(go())


def test_counter_failure_lets_request_through(app, monkeypatch):
    a, _ = app

    class Broken:
        async def hit(self, key, window):
            raise RuntimeError("db down")

    monkeypatch.setattr(rl, "_counter", Broken())
    assert TestClient(a).post("/chat").status_code == 200


def test_expensive_endpoints_are_limited():
    from main import app as real

    limited = {r.path for r in real.routes
               if any(getattr(d.dependency, "__qualname__", "").startswith("rate_limit")
                      for d in getattr(r, "dependencies", []))}
    for path in ("/api/v1/chat/stream", "/api/v1/chat/message", "/api/v1/mcq/generate",
                 "/api/v1/notes/generate", "/api/v1/documents/upload", "/api/v1/learning/visualize"):
        assert path in limited, path
