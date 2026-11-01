"""A learner's level and the tools they can use (see services/levels.py)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from services import levels
from services.tools_catalog import HINT_MODES, LEVELS, TOOLS

router = APIRouter()


class LevelRequest(BaseModel):
    level: str


@router.get("/catalog")
async def catalog():
    return {
        "levels": [{"key": k, **v} for k, v in LEVELS.items()],
        "tools": [{"key": k, "label": v} for k, v in TOOLS.items()],
        "hint_modes": list(HINT_MODES),
    }


@router.get("/me")
async def my_level(current_user: dict = Depends(get_current_user)):
    eff = await levels.effective_for(current_user["id"])
    return await with_photo_availability(eff, current_user["id"])


async def with_photo_availability(eff: dict, user_id: str) -> dict:
    """Photo questions need a model that can see images; hide the tool when this learner's can't."""
    from services.llm_service import vision_config
    from services.usage_service import usage
    if "image" in eff.get("tools", []):
        try:
            plan = await usage.plan(user_id)
        except Exception:
            plan = "free"
        if vision_config(plan) is None:
            eff = {**eff, "tools": [t for t in eff["tools"] if t != "image"]}
    return eff


@router.put("/me")
async def set_my_level(request: LevelRequest, current_user: dict = Depends(get_current_user)):
    current = await levels.effective_for(current_user["id"])
    if current["locked"]:
        raise HTTPException(403, "Your level is set by your class. Ask your teacher to change it.")
    try:
        await levels.set_own_level(current_user["id"], request.level)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return await levels.effective_for(current_user["id"])
