"""AI-call telemetry: cost estimates, rows for every call kind, never breaking a call."""

import asyncio
from types import SimpleNamespace

import pytest

from services import telemetry as t
from services.telemetry import estimate_cost, telemetry


def run(c):
    return asyncio.run(c)


@pytest.fixture
def prices(monkeypatch):
    s = t.settings
    for k, v in {"SMALL_LLM_PRICE_INPUT": 0.4, "SMALL_LLM_PRICE_OUTPUT": 1.6, "SMALL_LLM_PRICE_CACHED_INPUT": 0.1,
                 "BIG_LLM_PRICE_INPUT": 2.0, "BIG_LLM_PRICE_OUTPUT": 8.0, "BIG_LLM_PRICE_CACHED_INPUT": -1.0,
                 "EMBEDDING_PRICE_INPUT": 0.02, "RERANK_PRICE_PER_CALL": 0.002}.items():
        monkeypatch.setattr(s, k, v)


def test_cost_estimates(prices):
    assert estimate_cost("small", 1_000_000, 0) == pytest.approx(0.4)
    assert estimate_cost("small", 1_000_000, 1_000_000, cached_tokens=500_000) == pytest.approx(0.05 + 0.2 + 1.6)
    assert estimate_cost("big", 1_000_000, 0, cached_tokens=1_000_000) == pytest.approx(2.0)   # cached = input price
    assert estimate_cost("embedding", 1_000_000) == pytest.approx(0.02)
    assert estimate_cost("rerank") == pytest.approx(0.002)


def test_unknown_prices_cost_nothing():
    assert estimate_cost("small", 10_000, 10_000) == 0.0


def test_record_reads_user_and_feature(prices):
    from services.usage_service import current_feature, current_user_id
    current_user_id.set("u1")
    current_feature.set("quiz")
    try:
        telemetry.record("llm", "m", role="small", input_tokens=1000, output_tokens=500, latency_ms=42)
        telemetry.record_hit("pool", saved_usd=0.01)
    finally:
        current_user_id.set(None)
        current_feature.set("other")
    call, hit = telemetry._buffer
    assert call["user_id"] == "u1" and call["feature"] == "quiz" and call["latency_ms"] == 42
    assert call["cost_usd"] == pytest.approx(0.0012)
    assert hit["cache_hit"] is True and hit["cost_usd"] == 0 and hit["saved_usd"] == 0.01 and hit["role"] == "pool"


def test_flush_writes_rows_and_survives_db_errors(monkeypatch):
    written = []

    class Q:
        def __init__(self, rows): self.rows = rows
        def execute(self): written.extend(self.rows)

    class C:
        def table(self, name):
            assert name == "ai_calls"
            return SimpleNamespace(insert=lambda rows: Q(rows))

    import db.client
    monkeypatch.setattr(db.client, "get_supabase_client", lambda: C())
    telemetry.record("llm", "m", role="small")
    assert run(telemetry.flush()) == 1 and len(written) == 1 and telemetry._buffer == []

    monkeypatch.setattr(db.client, "get_supabase_client", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    telemetry.record("llm", "m", role="small")
    assert run(telemetry.flush()) == 1     # dropped quietly, no exception


def test_llm_calls_are_recorded_including_failures(monkeypatch):
    from services import llm_service as ls

    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20,
                            prompt_tokens_details=SimpleNamespace(cached_tokens=64))
    resp = SimpleNamespace(usage=usage, choices=[SimpleNamespace(
        message=SimpleNamespace(content="A long enough answer here."), finish_reason="stop")])

    async def ok(client, kwargs):
        return resp

    async def no_usage_db(*a, **k):
        return None
    monkeypatch.setattr(ls, "_create", ok)
    monkeypatch.setattr("services.usage_service.usage.record_tokens", no_usage_db)
    run(ls.llm_service.chat_completion([{"role": "user", "content": "hi"}]))
    row = telemetry._buffer[-1]
    assert (row["kind"], row["input_tokens"], row["output_tokens"], row["cached_tokens"], row["ok"]) == \
        ("llm", 100, 20, 64, True)

    async def boom(client, kwargs):
        raise RuntimeError("provider down")
    monkeypatch.setattr(ls, "_create", boom)
    with pytest.raises(RuntimeError):
        run(ls.llm_service.chat_completion([{"role": "user", "content": "hi"}]))
    assert telemetry._buffer[-1]["ok"] is False


def test_langfuse_is_sent_only_with_keys(monkeypatch):
    sent = []

    async def fake_send(rows):
        sent.append(len(rows))
    monkeypatch.setattr(telemetry, "_send_langfuse", fake_send)
    import db.client
    monkeypatch.setattr(db.client, "get_supabase_client", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    telemetry.record("llm", "m")
    run(telemetry.flush())
    assert sent == []
    monkeypatch.setattr(t.settings, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(t.settings, "LANGFUSE_SECRET_KEY", "sk")
    telemetry.record("llm", "m")
    run(telemetry.flush())
    assert sent == [1]
