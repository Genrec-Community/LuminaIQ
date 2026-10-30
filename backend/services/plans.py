"""
Subscription plans and their limits.

Limits are per user. None = unlimited. "Daily" limits reset at midnight in
PLAN_TIMEZONE (India by default); "monthly" limits on the 1st.

Metered features
  chat       chat answers (daily)
  deep       Deep-model answers and cram cards (monthly; Topper only)
  questions  quiz + Power Hour questions generated (daily)
  tools      notes, flashcards, mindmaps, topic summaries, graded answers (daily)
  cram       Exam Tonight cram cards generated (monthly; cached/shared ones are free)
  visual     Visual Lab simulations built (monthly; cached/shared/repairs are free)
  books      documents across all of the user's projects (total)
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

FEATURE_PERIOD = {
    "chat": "day",
    "questions": "day",
    "tools": "day",
    "deep": "month",
    "cram": "month",
    "visual": "month",
    "books": "total",
}

# Short names for "not included in your plan" messages
FEATURE_NAMES = {
    "chat": "Chat answers", "questions": "Quiz questions", "tools": "Study tools",
    "deep": "Deep answers", "cram": "Cram cards", "visual": "Visual Lab builds", "books": "More books",
}

FEATURE_LABELS = {
    "chat": "chat answers today",
    "questions": "quiz and Power Hour questions today",
    "tools": "notes, flashcards and summaries today",
    "deep": "Deep answers this month",
    "cram": "cram cards this month",
    "visual": "Visual Lab builds this month",
    "books": "books",
}

PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "Free",
        "price_inr": 0,
        "limits": {"chat": 20, "questions": 60, "tools": 20, "deep": 0,
                   "cram": 30, "visual": 3, "books": 3},
    },
    "scholar": {
        "name": "Scholar",
        "price_inr": 299,
        "price_inr_yearly": 2499,
        "limits": {"chat": 60, "questions": 300, "tools": 60, "deep": 0,
                   "cram": 300, "visual": 15, "books": 15},
    },
    "topper": {
        "name": "Topper",
        "price_inr": 999,
        "price_inr_yearly": 8499,
        # "Unlimited" features still have a fair-use ceiling so one account
        # can't run up unbounded AI costs
        "limits": {"chat": 100, "questions": 1000, "tools": 150, "deep": 200,
                   "cram": 1000, "visual": 40, "books": None},
    },
    "institution": {
        "name": "Institution",
        "price_inr": 179,          # per seat per month (+ GST once INSTITUTION_GSTIN is set)
        "limits": {"chat": 60, "questions": 500, "tools": 100, "deep": 50,
                   "cram": 500, "visual": 15, "books": None},
    },
}

# Paid personal plans (bought by students themselves)
PAID_PLANS = ("scholar", "topper")

# A renewing subscription's charge can land a little after the period ends:
# access continues this long past current_period_end while Razorpay retries.
RENEWAL_GRACE = timedelta(days=2)

# One-time 48-hour pass that unlocks Topper features
EXAM_NIGHT_PASS = {"name": "Exam Night Pass", "price_inr": 49, "hours": 48, "plan": "topper"}


def plan_price(plan: str, cycle: str) -> int:
    """Price in rupees for one term of a paid plan."""
    p = PLANS[plan]
    return p["price_inr"] if cycle == "monthly" else p["price_inr_yearly"]


def plan_limits(plan: str) -> Dict[str, Optional[int]]:
    return PLANS.get(plan, PLANS["free"])["limits"]


def public_catalog() -> Dict[str, Any]:
    """What the pricing page shows."""
    return {
        "plans": {
            key: {k: v for k, v in p.items() if k != "limits"} | {"limits": p["limits"]}
            for key, p in PLANS.items()
        },
        "exam_night_pass": EXAM_NIGHT_PASS,
        "labels": FEATURE_LABELS,
    }
