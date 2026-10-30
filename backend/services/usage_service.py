"""
Usage metering and plan enforcement.

    await usage.consume(user_id, "chat")            # check + count atomically
    await usage.check(user_id, "visual")            # check only (charge after a cache miss)
    await usage.charge(user_id, "visual")           # count without a check
    await usage.check_books(user_id)                # before an upload / import

Over the limit → HTTP 402 with a structured detail the frontend turns into an
upgrade prompt. If the billing tables are missing or the database hiccups,
metering fails open: students are never blocked by our own outage.

Token usage of every LLM call is also recorded per user/day/model
(llm_usage_daily) through record_tokens(), so real costs can be measured.
"""

from __future__ import annotations

import contextvars
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from config.settings import settings
from db.client import async_db, get_supabase_client
from services.plans import (FEATURE_LABELS, FEATURE_NAMES, FEATURE_PERIOD, PLANS, RENEWAL_GRACE,
                           plan_limits as _plan_limits)
from utils.logger import logger

# Who the current request is for; read by the LLM token recorder
current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_user_id", default=None)
current_feature: contextvars.ContextVar[str] = contextvars.ContextVar("current_feature", default="other")
# The signed-in user's plan for this request (set in api/deps.py); picks the LLM model
current_plan: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_plan", default=None)

_PLAN_TTL = 60  # seconds a resolved plan is cached in-process


def plan_limits(plan: str) -> Dict[str, Optional[int]]:
    """The limits in force: none at all while PLAN_LIMITS_ENABLED is off."""
    return _plan_limits(plan) if getattr(settings, "PLAN_LIMITS_ENABLED", False) else {}


def _tz():
    try:
        return ZoneInfo(getattr(settings, "PLAN_TIMEZONE", "") or "Asia/Kolkata")
    except Exception:
        # Slim images may lack the tz database; India has no DST
        return timezone(timedelta(hours=5, minutes=30))


def period_key(feature: str, now: Optional[datetime] = None) -> str:
    now = now or datetime.now(_tz())
    kind = FEATURE_PERIOD.get(feature, "day")
    if kind == "day":
        return f"d:{now:%Y-%m-%d}"
    if kind == "month":
        return f"m:{now:%Y-%m}"
    return "t"


