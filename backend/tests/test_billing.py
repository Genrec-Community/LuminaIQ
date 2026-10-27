"""Personal plans: exact term dates, one-time payments applied once, plan switches, models per plan."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from services import billing_service as bsvc
from services.billing_service import add_months, parse_time
from services.usage_service import usage
from tests.fake_supabase import FakeClient

UTC = timezone.utc


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(bsvc.billing, "client", fake)
    monkeypatch.setattr(usage, "client", fake)
    usage._plans.clear()
    return fake


def _plan(db, user_id):
    return next(r for r in db.tables["user_plans"] if r["user_id"] == user_id)


# ----------------------------------------------------------------- dates

def test_add_months_keeps_time_and_clamps_day():
    t = datetime(2027, 1, 31, 18, 30, tzinfo=UTC)
    assert add_months(t, 1) == datetime(2027, 2, 28, 18, 30, tzinfo=UTC)
    assert add_months(datetime(2028, 1, 31, tzinfo=UTC), 1) == datetime(2028, 2, 29, tzinfo=UTC)
    assert add_months(datetime(2027, 3, 15, tzinfo=UTC), 12) == datetime(2028, 3, 15, tzinfo=UTC)
    assert add_months(datetime(2027, 11, 30, tzinfo=UTC), 3) == datetime(2028, 2, 29, tzinfo=UTC)


def test_parse_time_handles_supabase_formats():
    assert parse_time("2027-01-01T00:00:00Z") == datetime(2027, 1, 1, tzinfo=UTC)
    assert parse_time("2027-01-01T05:30:00+05:30") == datetime(2027, 1, 1, tzinfo=UTC)
    assert parse_time("2027-01-01T00:00:00") == datetime(2027, 1, 1, tzinfo=UTC)
    assert parse_time("nonsense") is None and parse_time(None) is None


# ----------------------------------------------------------- term rules

def test_new_term_starts_now():
    now = datetime(2027, 5, 10, 9, 0, tzinfo=UTC)
    term = bsvc.billing.prepaid_term({}, "scholar", "monthly", now=now)
    assert term["start"] == now and term["end"] == datetime(2027, 6, 10, 9, 0, tzinfo=UTC)
    yearly = bsvc.billing.prepaid_term({}, "topper", "yearly", now=now)
    assert yearly["end"] == datetime(2028, 5, 10, 9, 0, tzinfo=UTC)


def test_same_plan_bought_early_stacks_on_current_end():
    now = datetime(2027, 5, 10, tzinfo=UTC)
    current = {"plan": "scholar", "source": "razorpay", "status": "active",
               "current_period_end": "2027-05-20T00:00:00+00:00"}
    term = bsvc.billing.prepaid_term(current, "scholar", "monthly", now=now)
    assert term["start"] == datetime(2027, 5, 20, tzinfo=UTC)
    assert term["end"] == datetime(2027, 6, 20, tzinfo=UTC)


def test_switching_plan_converts_days_left():
    now = datetime(2027, 5, 10, tzinfo=UTC)
    current = {"plan": "topper", "source": "razorpay", "status": "active",
               "current_period_end": (now + timedelta(days=10)).isoformat()}
    # 10 Topper days (999/month) are worth ~33.4 Scholar days (299/month)
    term = bsvc.billing.prepaid_term(current, "scholar", "monthly", now=now)
    assert term["start"] == now
    assert term["credit"] == timedelta(seconds=int(10 * 86400 * 999 / 299))
    up = bsvc.billing.prepaid_term({**current, "plan": "scholar"}, "topper", "monthly", now=now)
    assert up["credit"] == timedelta(seconds=int(10 * 86400 * 299 / 999))


def test_expired_plan_gives_no_credit():
    now = datetime(2027, 5, 10, tzinfo=UTC)
    current = {"plan": "topper", "source": "razorpay", "status": "active",
               "current_period_end": (now - timedelta(days=1)).isoformat()}
    term = bsvc.billing.prepaid_term(current, "scholar", "monthly", now=now)
    assert term["start"] == now and term["credit"] == timedelta(0)


# ------------------------------------------------ payments applied once

def _record(db, user_id, plan="scholar:monthly", amount=29900, order="order_1"):
    row = {"user_id": user_id, "kind": "plan", "plan": plan, "amount_paise": amount,
           "status": "created", "razorpay_order_id": order}
    db.tables.setdefault("payments", []).append(dict(row, id=order))
    return row


def test_one_time_payment_applies_once_and_sets_plan(db):
    from api.v1.endpoints.billing import _apply_plan

    rec = _record(db, "u1")
    run(_apply_plan(rec, "pay_1", "order_1"))
    run(_apply_plan(rec, "pay_1", "order_1", raw={"amount": 29900}))  # webhook after /verify
    row = _plan(db, "u1")
    end = parse_time(row["current_period_end"])
    start = parse_time(row["current_period_start"])
    assert row["plan"] == "scholar" and row["source"] == "razorpay" and row["razorpay_subscription_id"] is None
    assert end == add_months(start, 1)  # one month, not two
    paid = [p for p in db.tables["payments"] if p["status"] == "paid"]
    assert len(paid) == 1 and paid[0]["period_end"] == row["current_period_end"]
    usage.forget("u1")
    assert run(usage.plan("u1")) == "scholar"
    summary = run(usage.summary("u1"))
    assert summary["auto_renew"] is False and summary["billing_cycle"] == "monthly"


def test_underpaid_order_is_not_applied(db):
    from api.v1.endpoints.billing import _apply_plan

    rec = _record(db, "u2", plan="topper:yearly", amount=849900)
    run(_apply_plan(rec, "pay_2", "order_1", raw={"amount": 100}))
    assert not [r for r in db.tables.get("user_plans", []) if r["user_id"] == "u2"]
    assert [p for p in db.tables["payments"] if p.get("razorpay_payment_id") == "pay_2"][0]["status"] == "failed"


def test_second_month_extends_from_end(db):
    from api.v1.endpoints.billing import _apply_plan

    run(_apply_plan(_record(db, "u3", order="o1"), "pay_a", "o1"))
    first_end = parse_time(_plan(db, "u3")["current_period_end"])
    first_start = _plan(db, "u3")["current_period_start"]
    run(_apply_plan(_record(db, "u3", order="o2"), "pay_b", "o2"))
    row = _plan(db, "u3")
    assert parse_time(row["current_period_end"]) == add_months(first_end, 1)
    assert row["current_period_start"] == first_start  # the period keeps its start


def test_pass_applies_once(db):
    from api.v1.endpoints.billing import _apply_pass

    rec = {"user_id": "u4", "kind": "pass", "plan": "topper", "amount_paise": 4900}
    run(_apply_pass(rec, "pay_p", "op"))
    run(_apply_pass(rec, "pay_p", "op"))
    until = parse_time(_plan(db, "u4")["pass_until"])
    assert timedelta(hours=47) < until - datetime.now(UTC) <= timedelta(hours=48)


# -------------------------------------------------------- reading plans

def test_grace_only_for_renewing_subscriptions(db):
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    db.tables["user_plans"] = [
        {"user_id": "sub", "plan": "topper", "status": "active", "source": "razorpay",
         "current_period_end": past, "razorpay_subscription_id": "sub_1", "cancel_at_period_end": False},
        {"user_id": "once", "plan": "topper", "status": "active", "source": "razorpay",
         "current_period_end": past, "razorpay_subscription_id": None},
    ]
    assert run(usage.plan("sub")) == "topper"   # renewal charge may still land
    assert run(usage.plan("once")) == "free"    # one-time term is over


def test_school_students_cannot_buy_personal_plans(db, monkeypatch):
    from api.v1.endpoints import billing as ep

    monkeypatch.setattr(ep.rzp, "configured", lambda: True)
    with pytest.raises(HTTPException) as e:
        run(ep.checkout(ep.CheckoutRequest(plan="scholar", cycle="monthly"),
                        current_user={"id": "kid", "managed": True}))
    assert e.value.status_code == 409


# ------------------------------------------------------- model per plan

def test_model_follows_plan(monkeypatch):
    from services import llm_service as llm
    from services.usage_service import current_plan

    monkeypatch.setattr(llm, "_use_azure", lambda: False)
    monkeypatch.setattr(llm.settings, "LLM_MODEL", "base")
    monkeypatch.setattr(llm.settings, "LLM_LIGHT_MODEL", "light")
    monkeypatch.setattr(llm.settings, "LLM_DEEP_MODEL", "deep")
    monkeypatch.setattr(llm.settings, "LLM_TIER_MODELS", "free=small, topper=big ,bad")
    assert llm.tier_models() == {"free": "small", "topper": "big"}
    assert llm.resolve_model(plan="free") == "small"
    assert llm.resolve_model(plan="topper") == "big"
    assert llm.resolve_model(plan="scholar") == "base"            # not listed
    assert llm.resolve_model(plan="scholar", light=True) == "light"
    assert llm.resolve_model(plan="topper", deep=True) == "deep"
    token = current_plan.set("free")
    try:
        assert llm.resolve_model() == "small"                      # from the request
    finally:
        current_plan.reset(token)
    assert llm.resolve_model() == "base"                           # no signed-in user
