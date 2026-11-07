"""Per-plan monthly AI token caps (a safety net on top of feature limits)."""

import asyncio

import pytest

from services import usage_service as us
from services.plans import monthly_token_cap
from services.usage_service import LimitReached, UsageService


def run(c):
    return asyncio.run(c)


@pytest.fixture
def svc(monkeypatch):
    s = UsageService()
    state = {"plan": {"plan": "free", "status": "active"}, "tokens": 0, "added": []}

    async def plan_row(user_id):
        return state["plan"]

    async def month_tokens(user_id):
        return state["tokens"]

    async def add(user_id, feature, amount, limit):
        state["added"].append((feature, amount))
        return amount
    monkeypatch.setattr(s, "plan_row", plan_row)
    monkeypatch.setattr(s, "month_tokens", month_tokens)
    monkeypatch.setattr(s, "_add", add)
    monkeypatch.setattr(us.settings, "PLAN_LIMITS_ENABLED", True)
    return s, state


def test_under_the_cap_is_allowed(svc):
    s, state = svc
    state["tokens"] = monthly_token_cap("free") - 1
    run(s.consume("u", "chat"))
    assert state["added"] == [("chat", 1)]


def test_over_the_cap_blocks_with_a_clear_reason(svc):
    s, state = svc
    state["tokens"] = monthly_token_cap("free")
    with pytest.raises(LimitReached) as e:
        run(s.consume("u", "chat"))
    assert e.value.status_code == 402 and e.value.detail["feature"] == "ai_tokens"
    assert e.value.detail["resets_at"]            # resets next month
    with pytest.raises(LimitReached):
        run(s.check("u", "questions"))
    assert state["added"] == []


def test_paid_plans_have_higher_caps_and_unlimited_accounts_skip(svc):
    s, state = svc
    assert monthly_token_cap("topper") > monthly_token_cap("scholar") > monthly_token_cap("free")
    state["tokens"] = monthly_token_cap("free") + 1
    state["plan"] = {"plan": "topper", "status": "active"}
    run(s.consume("u", "chat"))
    state["plan"] = {"plan": "free", "status": "active", "unlimited": True}
    state["tokens"] = 10 ** 12
    run(s.consume("u", "chat"))


def test_caps_off_when_plan_limits_are_off(svc, monkeypatch):
    s, state = svc
    state["tokens"] = 10 ** 12
    monkeypatch.setattr(us.settings, "PLAN_LIMITS_ENABLED", False)
    run(s.consume("u", "chat"))


def test_database_trouble_fails_open(svc, monkeypatch):
    s, state = svc

    async def boom(user_id):
        raise RuntimeError("db down")
    monkeypatch.setattr(s, "month_tokens", boom)
    run(s.consume("u", "chat"))
