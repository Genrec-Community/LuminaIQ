from fastapi import APIRouter, HTTPException, status, Depends
from models.schemas import UserSignup, UserLogin
from services.auth_service import auth_service
from api.deps import require_owner, get_current_user
from pydantic import BaseModel
from typing import Any

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

@router.post("/signup", response_model=Any)
async def signup(user_in: UserSignup):
    """
    Create new user without the need to be logged in
    """
    try:
        result = await auth_service.signup(user_in.email, user_in.password, user_in.full_name)
        return result
    except ValueError as e:
        # Password validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        error_msg = str(e).lower()
        # Check if it's a timeout/network error
        if any(keyword in error_msg for keyword in ['timeout', 'timed out', 'unavailable', 'connection', 'network']):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is temporarily unavailable. Please try again in a few moments.",
            )
        # Check for duplicate user
        elif 'already registered' in error_msg or 'already exists' in error_msg or 'duplicate' in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

@router.post("/login", response_model=Any)
async def login(user_in: UserLogin):
    """
    Login and get access token
    """
    try:
        return await auth_service.login(user_in.email, user_in.password)
    except Exception as e:
        error_msg = str(e).lower()
        # Distinguish timeout/network errors from invalid credentials
        if "timed out" in error_msg or "timeout" in error_msg or "connect" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable. Please try again.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

from models.schemas import TokenExchangeRequest

@router.post("/exchange", response_model=Any)
async def exchange_token(request: TokenExchangeRequest):
    """
    Exchange Supabase OAuth or OTP Token for App Token
    """
    try:
        return await auth_service.exchange_supabase_token(request.access_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

@router.post("/create-handler", response_model=Any)
async def create_handler(
    user_in: UserSignup, 
    current_user: dict = Depends(require_owner)
):
    """
    Create a new handler user. Only accessible by users with the 'owner' role.
    """
    try:
        result = await auth_service.create_handler(user_in.email, user_in.password, user_in.full_name)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        error_msg = str(e).lower()
        if 'already registered' in error_msg or 'already exists' in error_msg or 'duplicate' in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

# Tables keyed by user_id that are not removed by a cascade from auth.users.
# Payment records are kept (they are financial records), unlinked from the account.
_USER_TABLES = [
    "class_book_copies", "class_members", "institution_members", "llm_usage_daily",
    "usage_counters", "user_gamification", "user_plans",
]


@router.delete("/account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    """
    Permanently delete the signed-in account: every book (files, vectors and
    extracted text), study data and the login itself. Required by Google Play
    for apps with accounts; also used by the website.
    """
    from db.client import get_supabase_client, async_db
    from services.document_service import document_service
    from services.qdrant_service import qdrant_service
    from utils.logger import logger

    user_id = current_user["id"]
    client = get_supabase_client()
    projects = (await async_db(lambda: client.table("projects").select("id").eq("user_id", user_id).execute())).data or []
    for p in projects:
        pid = p["id"]
        docs = (await async_db(lambda: client.table("documents").select("id").eq("project_id", pid).execute())).data or []
        for d in docs:
            try:
                await document_service.delete_document(pid, d["id"])
            except Exception as e:
                logger.warning(f"[DeleteAccount] document {d['id']}: {e}")
        try:
            await qdrant_service.async_client.delete_collection(f"project_{pid}")
        except Exception:
            pass  # no collection for an empty book
    await async_db(lambda: client.table("documents").delete().eq("user_id", user_id).execute())
    await async_db(lambda: client.table("projects").delete().eq("user_id", user_id).execute())
    for table in _USER_TABLES:
        try:
            await async_db(lambda: client.table(table).delete().eq("user_id", user_id).execute())
        except Exception as e:
            logger.warning(f"[DeleteAccount] {table}: {e}")
    try:
        await async_db(lambda: client.table("payments").update({"user_id": None}).eq("user_id", user_id).execute())
    except Exception as e:
        logger.warning(f"[DeleteAccount] payments: {e}")
    try:
        await async_db(lambda: client.auth.admin.delete_user(user_id))
    except Exception as e:
        logger.error(f"[DeleteAccount] auth user {user_id}: {e}")
        raise HTTPException(500, "Your data was deleted but the login could not be removed. Contact support.")
    logger.info(f"[DeleteAccount] deleted account {user_id} ({len(projects)} books)")
    return {"deleted": True}
