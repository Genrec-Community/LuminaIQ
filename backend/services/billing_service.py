"""
Plan state changes from payments: Scholar / Topper (renewing subscriptions or
one-time terms), Exam Night Passes and cancellations. The source of truth for
"what plan is this user on" is user_plans (read by services/usage_service.py).

Times are stored in UTC. A term runs from the payment (or from the end of the
current term when the same plan is bought again early) for calendar months, so
a month bought on 31 Jan ends on 28/29 Feb at the same time of day.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from db.client import async_db, get_supabase_client
from services.plans import EXAM_NIGHT_PASS, PAID_PLANS, PLANS
from services.usage_service import usage
from utils.logger import logger

# Columns added by migration 015. If it hasn't been run yet, writes are retried
# without them so a payment is never lost over a missing column.
_NEW_PLAN_COLUMNS = ("current_period_start", "last_payment_at")
_NEW_PAYMENT_COLUMNS = ("period_start", "period_end")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _from_epoch(ts: Optional[int]) -> Optional[datetime]:
    return datetime.fromtimestamp(int(ts), timezone.utc) if ts else None


def parse_time(value: Any) -> Optional[datetime]:
    """An ISO timestamp from the database as an aware UTC datetime (None if empty or bad)."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def add_months(dt: datetime, months: int) -> datetime:
    """Same day and time `months` later, clamped to the month's last day (31 Jan + 1 = 28/29 Feb)."""
    month0 = dt.month - 1 + months
    year, month = dt.year + month0 // 12, month0 % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def term_months(cycle: str) -> int:
    return 12 if cycle == "yearly" else 1


def _missing_column(error: Exception) -> bool:
    text = str(error).lower()
    return "column" in text and ("does not exist" in text or "could not find" in text or "schema cache" in text)


