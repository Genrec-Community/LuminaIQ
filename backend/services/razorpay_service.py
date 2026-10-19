"""
Razorpay: subscriptions (Scholar / Topper, monthly or yearly), one-time orders
(Exam Night Pass, institution seats), signature checks and webhook handling.

Uses the REST API directly (https://razorpay.com/docs/api/) with httpx; no SDK.
Amounts are in paise and are what the customer pays (GST-inclusive pricing).
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict, Optional

import httpx

from config.settings import settings
from utils.logger import logger

API = "https://api.razorpay.com/v1"


class RazorpayNotConfigured(Exception):
    pass


def configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def plan_id(plan: str, cycle: str) -> str:
    return getattr(settings, f"RAZORPAY_PLAN_{plan.upper()}_{cycle.upper()}", "") or ""


async def _request(method: str, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not configured():
        raise RazorpayNotConfigured()
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.request(
            method, f"{API}{path}", json=json,
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        )
    if r.status_code >= 400:
        logger.error(f"Razorpay {method} {path} -> {r.status_code}: {r.text[:500]}")
        r.raise_for_status()
    return r.json()


async def create_subscription(plan: str, cycle: str, notes: Dict[str, str]) -> Dict[str, Any]:
    pid = plan_id(plan, cycle)
    if not pid:
        raise RazorpayNotConfigured()
    return await _request("POST", "/subscriptions", {
        "plan_id": pid,
        # How many billing cycles the mandate covers (renews automatically)
        "total_count": 120 if cycle == "monthly" else 10,
        "customer_notify": 1,
        "notes": notes,
    })


async def cancel_subscription(subscription_id: str, at_cycle_end: bool = True) -> Dict[str, Any]:
    return await _request("POST", f"/subscriptions/{subscription_id}/cancel",
                          {"cancel_at_cycle_end": 1 if at_cycle_end else 0})


async def fetch_subscription(subscription_id: str) -> Dict[str, Any]:
    return await _request("GET", f"/subscriptions/{subscription_id}")


async def create_order(amount_paise: int, receipt: str, notes: Dict[str, str]) -> Dict[str, Any]:
    return await _request("POST", "/orders", {
        "amount": amount_paise, "currency": "INR", "receipt": receipt[:40], "notes": notes,
    })


async def list_invoices(subscription_id: str) -> Dict[str, Any]:
    return await _request("GET", f"/invoices?subscription_id={subscription_id}&count=24")


def _hmac(message: str, secret: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_subscription_payment(payment_id: str, subscription_id: str, signature: str) -> bool:
    expected = _hmac(f"{payment_id}|{subscription_id}", settings.RAZORPAY_KEY_SECRET)
    return hmac.compare_digest(expected, signature or "")


def verify_order_payment(order_id: str, payment_id: str, signature: str) -> bool:
    expected = _hmac(f"{order_id}|{payment_id}", settings.RAZORPAY_KEY_SECRET)
    return hmac.compare_digest(expected, signature or "")


def verify_webhook(body: bytes, signature: str) -> bool:
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
