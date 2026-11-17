"""
Product analytics inputs from the app: events, sign-up attribution, consent, feedback and
data requests. See services/product_analytics.py for what is kept and why.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from api.deps import get_current_user
from services import product_analytics as pa

router = APIRouter()

_optional_bearer = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)
TRACK_PER_MINUTE = 120


async def optional_user(token: Optional[str] = Depends(_optional_bearer)) -> Optional[dict]:
    """The signed-in user when there's a valid token, else None (landing page visitors)."""
    if not token:
        return None
    try:
        return await get_current_user(token)
    except HTTPException:
        return None


def _ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def _over_limit(key: str) -> bool:
    from config.settings import settings
    from utils.rate_limit import _get_counter
    if not settings.RATE_LIMITS_ENABLED:
        return False
    try:
        return await _get_counter().hit(f"track:{key}", 60) > TRACK_PER_MINUTE
    except Exception:
        return False


class EventIn(BaseModel):
    name: str
    project_id: Optional[str] = None
    path: Optional[str] = None
    props: Dict[str, Any] = Field(default_factory=dict)


class TrackIn(BaseModel):
    events: List[EventIn] = Field(..., max_length=25)
    anon_id: Optional[str] = None
    session_id: Optional[str] = None
    platform: Optional[str] = None


@router.post("/track", status_code=204)
async def track(body: TrackIn, request: Request, user: Optional[dict] = Depends(optional_user)):
    """Batched events. Unknown names are dropped; never fails the caller."""
    who = (user or {}).get("id") or body.anon_id or _ip(request) or "unknown"
    if await _over_limit(str(who)[:64]):
        return Response(status_code=204)
    await pa.track([e.model_dump() for e in body.events], user_id=(user or {}).get("id"),
                   anon_id=body.anon_id, session_id=body.session_id, platform=body.platform)
    return Response(status_code=204)


class AttributionIn(BaseModel):
    anon_id: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    referrer: Optional[str] = None
    landing_path: Optional[str] = None
    referral_code: Optional[str] = None
    invite_code: Optional[str] = None
    platform: Optional[str] = None
    first_seen_at: Optional[str] = None


@router.post("/attribution")
async def attribution(body: AttributionIn, request: Request, user: dict = Depends(get_current_user)):
    """First touch for this user; later calls change nothing."""
    country = request.headers.get("cf-ipcountry") or request.headers.get("x-country")
    saved = await pa.save_attribution(user["id"], body.model_dump(), country=country)
    return {"saved": saved}


async def _level(user_id: str) -> Optional[str]:
    try:
        from services import levels
        return (await levels.effective_for(user_id)).get("level")
    except Exception:
        return None


@router.get("/consent")
async def consent_status(user: dict = Depends(get_current_user)):
    """What this user has agreed to, and what's still needed (empty `missing` = nothing to ask)."""
    level = await _level(user["id"])
    try:
        state = await pa.consent_state(user["id"])
        missing = await pa.missing_consent(user["id"], level, bool(user.get("managed")))
    except Exception:
        # The table isn't there yet (migration pending): don't block anyone
        return {"state": {}, "missing": [], "level": level}
    return {"state": state, "missing": missing, "level": level,
            "versions": {k: pa.current_version(k) for k in ("terms", "privacy", "parental")}}


class ConsentIn(BaseModel):
    kind: str
    granted: bool = True
    method: str = "sign_in_notice"
    guardian_name: Optional[str] = Field(None, max_length=120)
    guardian_email: Optional[str] = Field(None, max_length=200)
    guardian_relation: Optional[str] = Field(None, max_length=40)


@router.post("/consent")
async def give_consent(body: ConsentIn, request: Request, user: dict = Depends(get_current_user)):
    if body.kind not in pa.CONSENT_KINDS:
        raise HTTPException(400, "Unknown consent kind.")
    granted_by = "self"
    if body.kind == "parental":
        if body.granted and (not (body.guardian_name or "").strip() or "@" not in (body.guardian_email or "")):
            raise HTTPException(400, "Please enter the parent's or guardian's name and email.")
        granted_by = "guardian"
    await pa.record_consent(user["id"], body.kind, body.granted, body.method, granted_by=granted_by,
                            guardian_name=body.guardian_name, guardian_email=body.guardian_email,
                            ip=_ip(request), user_agent=request.headers.get("user-agent"))
    return {"ok": True}


class FeedbackIn(BaseModel):
    kind: str
    rating: Optional[int] = None
    comment: Optional[str] = Field(None, max_length=2000)
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/feedback")
async def feedback(body: FeedbackIn, user: dict = Depends(get_current_user)):
    try:
        await pa.record_feedback(user["id"], body.kind, rating=body.rating, comment=body.comment,
                                 target_type=body.target_type, target_id=body.target_id, context=body.context)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


class DataRequestIn(BaseModel):
    kind: str
    note: Optional[str] = Field(None, max_length=1000)


@router.post("/data-request")
async def data_request(body: DataRequestIn, user: dict = Depends(get_current_user)):
    """Ask for a copy of your data or for your account to be deleted (handled by the team)."""
    try:
        return await pa.request_data(user["id"], body.kind, body.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
