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
    except Exception as e:
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