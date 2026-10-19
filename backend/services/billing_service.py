"""
Plan state changes from payments: activating subscriptions, Exam Night Passes,
renewals, cancellations. The source of truth for "what plan is this user on"
is user_plans (read by services/usage_service.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from db.client import async_db, get_supabase_client
from services.plans import EXAM_NIGHT_PASS
from services.usage_service import usage
from utils.logger import logger

GRACE = timedelta(days=2)  # renewal payments can land a little after the period ends


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _from_epoch(ts: Optional[int]) -> Optional[str]:
    return datetime.fromtimestamp(int(ts), timezone.utc).isoformat() if ts else None


class BillingService:
    def __init__(self):
        self.client = get_supabase_client()

    async def _upsert_plan(self, user_id: str, fields: Dict[str, Any]) -> None:
        row = {"user_id": user_id, "updated_at": _now().isoformat(), **fields}
        await async_db(lambda: self.client.table("user_plans").upsert(row, on_conflict="user_id").execute())
        usage.forget(user_id)

    async def record_payment(self, row: Dict[str, Any]) -> None:
        try:
            if row.get("razorpay_payment_id"):
                await async_db(lambda: self.client.table("payments").upsert(
                    row, on_conflict="razorpay_payment_id").execute())
            else:
                await async_db(lambda: self.client.table("payments").insert(row).execute())
        except Exception as e:
            logger.error(f"Could not record payment: {e}")

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

    # ---------------------------------------------------------- subscriptions

    async def activate_subscription(self, user_id: str, plan: str, cycle: str, subscription_id: str,
                                    current_end_epoch: Optional[int] = None) -> None:
        end = _from_epoch(current_end_epoch) if current_end_epoch else (
            _now() + (timedelta(days=31) if cycle == "monthly" else timedelta(days=366))).isoformat()
        end_with_grace = (datetime.fromisoformat(end) + GRACE).isoformat()
        await self._upsert_plan(user_id, {
            "plan": plan, "status": "active", "source": "razorpay", "billing_cycle": cycle,
            "current_period_end": end_with_grace, "cancel_at_period_end": False,
            "razorpay_subscription_id": subscription_id,
        })
        logger.info(f"[Billing] {user_id} -> {plan} ({cycle}) until {end_with_grace}")

    async def subscription_status(self, subscription_id: str, status: str, current_end_epoch: Optional[int] = None) -> None:
        res = await async_db(lambda: self.client.table("user_plans").select("user_id")
                             .eq("razorpay_subscription_id", subscription_id).limit(1).execute())
        if not res.data:
            return
        user_id = res.data[0]["user_id"]
        fields: Dict[str, Any] = {"status": status}
        if current_end_epoch:
            fields["current_period_end"] = (datetime.fromtimestamp(int(current_end_epoch), timezone.utc) + GRACE).isoformat()
        await self._upsert_plan(user_id, fields)
        logger.info(f"[Billing] subscription {subscription_id} -> {status}")

    async def mark_cancel_at_period_end(self, user_id: str) -> None:
        await self._upsert_plan(user_id, {"cancel_at_period_end": True})

    # ----------------------------------------------------------------- passes

    async def grant_pass(self, user_id: str) -> str:
        """Extend (or start) the 48-hour Topper pass."""
        res = await async_db(lambda: self.client.table("user_plans").select("pass_until")
                             .eq("user_id", user_id).limit(1).execute())
        start = _now()
        if res.data and res.data[0].get("pass_until"):
            current = datetime.fromisoformat(res.data[0]["pass_until"].replace("Z", "+00:00"))
            start = max(start, current)
        until = (start + timedelta(hours=EXAM_NIGHT_PASS["hours"])).isoformat()
        if res.data:
            await self._upsert_plan(user_id, {"pass_until": until})
        else:
            await self._upsert_plan(user_id, {"plan": "free", "status": "active", "source": "default", "pass_until": until})
        logger.info(f"[Billing] Exam Night Pass for {user_id} until {until}")
        return until


billing = BillingService()
