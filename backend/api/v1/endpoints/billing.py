"""
Plans, usage and payments (Razorpay).

- GET  /billing/plans            - plan catalogue for the pricing page (public)
- GET  /billing/me               - current plan, limits and usage
- POST /billing/checkout         - buy Scholar / Topper: a renewing subscription when Razorpay
                                   plan IDs are set, otherwise a one-time month or year
- POST /billing/pass/checkout    - start an Exam Night Pass order
- POST /billing/verify           - confirm a payment from Razorpay Checkout
- POST /billing/cancel           - cancel the subscription at the end of the period
- GET  /billing/invoices         - GST invoices for the subscription
- POST /billing/webhook          - Razorpay webhook (renewals, failures, cancellations)
"""

import json
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.deps import get_current_user
from config.settings import settings
from db.client import async_db, get_supabase_client
from services import razorpay_service as rzp
from services.billing_service import billing
from services.plans import EXAM_NIGHT_PASS, PLANS, plan_price, public_catalog
from services.usage_service import usage
from utils.logger import logger

router = APIRouter()

NOT_CONFIGURED = HTTPException(503, {
    "code": "billing_not_configured",
    "message": "Payments aren't switched on yet. Please check back soon.",
})


def _iso(epoch) -> Optional[str]:
    return datetime.fromtimestamp(int(epoch), timezone.utc).isoformat() if epoch else None


def renewing(plan: str, cycle: str) -> bool:
    """Scholar / Topper renew automatically only when the Razorpay plan ID is set."""
    return bool(rzp.plan_id(plan, cycle))


def payment_mode() -> str:
    return "subscription" if all(renewing(p, c) for p in ("scholar", "topper") for c in ("monthly", "yearly")) \
        else "one_time"


@router.get("/plans")
async def get_plans():
    return {**public_catalog(), "payments_enabled": rzp.configured(), "test_mode": rzp.test_mode(),
            "payment_mode": payment_mode()}


@router.get("/me")
async def get_my_plan(current_user: dict = Depends(get_current_user)):
    return await usage.summary(current_user["id"])


# ---------------------------------------------------------------- checkout

class CheckoutRequest(BaseModel):
    plan: Literal["scholar", "topper"]
    cycle: Literal["monthly", "yearly"] = "monthly"


@router.post("/checkout")
async def checkout(request: CheckoutRequest, current_user: dict = Depends(get_current_user)):
    if not rzp.configured():
        raise NOT_CONFIGURED
    user_id = current_user["id"]
    current = await usage.plan_row(user_id)
    if current_user.get("managed") or current.get("source") == "institution":
        raise HTTPException(409, {"code": "school_plan",
                                  "message": "Your school already gives you a plan, so there's nothing to buy."})
    amount = plan_price(request.plan, request.cycle)
    common = {
        "key_id": settings.RAZORPAY_KEY_ID, "plan": request.plan, "cycle": request.cycle, "amount_inr": amount,
        "name": "LuminaIQ", "prefill": {"email": current_user.get("email") or ""},
        "test_mode": rzp.test_mode(),
    }

    if renewing(request.plan, request.cycle):
        if current.get("source") == "razorpay" and current.get("razorpay_subscription_id") \
                and current.get("plan") == request.plan and current.get("billing_cycle") == request.cycle \
                and not current.get("cancel_at_period_end"):
            raise HTTPException(409, {"code": "already_subscribed", "message": "You're already on this plan."})
        try:
            sub = await rzp.create_subscription(request.plan, request.cycle, {
                "user_id": user_id, "plan": request.plan, "cycle": request.cycle,
            })
        except rzp.RazorpayNotConfigured:
            raise NOT_CONFIGURED
        except Exception:
            raise HTTPException(502, "Couldn't reach the payment provider. Please try again.")
        await billing.record_payment({
            "user_id": user_id, "kind": "subscription", "plan": f"{request.plan}:{request.cycle}",
            "amount_paise": amount * 100, "status": "created", "razorpay_subscription_id": sub["id"],
        })
        return {**common, "mode": "subscription", "subscription_id": sub["id"],
                "description": f"{PLANS[request.plan]['name']} · renews {request.cycle}"}

    # One-time payment for a month or a year (no Razorpay plan setup needed)
    term = billing.prepaid_term(await billing.plan_record(user_id), request.plan, request.cycle)
    try:
        order = await rzp.create_order(amount * 100, f"plan_{user_id[:8]}", {
            "user_id": user_id, "kind": "plan", "plan": request.plan, "cycle": request.cycle,
        })
    except rzp.RazorpayNotConfigured:
        raise NOT_CONFIGURED
    except Exception:
        raise HTTPException(502, "Couldn't reach the payment provider. Please try again.")
    await billing.record_payment({
        "user_id": user_id, "kind": "plan", "plan": f"{request.plan}:{request.cycle}",
        "amount_paise": amount * 100, "status": "created", "razorpay_order_id": order["id"],
    })
    term_name = "1 month" if request.cycle == "monthly" else "1 year"
    return {**common, "mode": "one_time", "order_id": order["id"], "amount_paise": amount * 100,
            "description": f"{PLANS[request.plan]['name']} · {term_name}",
            # What the student gets if they pay now (shown before paying)
            "starts_at": term["start"].isoformat(), "ends_at": term["end"].isoformat()}


