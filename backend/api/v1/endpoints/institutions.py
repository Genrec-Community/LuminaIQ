"""
Institution plan endpoints (services/institution_service.py).

- GET    /institutions/me                     - my institution (admin/teacher/student view)
- POST   /institutions                        - create an institution (14-day trial)
- POST   /institutions/join                   - join with a teacher or class code
- POST   /institutions/classes                - create a class
- GET    /institutions/classes/{id}           - class dashboard
- POST   /institutions/classes/{id}/books     - publish a book to a class
- GET    /institutions/publishable            - books I can publish
- DELETE /institutions/members/{user_id}      - remove a member (admin)
- POST   /institutions/seats/checkout         - pay for a year of student seats
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from config.settings import settings
from services import razorpay_service as rzp
from services.billing_service import billing
from services.institution_service import MIN_PAID_SEATS, institutions, seats_price_paise
from services.user_data_service import user_data

router = APIRouter()


async def _display_name(user: dict) -> str:
    try:
        s = await user_data.get_settings(user["id"]) or {}
        return (s.get("nickname") or s.get("studentName") or "").strip()[:80] or (user.get("email") or "").split("@")[0]
    except Exception:
        return (user.get("email") or "").split("@")[0]


class CreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    contact_email: Optional[str] = None
    billing_name: Optional[str] = None
    gstin: Optional[str] = Field(None, max_length=15)


class JoinRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=20)


class ClassRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class PublishRequest(BaseModel):
    document_id: str


class SeatsRequest(BaseModel):
    seats: int = Field(..., ge=1, le=100000)


@router.get("/me")
async def my_institution(current_user: dict = Depends(get_current_user)):
    return await institutions.overview(current_user)


@router.post("")
async def create_institution(request: CreateRequest, current_user: dict = Depends(get_current_user)):
    await institutions.create(current_user, request.name, request.contact_email, request.billing_name,
                              request.gstin, await _display_name(current_user))
    return await institutions.overview(current_user)


@router.post("/join")
async def join(request: JoinRequest, current_user: dict = Depends(get_current_user)):
    return await institutions.join(current_user, request.code, await _display_name(current_user))


@router.post("/classes")
async def create_class(request: ClassRequest, current_user: dict = Depends(get_current_user)):
    return await institutions.create_class(current_user, request.name)


@router.get("/classes/{class_id}")
async def class_dashboard(class_id: str, current_user: dict = Depends(get_current_user)):
    return await institutions.class_dashboard(current_user, class_id)


@router.post("/classes/{class_id}/books")
async def publish(class_id: str, request: PublishRequest, current_user: dict = Depends(get_current_user)):
    return await institutions.publish_book(current_user, class_id, request.document_id)


@router.get("/publishable")
async def publishable(current_user: dict = Depends(get_current_user)):
    return {"documents": await institutions.publishable_documents(current_user)}


@router.delete("/members/{member_user_id}")
async def remove_member(member_user_id: str, current_user: dict = Depends(get_current_user)):
    await institutions.remove_member(current_user, member_user_id)
    return {"removed": member_user_id}


@router.post("/seats/checkout")
async def seats_checkout(request: SeatsRequest, current_user: dict = Depends(get_current_user)):
    m = await institutions.membership(current_user["id"])
    if not m or m["role"] != "admin":
        raise HTTPException(403, "Only admins can buy seats.")
    students = await institutions.student_count(m["institution_id"])
    if request.seats < max(MIN_PAID_SEATS, students):
        raise HTTPException(400, f"Choose at least {max(MIN_PAID_SEATS, students)} seats.")
    if not rzp.configured():
        raise HTTPException(503, {"code": "billing_not_configured",
                                  "message": "Payments aren't switched on yet. Please check back soon."})
    price = seats_price_paise(request.seats)
    try:
        order = await rzp.create_order(price["total"], f"seats_{m['institution_id'][:8]}", {
            "user_id": current_user["id"], "kind": "seats",
            "institution_id": m["institution_id"], "seats": str(request.seats),
        })
    except Exception:
        raise HTTPException(502, "Couldn't reach the payment provider. Please try again.")
    await billing.record_payment({
        "user_id": current_user["id"], "kind": "seats", "plan": f"institution:{m['institution_id']}:{request.seats}",
        "amount_paise": price["total"], "status": "created", "razorpay_order_id": order["id"],
    })
    return {
        "key_id": settings.RAZORPAY_KEY_ID, "order_id": order["id"], "amount_paise": price["total"],
        "base_paise": price["base"], "gst_paise": price["gst"], "seats": request.seats,
        "name": "Lumina IQ", "description": f"Institution · {request.seats} students · 1 year",
        "prefill": {"email": current_user.get("email") or ""},
    }
