"""
Platform admin console (LuminaIQ staff, not school staff): approve, pause and
extend schools. Access: users with the 'owner' or 'admin' role in user_roles, or
an email listed in PLATFORM_ADMIN_EMAILS.

- GET  /platform/me                               - am I a platform admin?
- GET  /platform/institutions?status=&q=&page=    - all schools (pending | live | expired | suspended)
- POST /platform/institutions/{id}/approve        - approve (starts the trial if unpaid)
- POST /platform/institutions/{id}/suspend        - switch a school off now
- POST /platform/institutions/{id}/extend         - offline payment / goodwill: days, paid_until, seats
- POST /platform/institutions/{id}/trial          - mark as trial or paid
- GET  /platform/institutions/{id}/audit          - what happened to this school
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from config.settings import settings
from db.client import async_db, get_supabase_client
from services.institution_service import institutions

router = APIRouter()


def _allowed_emails() -> set:
    return {e.strip().lower() for e in (settings.PLATFORM_ADMIN_EMAILS or "").split(",") if e.strip()}


async def is_platform_admin(user: dict) -> bool:
    if user.get("managed"):
        return False
    if (user.get("email") or "").lower() in _allowed_emails():
        return True
    try:
        client = get_supabase_client()
        res = await async_db(lambda: client.table("user_roles").select("role")
                             .eq("user_id", user["id"]).limit(1).execute())
        return bool(res.data) and res.data[0].get("role") in ("owner", "admin")
    except Exception:
        return False


async def require_platform_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not await is_platform_admin(current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform admins only.")
    return current_user


class NoteRequest(BaseModel):
    note: str = Field("", max_length=500)


class ExtendRequest(BaseModel):
    days: Optional[int] = Field(None, ge=1, le=3660)
    paid_until: Optional[str] = None
    seats: Optional[int] = Field(None, ge=1, le=100000)
    note: str = Field("", max_length=500)


class TrialRequest(BaseModel):
    trial: bool


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {"platform_admin": await is_platform_admin(current_user)}


@router.get("/institutions")
async def list_institutions(status: str = "", q: str = "", page: int = 1, page_size: int = 50,
                            admin: dict = Depends(require_platform_admin)):
    return await institutions.platform_list(status, q, page, page_size)


@router.post("/institutions/{institution_id}/approve")
async def approve(institution_id: str, request: NoteRequest, admin: dict = Depends(require_platform_admin)):
    return await institutions.approve(admin, institution_id, request.note)


@router.post("/institutions/{institution_id}/suspend")
async def suspend(institution_id: str, request: NoteRequest, admin: dict = Depends(require_platform_admin)):
    return await institutions.suspend(admin, institution_id, request.note)


@router.post("/institutions/{institution_id}/extend")
async def extend(institution_id: str, request: ExtendRequest, admin: dict = Depends(require_platform_admin)):
    return await institutions.extend(admin, institution_id, request.days, request.paid_until, request.seats, request.note)


@router.post("/institutions/{institution_id}/trial")
async def set_trial(institution_id: str, request: TrialRequest, admin: dict = Depends(require_platform_admin)):
    return await institutions.set_trial(admin, institution_id, request.trial)


@router.get("/institutions/{institution_id}/audit")
async def audit(institution_id: str, admin: dict = Depends(require_platform_admin)):
    return {"events": await institutions.audit_log(institution_id)}