@router.post("/pass/checkout")
async def pass_checkout(current_user: dict = Depends(get_current_user)):
    if not rzp.configured():
        raise NOT_CONFIGURED
    user_id = current_user["id"]
    amount = EXAM_NIGHT_PASS["price_inr"] * 100
    try:
        order = await rzp.create_order(amount, f"pass_{user_id[:8]}", {"user_id": user_id, "kind": "pass"})
    except Exception:
        raise HTTPException(502, "Couldn't reach the payment provider. Please try again.")
    await billing.record_payment({
        "user_id": user_id, "kind": "pass", "plan": "topper", "amount_paise": amount,
        "status": "created", "razorpay_order_id": order["id"],
    })
    return {
        "key_id": settings.RAZORPAY_KEY_ID,
        "order_id": order["id"],
        "amount_paise": amount,
        "name": "LuminaIQ",
        "description": f"{EXAM_NIGHT_PASS['name']} · {EXAM_NIGHT_PASS['hours']} hours of Topper",
        "prefill": {"email": current_user.get("email") or ""},
    }


class VerifyRequest(BaseModel):
    kind: Literal["subscription", "plan", "pass", "seats"]
    razorpay_payment_id: str
    razorpay_signature: str
    razorpay_subscription_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None


@router.post("/verify")
async def verify(request: VerifyRequest, current_user: dict = Depends(get_current_user)):
    """Called by Checkout's success handler. The signature proves Razorpay took the payment."""
    user_id = current_user["id"]
    if request.kind == "subscription":
        if not request.razorpay_subscription_id or not rzp.verify_subscription_payment(
                request.razorpay_payment_id, request.razorpay_subscription_id, request.razorpay_signature):
            raise HTTPException(400, "Payment could not be verified.")
        record = await billing.checkout_record(subscription_id=request.razorpay_subscription_id)
        if not record or record["user_id"] != user_id:
            raise HTTPException(400, "Unknown subscription.")
        plan, cycle = record["plan"].split(":")
        start = end = None
        try:  # Razorpay's own period dates, so the stored end is exact
            sub = await rzp.fetch_subscription(request.razorpay_subscription_id)
            start, end = sub.get("current_start"), sub.get("current_end")
        except Exception as e:
            logger.warning(f"[Billing] could not fetch subscription dates: {e}")
        term = await billing.activate_subscription(user_id, plan, cycle, request.razorpay_subscription_id,
                                                   current_end_epoch=end, current_start_epoch=start)
        await billing.record_payment({
            "period_start": term["start"].isoformat(), "period_end": term["end"].isoformat(),
            "user_id": user_id, "kind": "subscription", "plan": record["plan"],
            "amount_paise": record.get("amount_paise"), "status": "paid",
            "razorpay_payment_id": request.razorpay_payment_id,
            "razorpay_subscription_id": request.razorpay_subscription_id,
        })
    elif request.kind == "plan":
        if not request.razorpay_order_id or not rzp.verify_order_payment(
                request.razorpay_order_id, request.razorpay_payment_id, request.razorpay_signature):
            raise HTTPException(400, "Payment could not be verified.")
        record = await billing.checkout_record(order_id=request.razorpay_order_id)
        if not record or record["user_id"] != user_id or record["kind"] != "plan":
            raise HTTPException(400, "Unknown order.")
        await _apply_plan(record, request.razorpay_payment_id, request.razorpay_order_id)
    elif request.kind == "seats":
        if not request.razorpay_order_id or not rzp.verify_order_payment(
                request.razorpay_order_id, request.razorpay_payment_id, request.razorpay_signature):
            raise HTTPException(400, "Payment could not be verified.")
        record = await billing.checkout_record(order_id=request.razorpay_order_id)
        if not record or record["user_id"] != user_id or record["kind"] != "seats":
            raise HTTPException(400, "Unknown order.")
        if not await billing.payment_paid(request.razorpay_payment_id):
            await _apply_seats(record, request.razorpay_payment_id, request.razorpay_order_id)
    else:
        if not request.razorpay_order_id or not rzp.verify_order_payment(
                request.razorpay_order_id, request.razorpay_payment_id, request.razorpay_signature):
            raise HTTPException(400, "Payment could not be verified.")
        record = await billing.checkout_record(order_id=request.razorpay_order_id)
        if not record or record["user_id"] != user_id or record["kind"] != "pass":
            raise HTTPException(400, "Unknown order.")
        await _apply_pass(record, request.razorpay_payment_id, request.razorpay_order_id)
    return await usage.summary(user_id)


