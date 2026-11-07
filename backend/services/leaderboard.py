"""
Class leaderboard (AGENTS.md Phase 7): this week's learning XP among classmates.

Only for students in a class whose tools include `leaderboard` (school level by default;
institutions can switch it off). Shows first names only, and ranks learning XP, which can't
be farmed by clicking around.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from db.client import async_db, get_supabase_client


async def class_week(user_id: str, top: int = 10) -> Dict[str, Any]:
    from services import levels
    from services.gamification_service import local_today
    eff = await levels.effective_for(user_id)
    if "leaderboard" not in (eff.get("tools") or []) or not eff.get("class_id"):
        return {"enabled": False, "rows": []}
    today = local_today()
    monday = today - timedelta(days=today.weekday())
    pg = get_supabase_client().pg
    rows = await async_db(lambda: pg.fetch(
        """SELECT cm.user_id::text AS user_id, im.display_name, COALESCE(sum(x.xp), 0)::int AS xp
           FROM class_members cm
           JOIN institution_classes c ON c.id = cm.class_id
           LEFT JOIN institution_members im ON im.user_id = cm.user_id AND im.institution_id = c.institution_id
           LEFT JOIN xp_events x ON x.user_id = cm.user_id AND x.day >= %s
           WHERE cm.class_id = %s
           GROUP BY cm.user_id, im.display_name
           ORDER BY xp DESC, im.display_name""", (monday, eff["class_id"])))
    ranked = []
    for i, r in enumerate(rows, 1):
        first = ((r.get("display_name") or "Student").split() or ["Student"])[0]
        ranked.append({"rank": i, "name": first, "xp": r["xp"], "me": r["user_id"] == str(user_id)})
    me = next((r for r in ranked if r["me"]), None)
    shown = ranked[:top]
    if me and me not in shown:
        shown.append(me)
    return {"enabled": True, "week_start": monday.isoformat(), "rows": shown, "size": len(ranked)}
