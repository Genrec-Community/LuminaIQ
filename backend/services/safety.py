"""
Child-safety screening for school-level learners (Class 5-10).

Messages showing distress (self-harm, wanting to die) get a caring reply with a
helpline instead of an AI answer. An optional moderation API (OpenAI-compatible
/moderations, set MODERATION_BASE_URL and MODERATION_API_KEY) also screens
sexual and violent requests. Only counts are stored (safety_events), never text.
Other levels are not screened here; the model's own safety rules still apply.
"""

import re
from typing import Optional

from utils.logger import logger

_DISTRESS = re.compile(
    r"\b(kill(ing)?\s+my\s*self|suicid\w*|end(ing)?\s+(my|this)\s+life|want\s+to\s+die|wanna\s+die|"
    r"self[\s-]?harm|hurt(ing)?\s+my\s*self|cut(ting)?\s+my\s*self|no\s+reason\s+to\s+live|"
    r"marna\s+(hai|chahta|chahti)|khud\s*kushi|aatmahatya)\b",
    re.IGNORECASE,
)

DISTRESS_REPLY = (
    "I'm really glad you told me. You matter, and you don't have to feel this way alone. 💛\n\n"
    "Please talk to someone you trust right now: a parent, a teacher or a friend's parent.\n\n"
    "You can also call **Tele-MANAS on 14416** (free, any time, in many Indian languages). "
    "If you are in danger right now, call **112**.\n\n"
    "I'm here to help with your studies whenever you're ready."
)

BLOCKED_REPLY = (
    "That's not something I can help with. Let's get back to your studies. "
    "What topic would you like to understand better? 📚"
)


async def _record(user_id: Optional[str], level: str, category: str) -> None:
    try:
        from db.client import async_db, get_supabase_client
        await async_db(lambda: get_supabase_client().table("safety_events").insert(
            {"user_id": user_id, "level": level, "category": category}).execute())
    except Exception as e:
        logger.debug(f"[Safety] event not recorded: {e}")


async def _moderation_flags(text: str) -> Optional[str]:
    from config.settings import settings
    if not (settings.MODERATION_BASE_URL and settings.MODERATION_API_KEY):
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.post(f"{settings.MODERATION_BASE_URL.rstrip('/')}/moderations",
                                    headers={"Authorization": f"Bearer {settings.MODERATION_API_KEY}"},
                                    json={"model": settings.MODERATION_MODEL, "input": text})
        res.raise_for_status()
        result = res.json()["results"][0]
        if not result.get("flagged"):
            return None
        cats = {k for k, v in (result.get("categories") or {}).items() if v}
        if any(c.startswith("self-harm") for c in cats):
            return "distress"
        return "blocked"
    except Exception as e:   # moderation outage: don't block learning
        logger.warning(f"[Safety] moderation check skipped: {e}")
        return None


async def screen(text: str, level: Optional[str], user_id: Optional[str]) -> Optional[str]:
    """A reply to send instead of an AI answer, or None when the message is fine."""
    if level != "school" or not text:
        return None
    category = "distress" if _DISTRESS.search(text) else await _moderation_flags(text)
    if not category:
        return None
    await _record(user_id, level, category)
    return DISTRESS_REPLY if category == "distress" else BLOCKED_REPLY