@router.post("/cancel")
async def cancel(current_user: dict = Depends(get_current_user)):
    row = await usage.plan_row(current_user["id"])
    sub_id = row.get("razorpay_subscription_id")
    if row.get("source") != "razorpay" or not sub_id:
        raise HTTPException(400, {"code": "nothing_to_cancel",
                                  "message": "Your plan doesn't renew by itself, so there's nothing to cancel. "
                                             "It simply ends on its end date."})
    try:
        await rzp.cancel_subscription(sub_id, at_cycle_end=True)
    except rzp.RazorpayNotConfigured:
        raise NOT_CONFIGURED
    except Exception:
        raise HTTPException(502, "Couldn't reach the payment provider. Please try again.")
    await billing.mark_cancel_at_period_end(current_user["id"])
    return await usage.summary(current_user["id"])


@router.get("/invoices")
async def invoices(current_user: dict = Depends(get_current_user)):
    row = await usage.plan_row(current_user["id"])
    sub_id = row.get("razorpay_subscription_id")
    if not sub_id or not rzp.configured():
        return {"invoices": []}
    try:
        data = await rzp.list_invoices(sub_id)
    except Exception:
        return {"invoices": []}
    return {"invoices": [
        {"id": i.get("id"), "date": i.get("date") or i.get("issued_at"), "amount_paise": i.get("amount"),
         "status": i.get("status"), "url": i.get("short_url")}
        for i in data.get("items", [])
    ]}


def parse_seats_plan(plan: str):
    """'institution:<id>:<seats>[:<months>]' -> (id, seats, months). Older orders were yearly."""
    parts = plan.split(":")
    months = int(parts[3]) if len(parts) > 3 else 12
    return parts[1], int(parts[2]), months


async def _apply_seats(record: dict, payment_id: str, order_id: str, raw: dict = None) -> None:
    from services.institution_service import institutions

    institution_id, seats, months = parse_seats_plan(record["plan"])
    paid = (raw or {}).get("amount")
    if paid is not None and record.get("amount_paise") and int(paid) < int(record["amount_paise"]):
        logger.error(f"[Billing] seats payment {payment_id} paid {paid} < expected {record['amount_paise']}; not applied")
        await billing.record_payment({
            "user_id": record["user_id"], "kind": "seats", "plan": record["plan"], "amount_paise": paid,
            "status": "failed", "razorpay_payment_id": payment_id, "razorpay_order_id": order_id, "raw": raw,
        })
        return
    # /verify and the webhook can arrive together: only the first one extends the term
    if not await billing.claim(payment_id, "seats.apply"):
        logger.info(f"[Billing] seats payment {payment_id} already applied")
        return
    try:
        await institutions.activate_seats(institution_id, seats, months, actor=record.get("user_id"),
                                          source="razorpay", payment_id=payment_id)
    except Exception:
        await billing.release(payment_id)
        raise
    await billing.record_payment({
        "user_id": record["user_id"], "kind": "seats", "plan": record["plan"],
        "amount_paise": record.get("amount_paise"), "status": "paid",
        "razorpay_payment_id": payment_id, "razorpay_order_id": order_id, "raw": raw,
    })


async def _apply_plan(record: dict, payment_id: str, order_id: str, raw: dict = None) -> None:
    """A one-time Scholar / Topper payment: add the month or year (exactly once)."""
    plan, cycle = record["plan"].split(":")
    paid = (raw or {}).get("amount")
    if paid is not None and record.get("amount_paise") and int(paid) < int(record["amount_paise"]):
        logger.error(f"[Billing] plan payment {payment_id} paid {paid} < expected {record['amount_paise']}; not applied")
        await billing.record_payment({
            "user_id": record["user_id"], "kind": "plan", "plan": record["plan"], "amount_paise": paid,
            "status": "failed", "razorpay_payment_id": payment_id, "razorpay_order_id": order_id, "raw": raw,
        })
        return
    if await billing.payment_paid(payment_id) or not await billing.claim(payment_id, "plan.apply"):
        logger.info(f"[Billing] plan payment {payment_id} already applied")
        return
    try:
        term = await billing.activate_prepaid(record["user_id"], plan, cycle)
    except Exception:
        await billing.release(payment_id)
        raise
    await billing.record_payment({
        "user_id": record["user_id"], "kind": "plan", "plan": record["plan"],
        "amount_paise": record.get("amount_paise"), "status": "paid",
        "razorpay_payment_id": payment_id, "razorpay_order_id": order_id, "raw": raw,
        "period_start": term["start"].isoformat(), "period_end": term["end"].isoformat(),
    })


