"""
Who sees what: a learner's level and their effective tools.

effective_for(user_id) combines, in order:
  1. the level: their class's level if they're in a class that has one
     (then locked), else the level they chose, else none yet (needs_level);
  2. the level's tools: catalog defaults, changed by the platform admin;
  3. the class's tools: a class can switch tools off, never on beyond step 2;
  4. hints-first mode and whether answers may go beyond the book.
Results are cached briefly; saving a policy clears the cache.
"""

from typing import Any, Dict, Iterable, Optional

from db.client import async_db, get_supabase_client
from services.tools_catalog import DEFAULT_TOOLS, FALLBACK_LEVEL, HINT_MODES, LEVELS, TOOLS
from utils.cache import get_cache

_TTL = 120
_PREFIX = "levels:eff:"


def _client():
    return get_supabase_client()


async def _rows(table: str, **eq) -> list:
    def run():
        q = _client().table(table).select("*")
        for k, v in eq.items():
            q = q.eq(k, v)
        return q.execute()
    return (await async_db(run)).data or []


async def _student_class(user_id: str) -> Optional[Dict[str, Any]]:
    """The class that sets this student's level: the most recently joined one with a level."""
    links = await async_db(lambda: _client().table("class_members").select("class_id, joined_at")
                           .eq("user_id", user_id).order("joined_at", desc=True).execute())
    ids = [r["class_id"] for r in links.data or []]
    if not ids:
        return None
    classes = await async_db(lambda: _client().table("institution_classes").select("*").in_("id", ids).execute())
    by_id = {c["id"]: c for c in classes.data or []}
    ordered = [by_id[i] for i in ids if i in by_id]
    with_level = [c for c in ordered if c.get("level") in LEVELS]
    return with_level[0] if with_level else (ordered[0] if ordered else None)


async def level_policy(level: str) -> Dict[str, Any]:
    """The tools and switches the platform admin set for a level."""
    tools = set(DEFAULT_TOOLS[level])
    for row in await _rows("level_tool_policies", level=level):
        if row["tool"] in TOOLS:
            (tools.add if row["enabled"] else tools.discard)(row["tool"])
    settings = (await _rows("level_settings", level=level) or [{}])[0]
    return {
        "level": level,
        "tools": [t for t in TOOLS if t in tools],
        "hints_default": bool(settings.get("hints_default", False)),
        "outside_book": bool(settings.get("outside_book", True)),
    }


async def effective_for(user_id: str) -> Dict[str, Any]:
    cache = get_cache()
    cached = await cache.get(_PREFIX + user_id)
    if cached:
        return cached

    cls = await _student_class(user_id)
    own = (await _rows("user_settings", user_id=user_id) or [{}])[0].get("settings") or {}
    own_level = own.get("studyLevel") if own.get("studyLevel") in LEVELS else None

    if cls and cls.get("level") in LEVELS:
        level, locked = cls["level"], True
    else:
        level, locked = own_level, False

    policy = await level_policy(level or FALLBACK_LEVEL)
    tools = set(policy["tools"])
    hint_mode, outside_book = "student_choice", policy["outside_book"]
    if cls:
        for row in await _rows("class_tool_policies", class_id=cls["id"]):
            if not row["enabled"]:
                tools.discard(row["tool"])
        if cls.get("hint_mode") in HINT_MODES:
            hint_mode = cls["hint_mode"]
        outside_book = outside_book and cls.get("allow_outside_book", True) is not False

    result = {
        "level": level,
        "level_label": LEVELS[level]["label"] if level else None,
        "locked": locked,
        "needs_level": level is None,
        "tools": [t for t in TOOLS if t in tools],
        "hint_mode": hint_mode,
        "hints_default": policy["hints_default"],
        "outside_book": outside_book,
        "class_id": cls["id"] if cls else None,
    }
    await cache.set(_PREFIX + user_id, result, ttl=_TTL)
    return result


async def forget(user_id: str) -> None:
    """Drop one user's cached result (e.g. after they join a class)."""
    await get_cache().delete(_PREFIX + user_id)


async def _clear_all() -> None:
    await get_cache().clear_prefix(_PREFIX)


async def set_own_level(user_id: str, level: str) -> None:
    if level not in LEVELS:
        raise ValueError(f"Unknown level: {level}")
    rows = await _rows("user_settings", user_id=user_id)
    settings = dict((rows[0].get("settings") if rows else None) or {})
    settings["studyLevel"] = level
    await async_db(lambda: _client().table("user_settings").upsert(
        {"user_id": user_id, "settings": settings}, on_conflict="user_id").execute())
    await forget(user_id)


def _clean_tools(tools: Dict[str, Any]) -> Dict[str, bool]:
    unknown = set(tools) - set(TOOLS)
    if unknown:
        raise ValueError(f"Unknown tools: {', '.join(sorted(unknown))}")
    return {k: bool(v) for k, v in tools.items()}


async def save_level_policy(level: str, tools: Dict[str, Any], *, hints_default: Optional[bool] = None,
                            outside_book: Optional[bool] = None) -> Dict[str, Any]:
    if level not in LEVELS:
        raise ValueError(f"Unknown level: {level}")
    rows = [{"level": level, "tool": t, "enabled": on} for t, on in _clean_tools(tools).items()]
    if rows:
        await async_db(lambda: _client().table("level_tool_policies")
                       .upsert(rows, on_conflict="level,tool").execute())
    if hints_default is not None or outside_book is not None:
        current = (await _rows("level_settings", level=level) or [{}])[0]
        row = {"level": level,
               "hints_default": current.get("hints_default", False) if hints_default is None else hints_default,
               "outside_book": current.get("outside_book", True) if outside_book is None else outside_book}
        await async_db(lambda: _client().table("level_settings").upsert(row, on_conflict="level").execute())
    await _clear_all()
    return await level_policy(level)


async def class_policy(class_id: str) -> Dict[str, Any]:
    cls = (await _rows("institution_classes", id=class_id) or [None])[0]
    if not cls:
        raise LookupError("Class not found")
    level = cls.get("level") if cls.get("level") in LEVELS else None
    allowed = (await level_policy(level or FALLBACK_LEVEL))["tools"]
    off = {r["tool"] for r in await _rows("class_tool_policies", class_id=class_id) if not r["enabled"]}
    return {
        "class_id": class_id, "level": level, "hint_mode": cls.get("hint_mode") or "student_choice",
        "allow_outside_book": cls.get("allow_outside_book", True) is not False,
        "allowed_tools": allowed,                       # what the platform permits for this level
        "tools": [t for t in allowed if t not in off],  # what this class actually has
    }


async def save_class_policy(class_id: str, tools: Optional[Dict[str, Any]] = None, *,
                            level: Optional[str] = None, hint_mode: Optional[str] = None,
                            allow_outside_book: Optional[bool] = None) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if level is not None:
        if level not in LEVELS:
            raise ValueError(f"Unknown level: {level}")
        updates["level"] = level
    if hint_mode is not None:
        if hint_mode not in HINT_MODES:
            raise ValueError(f"Unknown hint mode: {hint_mode}")
        updates["hint_mode"] = hint_mode
    if allow_outside_book is not None:
        updates["allow_outside_book"] = bool(allow_outside_book)
    if updates:
        await async_db(lambda: _client().table("institution_classes").update(updates).eq("id", class_id).execute())
    if tools:
        rows = [{"class_id": class_id, "tool": t, "enabled": on} for t, on in _clean_tools(tools).items()]
        await async_db(lambda: _client().table("class_tool_policies")
                       .upsert(rows, on_conflict="class_id,tool").execute())
    await _clear_all()
    return await class_policy(class_id)
