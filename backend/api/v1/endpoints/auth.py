from fastapi import APIRouter, HTTPException, status
from models.schemas import UserSignup, UserLogin
from services.auth_service import auth_service
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

from models.schemas import GoogleLoginRequest

@router.post("/google", response_model=Any)
async def google_login(request: GoogleLoginRequest):
    """
    Exchange Google/Supabase Token for App Token
    """
    try:
        return await auth_service.login_with_google(request.access_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )