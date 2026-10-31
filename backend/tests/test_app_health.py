"""Liveness, readiness, request ids and the production secrets check."""

import pytest
from fastapi.testclient import TestClient

from config.settings import Settings
from db.client import SupabaseClient
from tests.fake_supabase import FakeClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(SupabaseClient, "_instance", FakeClient())
    from main import app

    return TestClient(app, raise_server_exceptions=False)


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_response_has_request_id(client):
    assert client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) >= 16


def test_request_id_is_in_log_records(client):
    import logging

    from utils.logger import RequestIdFilter, request_id_var

    token = request_id_var.set("rid-42")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
        RequestIdFilter().filter(record)
        assert record.request_id == "rid-42"
    finally:
        request_id_var.reset(token)


def test_ready_ok_when_supabase_answers(client):
    res = client.get("/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["checks"]["supabase"] == "ok"
    # Optional services that aren't configured are reported, not failed
    assert body["checks"]["vector_db"] == "not configured"
    assert body["checks"]["redis"] == "not configured"


def test_ready_503_when_supabase_fails(client, monkeypatch):
    class Broken(FakeClient):
        def table(self, name):
            raise RuntimeError("down")

    monkeypatch.setattr(SupabaseClient, "_instance", Broken())
    res = client.get("/ready")
    assert res.status_code == 503
    assert res.json()["checks"]["supabase"].startswith("error")


def test_validate_production_rejects_default_secrets():
    s = Settings(ENVIRONMENT="production", SECRET_KEY="supersecretkey")
    with pytest.raises(RuntimeError) as e:
        s.validate_production()
    msg = str(e.value)
    assert "SECRET_KEY" in msg and "WEBHOOK_SECRET" in msg and "MAIN_API_WEBHOOK_SECRET" in msg


def test_validate_production_allows_dev_defaults():
    Settings(ENVIRONMENT="development", SECRET_KEY="supersecretkey").validate_production()


def test_validate_production_passes_with_real_secrets():
    Settings(ENVIRONMENT="production", SECRET_KEY="a" * 40, WEBHOOK_SECRET="w" * 32,
             MAIN_API_WEBHOOK_SECRET="m" * 32).validate_production()
