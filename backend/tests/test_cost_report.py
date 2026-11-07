"""The admin AI cost dashboard numbers (real Postgres)."""

import asyncio
import uuid

from db.client import SupabaseClient
from services import cost_report


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg


def test_report_totals_breakdowns_and_hit_rate(pg_client, monkeypatch):
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(pg_client))
    u = str(uuid.uuid4())
    pg_client.table("app_users").insert({"id": u, "email": "kid@example.com"}).execute()
    rows = [
        {"user_id": u, "feature": "chat", "kind": "llm", "model": "small-m", "role": "small",
         "input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.01, "latency_ms": 800},
        {"user_id": u, "feature": "chat", "kind": "embedding", "model": "emb", "role": "embedding",
         "input_tokens": 10, "cost_usd": 0.0001, "latency_ms": 50},
        {"user_id": u, "feature": "quiz", "kind": "llm", "model": "small-m", "role": "small",
         "input_tokens": 3000, "output_tokens": 1500, "cost_usd": 0.03, "latency_ms": 2000, "ok": False},
        {"user_id": u, "feature": "quiz", "kind": "cache", "model": "cache", "role": "pool",
         "cache_hit": True, "saved_usd": 0.03},
        {"user_id": u, "feature": "chat", "kind": "cache", "model": "cache", "role": "answer",
         "cache_hit": True, "saved_usd": 0.01},
    ]
    pg_client.table("ai_calls").insert(rows).execute()
    out = asyncio.run(cost_report.report(7))
    t = out["totals"]
    assert t["calls"] == 3 and t["cache_hits"] == 2 and t["llm_calls"] == 2 and t["errors"] == 1
    assert abs(t["cost_usd"] - 0.0401) < 1e-6 and abs(t["saved_usd"] - 0.04) < 1e-6
    assert t["cache_hit_rate"] == 0.5
    quiz = next(f for f in out["by_feature"] if f["feature"] == "quiz")
    assert quiz["cache_hit_rate"] == 0.5 and quiz["llm_calls"] == 1
    assert out["by_model"][0]["model"] == "small-m" and out["by_model"][0]["calls"] == 2
    assert out["by_user"][0]["email"] == "kid@example.com"
    assert len(out["daily"]) == 1