class BillingService:
    def __init__(self):
        self.client = get_supabase_client()

    async def _upsert_plan(self, user_id: str, fields: Dict[str, Any]) -> None:
        row = {"user_id": user_id, "updated_at": _now().isoformat(), **fields}
        try:
            await async_db(lambda: self.client.table("user_plans").upsert(row, on_conflict="user_id").execute())
        except Exception as e:
            if not _missing_column(e):
                raise
            logger.warning("[Billing] user_plans is missing migration 015 columns; saved without them")
            slim = {k: v for k, v in row.items() if k not in _NEW_PLAN_COLUMNS}
            await async_db(lambda: self.client.table("user_plans").upsert(slim, on_conflict="user_id").execute())
        usage.forget(user_id)

    async def plan_record(self, user_id: str) -> Dict[str, Any]:
        """The stored user_plans row (not the effective plan), or {}."""
        res = await async_db(lambda: self.client.table("user_plans").select("*")
                             .eq("user_id", user_id).limit(1).execute())
        return res.data[0] if res.data else {}

    async def record_payment(self, row: Dict[str, Any]) -> None:
        async def write(r):
            if r.get("razorpay_payment_id"):
                await async_db(lambda: self.client.table("payments").upsert(
                    r, on_conflict="razorpay_payment_id").execute())
            else:
                await async_db(lambda: self.client.table("payments").insert(r).execute())

        try:
            await write(row)
        except Exception as e:
            try:
                if not _missing_column(e):
                    raise
                await write({k: v for k, v in row.items() if k not in _NEW_PAYMENT_COLUMNS})
            except Exception as e2:
                logger.error(f"Could not record payment: {e2}")

    async def payment_paid(self, payment_id: str) -> bool:
        """Has this Razorpay payment already been applied? (verify + webhook both fire)"""
        res = await async_db(lambda: self.client.table("payments").select("id")
                             .eq("razorpay_payment_id", payment_id).eq("status", "paid").limit(1).execute())
        return bool(res.data)

    async def checkout_record(self, *, subscription_id: str = None, order_id: str = None) -> Optional[Dict[str, Any]]:
        """The 'created' payment row we stored at checkout (who bought what)."""
        q = self.client.table("payments").select("*").eq("status", "created")
        q = q.eq("razorpay_subscription_id", subscription_id) if subscription_id else q.eq("razorpay_order_id", order_id)
        res = await async_db(lambda: q.limit(1).execute())
        return res.data[0] if res.data else None

    # ------------------------------------------------- apply a payment once

    async def claim(self, payment_id: str, what: str) -> bool:
        """
        First caller wins: /verify and the webhook often arrive together for the
        same payment, and only one of them may extend a term.
        """
        try:
            await async_db(lambda: self.client.table("billing_events").insert(
                {"event_id": f"apply:{payment_id}", "event": what}).execute())
            return True
        except Exception:
            return False

    async def release(self, payment_id: str) -> None:
        """Applying failed: let the next attempt (webhook retry) try again."""
        try:
            await async_db(lambda: self.client.table("billing_events").delete()
                           .eq("event_id", f"apply:{payment_id}").execute())
        except Exception as e:
            logger.error(f"[Billing] could not release claim for {payment_id}: {e}")

    # ---------------------------------------------------------- subscriptions

    async def activate_subscription(self, user_id: str, plan: str, cycle: str, subscription_id: str,
                                    current_end_epoch: Optional[int] = None,
                                    current_start_epoch: Optional[int] = None) -> Dict[str, Any]:
        """
        A renewing Razorpay subscription is active (first payment or a renewal).
        Stores Razorpay's own period end; the short renewal grace is added when the
        plan is read (usage_service), so the stored date is the real one.
        """
        now = _now()
        start = _from_epoch(current_start_epoch) or now
        end = _from_epoch(current_end_epoch) or add_months(start, term_months(cycle))
        previous = await self.plan_record(user_id)
        await self._upsert_plan(user_id, {
            "plan": plan, "status": "active", "source": "razorpay", "billing_cycle": cycle,
            "current_period_start": start.isoformat(), "current_period_end": end.isoformat(),
            "cancel_at_period_end": False, "razorpay_subscription_id": subscription_id,
            "last_payment_at": now.isoformat(),
        })
        old_sub = previous.get("razorpay_subscription_id")
        if old_sub and old_sub != subscription_id:
            # Switched plan: stop the old subscription so it never charges again
            await self._stop_subscription(old_sub, at_cycle_end=True)
        logger.info(f"[Billing] {user_id} -> {plan} ({cycle}, renewing) {start.isoformat()} .. {end.isoformat()}")
        return {"start": start, "end": end}

    async def _stop_subscription(self, subscription_id: str, at_cycle_end: bool) -> None:
        from services import razorpay_service as rzp
        try:
            await rzp.cancel_subscription(subscription_id, at_cycle_end=at_cycle_end)
            logger.info(f"[Billing] cancelled old subscription {subscription_id}")
        except Exception as e:
            logger.error(f"[Billing] could not cancel old subscription {subscription_id}: {e}")

    async def subscription_status(self, subscription_id: str, status: str, current_end_epoch: Optional[int] = None) -> None:
        res = await async_db(lambda: self.client.table("user_plans").select("user_id")
                             .eq("razorpay_subscription_id", subscription_id).limit(1).execute())
        if not res.data:
            return  # an old subscription the user has since replaced
        user_id = res.data[0]["user_id"]
        fields: Dict[str, Any] = {"status": status}
        if current_end_epoch:
            fields["current_period_end"] = _from_epoch(current_end_epoch).isoformat()
        await self._upsert_plan(user_id, fields)
        logger.info(f"[Billing] subscription {subscription_id} -> {status}")

    async def mark_cancel_at_period_end(self, user_id: str) -> None:
        await self._upsert_plan(user_id, {"cancel_at_period_end": True})

    # ------------------------------------------------------ one-time terms

    def prepaid_term(self, current: Dict[str, Any], plan: str, cycle: str,
                     now: Optional[datetime] = None) -> Dict[str, datetime]:
        """
        Start and end of a one-time term bought now.
        - Same plan still running: the new term starts when the current one ends.
        - Switching from the other paid plan: the term starts now, and the days left
          on the old plan are converted at the two plans' prices and added on, so
          nothing already paid for is lost.
        """
        now = now or _now()
        start, credit = now, timedelta(0)
        end = parse_time(current.get("current_period_end"))
        running = (current.get("source") == "razorpay" and current.get("plan") in PAID_PLANS
                   and current.get("status") in ("active", "authenticated") and end and end > now)
        if running and current["plan"] == plan:
            start = end
        elif running:
            old_price, new_price = PLANS[current["plan"]]["price_inr"], PLANS[plan]["price_inr"]
            credit = timedelta(seconds=int((end - now).total_seconds() * old_price / new_price))
        return {"start": start, "end": add_months(start, term_months(cycle)) + credit, "credit": credit}

    async def activate_prepaid(self, user_id: str, plan: str, cycle: str) -> Dict[str, Any]:
        """A one-time payment for a month or a year of Scholar / Topper."""
        current = await self.plan_record(user_id)
        now = _now()
        term = self.prepaid_term(current, plan, cycle, now=now)
        # Bought early to extend: the plan period keeps its original start
        start = (parse_time(current.get("current_period_start")) or now) if term["start"] > now else now
        await self._upsert_plan(user_id, {
            "plan": plan, "status": "active", "source": "razorpay", "billing_cycle": cycle,
            "current_period_start": start.isoformat(), "current_period_end": term["end"].isoformat(),
            "cancel_at_period_end": False, "razorpay_subscription_id": None,
            "last_payment_at": now.isoformat(),
        })
        if current.get("razorpay_subscription_id"):
            # Moving from a renewing subscription to one-time payments: no more charges
            await self._stop_subscription(current["razorpay_subscription_id"], at_cycle_end=False)
        logger.info(f"[Billing] {user_id} -> {plan} ({cycle}, one-time) until {term['end'].isoformat()}"
                    + (f" incl. {term['credit']} credit" if term["credit"] else ""))
        return term

    # ----------------------------------------------------------------- passes

    async def grant_pass(self, user_id: str) -> str:
        """Extend (or start) the 48-hour Topper pass."""
        current = await self.plan_record(user_id)
        start = _now()
        until_now = parse_time(current.get("pass_until"))
        if until_now and until_now > start:
            start = until_now
        until = (start + timedelta(hours=EXAM_NIGHT_PASS["hours"])).isoformat()
        if current:
            await self._upsert_plan(user_id, {"pass_until": until})
        else:
            await self._upsert_plan(user_id, {"plan": "free", "status": "active", "source": "default", "pass_until": until})
        logger.info(f"[Billing] Exam Night Pass for {user_id} until {until}")
        return until


billing = BillingService()
