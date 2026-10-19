"""
Plans, usage and payments.

- GET  /billing/plans   - plan catalogue for the pricing page (public)
- GET  /billing/me      - current plan, limits and usage
"""

from fastapi import APIRouter, Depends

from api.deps import get_current_user
from services.plans import public_catalog
from services.usage_service import usage

router = APIRouter()


@router.get("/plans")
async def get_plans():
    return public_catalog()


@router.get("/me")
async def get_my_plan(current_user: dict = Depends(get_current_user)):
    return await usage.summary(current_user["id"])