async def _apply_pass(record: dict, payment_id: str, order_id: str, raw: dict = None) -> None:
    """An Exam Night Pass payment: add 48 hours of Topper (exactly once)."""
    if await billing.payment_paid(payment_id) or not await billing.claim(payment_id, "pass.apply"):
        return
    try:
        until = await billing.grant_pass(record["user_id"])
    except Exception:
        await billing.release(payment_id)
        raise
    await billing.record_payment({
        "user_id": record["user_id"], "kind": "pass", "plan": "topper",
        "amount_paise": (raw or {}).get("amount") or record.get("amount_paise"), "status": "paid",
        "razorpay_payment_id": payment_id, "razorpay_order_id": order_id, "raw": raw, "period_end": until,
    })


# ----------------------------------------------------------------- webhook

@router.post("/webhook")
async def webhook(request: Request):
    """
    Razorpay → us. Configure in Razorpay Dashboard → Webhooks with URL
    https://<backend>/api/v1/billing/webhook, the secret in RAZORPAY_WEBHOOK_SECRET and
    events: subscription.activated, subscription.charged, subscription.pending,
    subscription.halted, subscription.cancelled, subscription.completed, payment.captured,
    order.paid, payment.failed. Test mode works the same with rzp_test_ keys and a
    webhook created while the Dashboard is in Test Mode.
    """
    body = await request.body()
    if not rzp.verify_webhook(body, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(body)
    name = event.get("event", "")
    event_id = request.headers.get("x-razorpay-event-id") or f"{name}:{event.get('created_at')}"

    client = get_supabase_client()
    try:
        await async_db(lambda: client.table("billing_events").insert({"event_id": event_id, "event": name}).execute())
    except Exception:
        return {"status": "duplicate"}  # already processed (Razorpay retries deliveries)

    async def _forget_event():
        # Processing failed: drop the marker so Razorpay's retry is processed, not skipped
        try:
            await async_db(lambda: client.table("billing_events").delete().eq("event_id", event_id).execute())
        except Exception as e:
            logger.error(f"[Billing] could not clear event {event_id}: {e}")

    payload = event.get("payload", {})
    sub = (payload.get("subscription") or {}).get("entity") or {}
    pay = (payload.get("payment") or {}).get("entity") or {}
    try:
        if name in ("subscription.activated", "subscription.charged"):
            notes = sub.get("notes") or {}
            if notes.get("user_id") and notes.get("plan") in PLANS:
                await billing.activate_subscription(
                    notes["user_id"], notes["plan"], notes.get("cycle", "monthly"), sub["id"],
                    current_end_epoch=sub.get("current_end"), current_start_epoch=sub.get("current_start"))
            if pay.get("id"):
                await billing.record_payment({
                    "period_start": _iso(sub.get("current_start")), "period_end": _iso(sub.get("current_end")),
                    "user_id": notes.get("user_id"), "kind": "subscription",
                    "plan": f"{notes.get('plan')}:{notes.get('cycle')}", "amount_paise": pay.get("amount"),
                    "status": "paid", "razorpay_payment_id": pay["id"], "razorpay_subscription_id": sub.get("id"),
                    "raw": pay,
                })
        elif name in ("subscription.halted", "subscription.cancelled", "subscription.completed", "subscription.expired"):
            await billing.subscription_status(sub["id"], name.split(".")[1])
        elif name == "subscription.pending":
            # A renewal payment failed and is being retried: keep access during the retries
            await billing.subscription_status(sub["id"], "active", sub.get("current_end"))
        elif name == "payment.failed" and pay.get("order_id"):
            record = await billing.checkout_record(order_id=pay["order_id"])
            if record:
                await billing.record_payment({
                    "user_id": record["user_id"], "kind": record["kind"], "plan": record.get("plan"),
                    "amount_paise": pay.get("amount"), "status": "failed",
                    "razorpay_payment_id": pay.get("id"), "razorpay_order_id": pay["order_id"], "raw": pay,
                })
        elif name in ("payment.captured", "order.paid") and pay.get("order_id"):
            # Backup for plans, seats and the Exam Night Pass if the browser closed before /verify ran
            record = await billing.checkout_record(order_id=pay["order_id"])
            if record and record["kind"] == "plan":
                await _apply_plan(record, pay["id"], pay["order_id"], raw=pay)
            if record and record["kind"] == "seats" and not await billing.payment_paid(pay["id"]):
                await _apply_seats(record, pay["id"], pay["order_id"], raw=pay)
            if record and record["kind"] == "pass":
                await _apply_pass(record, pay["id"], pay["order_id"], raw=pay)
    except Exception as e:
        logger.error(f"[Billing] webhook {name} failed: {e}")
        await _forget_event()
        raise HTTPException(500, "Webhook processing failed")  # Razorpay will retry
    return {"status": "ok"}
