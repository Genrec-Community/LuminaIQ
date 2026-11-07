from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from config.settings import settings
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    if payload.get("mgd"):
        # School-created student account: works only while the school is approved,
        # paid up and hasn't switched this account off (cached for a minute).
        from services.institution_service import institutions
        access = await institutions.managed_access(user_id)
        if not access.get("ok"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "school_inactive", "state": access.get("state"),
                        "message": access.get("message") or "Your school's Lumina IQ access is paused."},
            )
    await _remember_user(user_id, payload.get("email"))
    await _remember_plan(user_id)
    return {"id": user_id, "email": payload.get("email"), "managed": bool(payload.get("mgd"))}


# Users recorded in app_users recently (per process), so it's one write per user per hour
_SEEN_TTL = 3600.0
_seen: dict = {}


async def _remember_user(user_id: str, email: Optional[str]) -> None:
    """Keep app_users (id, email) current: Supabase owns the accounts, but SQL joins on email."""
    import time
    from datetime import datetime as _dt
    from services.usage_service import _tz
    now = time.monotonic()
    key = (user_id, _dt.now(_tz()).date())   # a new day writes again, so active days stay exact
    if _seen.get(key, 0) > now:
        return
    if len(_seen) > 50000:
        _seen.clear()
    try:
        from datetime import datetime, timezone
        from db.client import async_db, get_supabase_client
        client = get_supabase_client()
        row = {"id": user_id, "last_seen_at": datetime.now(timezone.utc).isoformat()}
        if email:
            row["email"] = email.lower()
        await async_db(lambda: client.table("app_users").upsert(row).execute())
        _seen[key] = now + _SEEN_TTL
        await _mark_active_day(client, user_id)
    except Exception:
        pass  # never block a request over this


async def _mark_active_day(client, user_id: str) -> None:
    """One row per user per local day, for active-user and retention numbers (admin analytics)."""
    try:
        from datetime import datetime
        from db.client import async_db
        from services.usage_service import _tz
        day = datetime.now(_tz()).date()
        await async_db(lambda: client.pg.fetch(
            "INSERT INTO user_active_days (user_id, day) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, day)))
    except Exception:
        pass  # never block a request over this


async def _remember_plan(user_id: str) -> None:
    """Note the user's plan for this request so AI calls use that plan's model."""
    try:
        from services.usage_service import current_plan, usage
        current_plan.set(await usage.plan(user_id))
    except Exception:
        pass  # never block a request over this; the default model is used

async def get_current_user_with_role(current_user: dict = Depends(get_current_user)):
    from db.client import get_supabase_client
    client = get_supabase_client()
    try:
        response = client.table('user_roles').select('role').eq('user_id', current_user['id']).execute()
        if response.data and len(response.data) > 0:
            current_user['role'] = response.data[0]['role']
        else:
            current_user['role'] = 'handler' # Default role if not found
        return current_user
    except Exception as e:
        # If the table doesn't exist yet or other DB error, fallback gracefully
        current_user['role'] = 'handler'
        return current_user

async def require_owner(current_user: dict = Depends(get_current_user_with_role)):
    if current_user.get('role') != 'owner':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action. Owner role required."
        )
    return current_user

async def require_admin(current_user: dict = Depends(get_current_user_with_role)):
    if current_user.get('role') not in ['owner', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action. Admin or Owner role required."
        )
    return current_user
