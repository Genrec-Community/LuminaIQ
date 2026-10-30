"""
Create the Lumina IQ subscription plans in your Razorpay account (run once per
account / mode) and print the env vars to paste into Render.

    cd backend
    RAZORPAY_KEY_ID=rzp_test_xxx RAZORPAY_KEY_SECRET=xxx python scripts/create_razorpay_plans.py

Use test keys first; run again with live keys when you go live (plan IDs differ).
Prices come from services/plans.py (GST-inclusive amounts the student pays).
"""

import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.plans import PLANS  # noqa: E402

key_id, secret = os.environ.get("RAZORPAY_KEY_ID"), os.environ.get("RAZORPAY_KEY_SECRET")
if not key_id or not secret:
    sys.exit("Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET first.")

lines = []
for plan in ("scholar", "topper"):
    for cycle, field in (("monthly", "price_inr"), ("yearly", "price_inr_yearly")):
        amount = PLANS[plan][field]
        r = httpx.post(
            "https://api.razorpay.com/v1/plans",
            auth=(key_id, secret),
            json={
                "period": cycle,
                "interval": 1,
                "item": {
                    "name": f"Lumina IQ {PLANS[plan]['name']} ({cycle})",
                    "amount": amount * 100,
                    "currency": "INR",
                    "description": f"Lumina IQ {PLANS[plan]['name']} plan, billed {cycle}",
                },
                "notes": {"plan": plan, "cycle": cycle},
            },
            timeout=20,
        )
        r.raise_for_status()
        pid = r.json()["id"]
        lines.append(f"RAZORPAY_PLAN_{plan.upper()}_{cycle.upper()}={pid}")
        print(f"created {plan} {cycle}: ₹{amount} -> {pid}")

print("\nAdd these to the Render service's environment:\n")
print("\n".join(lines))