def resets_at(feature: str, now: Optional[datetime] = None) -> Optional[str]:
    now = now or datetime.now(_tz())
    kind = FEATURE_PERIOD.get(feature, "day")
    if kind == "day":
        nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif kind == "month":
        nxt = (now.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return None
    return nxt.isoformat()


class LimitReached(HTTPException):
    def __init__(self, plan: str, feature: str, limit: int, used: int):
        super().__init__(402, {
            "code": "limit_reached",
            "plan": plan,
            "plan_name": PLANS.get(plan, PLANS["free"])["name"],
            "feature": feature,
            "label": FEATURE_LABELS.get(feature, feature),
            "limit": limit,
            "used": used,
            "resets_at": resets_at(feature),
            "message": (
                f"{FEATURE_NAMES.get(feature, feature)} aren't included in the "
                f"{PLANS.get(plan, PLANS['free'])['name']} plan."
                if limit == 0 else
                f"You've used all {limit} {FEATURE_LABELS.get(feature, feature)} on the "
                f"{PLANS.get(plan, PLANS['free'])['name']} plan."
            ),
        })


class UsageService:
    def __init__(self):
        self.client = get_supabase_client()
        self._plans: Dict[str, tuple] = {}  # user_id -> (expires, plan_row)

    # ---------------------------------------------------------------- plans

    async def plan_row(self, user_id: str) -> Dict[str, Any]:
        cached = self._plans.get(user_id)
        if cached and cached[0] > time.time():
            return cached[1]
        row = {"plan": "free", "status": "active", "source": "default"}
        try:
            res = await async_db(lambda: self.client.table("user_plans")
                                 .select("*").eq("user_id", user_id).limit(1).execute())
            if res.data:
                r = res.data[0]
                end = r.get("current_period_end")
                active = r.get("status") in ("active", "authenticated", "trialing")
                if end:
                    try:
                        ends = datetime.fromisoformat(end.replace("Z", "+00:00"))
                        if r.get("razorpay_subscription_id") and not r.get("cancel_at_period_end"):
                            ends += RENEWAL_GRACE  # the renewal charge may land a little late
                        active = active and ends > datetime.now(timezone.utc)
                    except ValueError:
                        pass
                if active and r.get("plan") in PLANS:
                    row = r
                # An institution plan only applies while the school is approved and paid up
                if row.get("source") == "institution" and row.get("institution_id"):
                    from services.institution_service import institutions
                    if not await institutions.plan_is_live(row["institution_id"]):
                        row = {"plan": "free", "status": "active", "source": "default"}
                # An Exam Night Pass lifts anyone below Topper to Topper until it ends
                pass_until = r.get("pass_until")
                if pass_until and row["plan"] != "topper":
                    try:
                        until = datetime.fromisoformat(pass_until.replace("Z", "+00:00"))
                        if until > datetime.now(timezone.utc):
                            row = {**r, "plan": "topper", "status": "active", "source": "pass",
                                   "current_period_end": pass_until, "underlying_plan": row["plan"]}
                    except ValueError:
                        pass
        except Exception as e:
            logger.debug(f"Plan lookup failed, treating as free: {e}")
        # Testers and staff on the unlimited-access list (migration 016) skip every
        # limit, whatever their plan
        try:
            res = await async_db(lambda: self.client.rpc("is_unlimited", {"p_user": user_id}).execute())
            if res.data is True:
                row = {**row, "unlimited": True}
        except Exception as e:
            logger.debug(f"Unlimited-access check skipped: {e}")
        self._plans[user_id] = (time.time() + _PLAN_TTL, row)
        return row

    async def plan(self, user_id: str) -> str:
        return (await self.plan_row(user_id))["plan"]

    async def limits(self, user_id: str) -> Dict[str, Optional[int]]:
        """Limits for this user: none for accounts on the unlimited-access list."""
        row = await self.plan_row(user_id)
        return {} if row.get("unlimited") else plan_limits(row["plan"])

    def forget(self, user_id: str) -> None:
        """Drop the cached plan (after a purchase or cancellation)."""
        self._plans.pop(user_id, None)

    # ------------------------------------------------------------- counters

    async def _used(self, user_id: str, feature: str) -> int:
        res = await async_db(lambda: self.client.table("usage_counters").select("count")
                             .eq("user_id", user_id).eq("feature", feature)
                             .eq("period", period_key(feature)).limit(1).execute())
        return int(res.data[0]["count"]) if res.data else 0

    async def _add(self, user_id: str, feature: str, amount: int, limit: Optional[int]) -> int:
        res = await async_db(lambda: self.client.rpc("consume_usage", {
            "p_user": user_id, "p_feature": feature, "p_period": period_key(feature),
            "p_amount": amount, "p_limit": -1 if limit is None else limit,
        }).execute())
        return int(res.data) if res.data is not None else 0

    async def consume(self, user_id: str, feature: str, amount: int = 1) -> None:
        """Atomically count `amount` uses, or raise LimitReached."""
        if not user_id or amount <= 0:
            return
        plan = await self.plan(user_id)
        limit = (await self.limits(user_id)).get(feature)
        try:
            new_count = await self._add(user_id, feature, amount, limit)
        except Exception as e:
            logger.debug(f"Usage metering unavailable ({feature}): {e}")
            return
        if new_count < 0:
            used = 0
            try:
                used = await self._used(user_id, feature)
            except Exception:
                pass
            raise LimitReached(plan, feature, limit or 0, used)

    async def check(self, user_id: str, feature: str, amount: int = 1) -> None:
        """Raise LimitReached if `amount` more uses would exceed the plan."""
        if not user_id:
            return
        plan = await self.plan(user_id)
        limit = (await self.limits(user_id)).get(feature)
        if limit is None:
            return
        try:
            used = await self._used(user_id, feature)
        except Exception as e:
            logger.debug(f"Usage check unavailable ({feature}): {e}")
            return
        if used + amount > limit:
            raise LimitReached(plan, feature, limit, used)

    async def charge(self, user_id: str, feature: str, amount: int = 1) -> None:
        """Count uses after the fact (work already done, never raises)."""
        if not user_id or amount <= 0:
            return
        try:
            await self._add(user_id, feature, amount, None)
        except Exception as e:
            logger.debug(f"Usage charge skipped ({feature}): {e}")

    async def count_books(self, user_id: str) -> int:
        projects = await async_db(lambda: self.client.table("projects")
                                  .select("id").eq("user_id", user_id).execute())
        ids = [p["id"] for p in projects.data or []]
        if not ids:
            return 0
        docs = await async_db(lambda: self.client.table("documents").select("id", count="exact")
                              .in_("project_id", ids).neq("upload_status", "failed").execute())
        return docs.count or 0

    async def check_books(self, user_id: str, adding: int = 1) -> None:
        plan = await self.plan(user_id)
        limit = (await self.limits(user_id)).get("books")
        if limit is None:
            return
        try:
            used = await self.count_books(user_id)
        except Exception as e:
            logger.debug(f"Book count unavailable: {e}")
            return
        if used + adding > limit:
            raise LimitReached(plan, "books", limit, used)

    # -------------------------------------------------------------- summary

    async def summary(self, user_id: str) -> Dict[str, Any]:
        row = await self.plan_row(user_id)
        plan = row["plan"]
        limits = {} if row.get("unlimited") else plan_limits(plan)
        usage: Dict[str, Any] = {}
        for feature in FEATURE_PERIOD:
            try:
                used = await (self.count_books(user_id) if feature == "books" else self._used(user_id, feature))
            except Exception:
                used = 0
            usage[feature] = {
                "used": used,
                "limit": limits.get(feature),
                "label": FEATURE_LABELS[feature],
                "resets_at": resets_at(feature),
            }
        return {
            "plan": plan,
            "plan_name": PLANS[plan]["name"],
            "status": row.get("status"),
            "source": row.get("source"),
            "current_period_end": row.get("current_period_end"),
            "cancel_at_period_end": row.get("cancel_at_period_end", False),
            "current_period_start": row.get("current_period_start"),
            "billing_cycle": row.get("billing_cycle"),
            # Renews by itself (Razorpay subscription) or ends unless paid again (one-time)
            "auto_renew": bool(row.get("source") == "razorpay" and row.get("razorpay_subscription_id")
                               and not row.get("cancel_at_period_end")),
            "pass_until": row.get("pass_until"),
            "institution_id": row.get("institution_id"),
            "usage": usage,
            "limits_enabled": bool(getattr(settings, "PLAN_LIMITS_ENABLED", False)) and not row.get("unlimited"),
            "unlimited": bool(row.get("unlimited")),
        }

    # --------------------------------------------------------------- tokens

    async def record_tokens(self, model: str, input_tokens: int, output_tokens: int) -> None:
        # Read context here: the DB call below runs on a worker thread without it
        user_id = current_user_id.get()
        feature = current_feature.get()
        if not (input_tokens or output_tokens):
            return
        try:
            day = datetime.now(_tz()).date().isoformat()
            await async_db(lambda: self.client.rpc("add_llm_usage", {
                "p_user": user_id, "p_day": day, "p_model": model or "unknown",
                "p_feature": feature,
                "p_input": int(input_tokens or 0), "p_output": int(output_tokens or 0),
            }).execute())
        except Exception as e:
            logger.debug(f"Token usage not recorded: {e}")


usage = UsageService()


def metered(user: dict, feature: str) -> None:
    """Tag the current request so LLM token usage is attributed to it."""
    current_user_id.set(user.get("id") if user else None)
    current_feature.set(feature)
