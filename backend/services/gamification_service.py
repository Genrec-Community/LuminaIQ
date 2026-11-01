"""
Gamification that rewards learning, not clicking (AGENTS.md Phase 7).

XP is granted only by award(), and only from places where learning is measured on the
server (never from what the browser claims):

    mastery_gain    a topic's mastery rose (learning_engine.record): XP = the rise in points
    mistake_fixed   a question answered wrong before is now right (learner_model.mark_fixed)
    review_on_time  a spaced-repetition review done while the card was due
    daily_goal      today's adaptive goal reached (services/daily_goal.py)
    exam_plan_step  a learning-path topic completed for the first time
    comeback        the first learning after a break of 3+ days (instead of a punishing reset)

Each kind has a daily cap and most achievements a dedupe key, so nothing can be farmed.
Every grant is a row in xp_events; user_gamification keeps the totals, streak and badges.

Streaks count days with any XP. One automatic "freeze" per week covers a single missed day.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db.client import async_db, get_supabase_client
from utils.logger import logger

# ======================== Levels ========================
# Learning XP comes slower than the old click XP (a good day is ~60-150), so the curve is gentler.

LEVELS = [
    {"level": 1, "title": "Curious Reader", "xp_required": 0},
    {"level": 2, "title": "Page Turner", "xp_required": 60},
    {"level": 3, "title": "Knowledge Seeker", "xp_required": 150},
    {"level": 4, "title": "Study Warrior", "xp_required": 300},
    {"level": 5, "title": "Quick Learner", "xp_required": 500},
    {"level": 6, "title": "Bookworm", "xp_required": 750},
    {"level": 7, "title": "Topic Explorer", "xp_required": 1050},
    {"level": 8, "title": "Brain Builder", "xp_required": 1400},
    {"level": 9, "title": "Quiz Champion", "xp_required": 1850},
    {"level": 10, "title": "Knowledge Knight", "xp_required": 2400},
    {"level": 11, "title": "Study Sage", "xp_required": 3100},
    {"level": 12, "title": "Wisdom Keeper", "xp_required": 4000},
    {"level": 13, "title": "Mind Master", "xp_required": 5100},
    {"level": 14, "title": "Grand Scholar", "xp_required": 6400},
    {"level": 15, "title": "Lumina Legend", "xp_required": 8000},
]

# ======================== XP rules ========================

FIXED_XP = {"mistake_fixed": 15, "review_on_time": 4, "daily_goal": 30, "exam_plan_step": 10, "comeback": 20}
DAILY_CAPS = {"mastery_gain": 150, "mistake_fixed": 90, "review_on_time": 60, "daily_goal": 30,
              "exam_plan_step": 50, "comeback": 20}
KINDS = set(DAILY_CAPS)
COMEBACK_AFTER_DAYS = 3

LABELS = {
    "mastery_gain": "Mastery up", "mistake_fixed": "Mistake fixed", "review_on_time": "Review on time",
    "daily_goal": "Daily goal reached", "exam_plan_step": "Plan step done", "comeback": "Welcome back",
}

# ======================== Badges (learning only) ========================

BADGE_DEFINITIONS = [
    {"id": "first_gain", "title": "First Steps", "description": "Raise your mastery of a topic", "icon": "rocket", "category": "milestone"},
    {"id": "mastery_100", "title": "Getting Stronger", "description": "Gain 100 mastery points", "icon": "trending-up", "category": "milestone"},
    {"id": "mastery_500", "title": "Deep Understanding", "description": "Gain 500 mastery points", "icon": "brain", "category": "milestone"},
    {"id": "mistakes_10", "title": "Learns From Mistakes", "description": "Fix 10 questions you once got wrong", "icon": "check-circle", "category": "achievement"},
    {"id": "mistakes_50", "title": "Comeback Kid", "description": "Fix 50 questions you once got wrong", "icon": "award", "category": "achievement"},
    {"id": "reviews_50", "title": "Right On Time", "description": "Do 50 reviews when they're due", "icon": "repeat", "category": "habit"},
    {"id": "goals_7", "title": "Goal Getter", "description": "Reach your daily goal 7 times", "icon": "target", "category": "habit"},
    {"id": "goals_30", "title": "Unstoppable", "description": "Reach your daily goal 30 times", "icon": "trophy", "category": "habit"},
    {"id": "streak_7", "title": "One Week Strong", "description": "Learn something 7 days in a row", "icon": "timer", "category": "habit"},
    {"id": "streak_30", "title": "Habit Formed", "description": "Learn something 30 days in a row", "icon": "star", "category": "habit"},
    {"id": "plan_10", "title": "Path Finder", "description": "Complete 10 learning-path topics", "icon": "map", "category": "milestone"},
    {"id": "level_5", "title": "Rising Star", "description": "Reach Level 5", "icon": "trending-up", "category": "level"},
    {"id": "level_10", "title": "Elite Learner", "description": "Reach Level 10", "icon": "shield", "category": "level"},
    {"id": "level_15", "title": "Lumina Legend", "description": "Reach the top level", "icon": "crown", "category": "level"},
]

_STAT_FOR_KIND = {"mastery_gain": "mastery_points", "mistake_fixed": "mistakes_fixed",
                  "review_on_time": "reviews_on_time", "daily_goal": "goals_met",
                  "exam_plan_step": "plan_steps", "comeback": "comebacks"}

DEFAULT_STATS = {"mastery_points": 0, "mistakes_fixed": 0, "reviews_on_time": 0, "goals_met": 0,
                 "plan_steps": 0, "comebacks": 0, "streak_days": 0, "best_streak": 0,
                 "last_active_date": "", "freeze_week": ""}

# How each level sees progress (owner decision: presentation by level)
STYLES = {"school": "playful", "higher_secondary": "exam", "ugpg": "quiet", "general": "quiet", "research": "milestones"}


def style_for(level: Optional[str]) -> str:
    return STYLES.get(level or "general", "quiet")


def local_today() -> date:
    from services.usage_service import _tz
    return datetime.now(_tz()).date()


def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def calculate_level(total_xp: int) -> Dict[str, Any]:
    current, nxt = LEVELS[0], LEVELS[1]
    for i, lvl in enumerate(LEVELS):
        if total_xp >= lvl["xp_required"]:
            current, nxt = lvl, (LEVELS[i + 1] if i + 1 < len(LEVELS) else None)
        else:
            break
    if nxt:
        have = total_xp - current["xp_required"]
        need = nxt["xp_required"] - current["xp_required"]
        progress = round(100 * have / need, 1)
    else:
        have, need, progress = 0, 0, 100
    return {"level": current["level"], "title": current["title"], "xp_in_level": have, "xp_needed": need,
            "progress": progress, "next_level": nxt}


def update_streak(stats: Dict[str, Any], today: date) -> Dict[str, Any]:
    """
    Advance the streak for a day with learning. Returns {"comeback": bool, "freeze_used": bool}.
    One missed day is covered by the week's freeze; a longer break restarts at 1 with a comeback bonus.
    """
    last = stats.get("last_active_date") or ""
    out = {"comeback": False, "freeze_used": False}
    if last == today.isoformat():
        return out
    if not last:
        stats["streak_days"] = 1
    else:
        gap = (today - date.fromisoformat(last)).days
        if gap == 1:
            stats["streak_days"] = int(stats.get("streak_days") or 0) + 1
        elif gap == 2 and stats.get("freeze_week") != _iso_week(today):
            stats["streak_days"] = int(stats.get("streak_days") or 0) + 1
            stats["freeze_week"] = _iso_week(today)
            out["freeze_used"] = True
        else:
            stats["streak_days"] = 1
            out["comeback"] = gap >= COMEBACK_AFTER_DAYS
    stats["last_active_date"] = today.isoformat()
    stats["best_streak"] = max(int(stats.get("best_streak") or 0), int(stats["streak_days"]))
    return out


def _earned_badges(stats: Dict[str, Any], level: int, have: set) -> List[Dict[str, Any]]:
    s = lambda k: int(stats.get(k) or 0)   # noqa: E731
    conditions = {
        "first_gain": s("mastery_points") >= 1, "mastery_100": s("mastery_points") >= 100,
        "mastery_500": s("mastery_points") >= 500, "mistakes_10": s("mistakes_fixed") >= 10,
        "mistakes_50": s("mistakes_fixed") >= 50, "reviews_50": s("reviews_on_time") >= 50,
        "goals_7": s("goals_met") >= 7, "goals_30": s("goals_met") >= 30,
        "streak_7": s("streak_days") >= 7, "streak_30": s("streak_days") >= 30, "plan_10": s("plan_steps") >= 10,
        "level_5": level >= 5, "level_10": level >= 10, "level_15": level >= 15,
    }
    return [b for b in BADGE_DEFINITIONS if b["id"] not in have and conditions.get(b["id"])]


# ======================== Awarding (one transaction) ========================

def award_tx(pg, user_id: str, kind: str, xp: Optional[int] = None, dedupe_key: Optional[str] = None,
             meta: Optional[Dict[str, Any]] = None, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """Grant XP inside one database transaction. None when capped, a repeat, or worth nothing."""
    if kind not in KINDS:
        raise ValueError(f"Unknown XP kind: {kind}")
    amount = int(FIXED_XP.get(kind, 0) if xp is None else xp)
    if amount <= 0:
        return None
    today = today or local_today()
    with pg.pool.connection() as conn:
        with conn.transaction():
            conn.execute("""INSERT INTO user_gamification (user_id, total_xp, level, badges, stats)
                            VALUES (%s, 0, 1, '[]'::jsonb, %s::jsonb) ON CONFLICT (user_id) DO NOTHING""",
                         (str(user_id), json.dumps(DEFAULT_STATS)))
            row = conn.execute("SELECT * FROM user_gamification WHERE user_id = %s FOR UPDATE",
                               (str(user_id),)).fetchone()
            if dedupe_key and conn.execute("SELECT 1 FROM xp_events WHERE user_id = %s AND dedupe_key = %s",
                                           (user_id, dedupe_key)).fetchone():
                return None
            stats = {**DEFAULT_STATS, **(row["stats"] or {})}
            events: List[Dict[str, Any]] = []

            def grant(k: str, want: int, key: Optional[str], m: Dict[str, Any]) -> int:
                used = conn.execute("SELECT COALESCE(sum(xp), 0) AS n FROM xp_events WHERE user_id = %s AND day = %s "
                                    "AND kind = %s", (user_id, today, k)).fetchone()["n"]
                give = min(want, DAILY_CAPS[k] - int(used))
                if give <= 0:
                    return 0
                ev = conn.execute(
                    """INSERT INTO xp_events (user_id, kind, xp, day, dedupe_key, meta) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                       RETURNING id, created_at""", (user_id, k, give, today, key, json.dumps(m))).fetchone()
                stat = _STAT_FOR_KIND[k]
                stats[stat] = int(stats.get(stat) or 0) + (give if k == "mastery_gain" else 1)
                events.append({"id": ev["id"], "kind": k, "label": LABELS[k], "xp": give, "meta": m,
                               "created_at": ev["created_at"].isoformat()})
                return give

            if not grant(kind, amount, dedupe_key, meta or {}):
                return None
            streak = update_streak(stats, today)
            if streak["comeback"]:
                grant("comeback", FIXED_XP["comeback"], f"comeback:{today.isoformat()}", {})
            old_xp = int(row["total_xp"] or 0)
            new_xp = old_xp + sum(e["xp"] for e in events)
            old_level, info = calculate_level(old_xp)["level"], calculate_level(new_xp)
            badges = list(row["badges"] or [])
            new_badges = _earned_badges(stats, info["level"], {b.get("id") for b in badges})
            now = datetime.now(timezone.utc).isoformat()
            badges += [{**b, "earned_at": now} for b in new_badges]
            conn.execute("""UPDATE user_gamification SET total_xp = %s, level = %s, badges = %s::jsonb, stats = %s::jsonb,
                            updated_at = now() WHERE user_id = %s""",
                         (new_xp, info["level"], json.dumps(badges), json.dumps(stats), str(user_id)))
    return {"events": events, "xp_earned": sum(e["xp"] for e in events), "total_xp": new_xp,
            "level": info["level"], "level_title": info["title"], "leveled_up": info["level"] > old_level,
            "new_badges": new_badges, "streak_days": stats["streak_days"], "freeze_used": streak["freeze_used"]}


class GamificationService:
    def __init__(self):
        self.client = get_supabase_client()

    @staticmethod
    def _pg():
        return get_supabase_client().pg

    async def award(self, user_id: str, kind: str, xp: Optional[int] = None, dedupe_key: Optional[str] = None,
                    meta: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Grant XP for learning (never raises: a reward must not break a student's request)."""
        if not user_id:
            return None
        try:
            pg = self._pg()
            return await async_db(lambda: award_tx(pg, user_id, kind, xp, dedupe_key, meta))
        except Exception as e:
            logger.warning(f"[XP] {kind} not awarded: {e}")
            return None

    async def events_since(self, user_id: str, since: Optional[str], limit: int = 20) -> List[Dict[str, Any]]:
        if not since:
            return []
        pg = self._pg()
        rows = await async_db(lambda: pg.fetch(
            """SELECT id, kind, xp, meta, created_at FROM xp_events WHERE user_id = %s AND created_at > %s
               ORDER BY created_at LIMIT %s""", (user_id, since, limit)))
        return [{"id": r["id"], "kind": r["kind"], "label": LABELS.get(r["kind"], r["kind"]), "xp": r["xp"],
                 "meta": r["meta"], "created_at": str(r["created_at"])} for r in rows]

    async def get_gamification(self, user_id: str, since: Optional[str] = None) -> Dict[str, Any]:
        """The learner's progress, how to show it (style), today's goal and XP earned since `since`."""
        from services import daily_goal, levels
        row = {}
        try:
            res = await async_db(lambda: self.client.table("user_gamification").select("*")
                                 .eq("user_id", str(user_id)).limit(1).execute())
            row = res.data[0] if res.data else {}
        except Exception as e:
            logger.warning(f"[XP] state unavailable: {e}")
        stats = {**DEFAULT_STATS, **(row.get("stats") or {})}
        total = int(row.get("total_xp") or 0)
        info = calculate_level(total)
        today = local_today()
        last = stats.get("last_active_date") or ""
        # A streak shown today is only "alive" if yesterday (or a covered day) had learning
        alive = bool(last) and (today - date.fromisoformat(last)).days <= (
            2 if stats.get("freeze_week") != _iso_week(today) else 1)
        try:
            eff = await levels.effective_for(user_id)
        except Exception:
            eff = {"level": None, "tools": []}
        try:
            goal = await daily_goal.today(user_id, eff.get("level"))
        except Exception as e:
            logger.debug(f"[XP] goal unavailable: {e}")
            goal = None
        try:
            recent = await self.events_since(user_id, since)
        except Exception:
            recent = []
        return {
            "total_xp": total, "level": info["level"], "level_title": info["title"],
            "xp_in_level": info["xp_in_level"], "xp_needed": info["xp_needed"], "level_progress": info["progress"],
            "next_level": info["next_level"], "badges": row.get("badges") or [], "stats": stats,
            "streak_days": int(stats.get("streak_days") or 0) if alive else 0,
            "best_streak": int(stats.get("best_streak") or 0),
            "freeze_available": stats.get("freeze_week") != _iso_week(today),
            "style": style_for(eff.get("level")), "level_key": eff.get("level"),
            "leaderboard": "leaderboard" in (eff.get("tools") or []) and bool(eff.get("class_id")),
            "daily_goal": goal, "events": recent, "server_time": datetime.now(timezone.utc).isoformat(),
            "all_levels": LEVELS, "all_badges": BADGE_DEFINITIONS, "daily_caps": DAILY_CAPS,
        }

    # Kept for older callers: activity no longer earns XP; this just returns the state
    async def award_xp(self, user_id: str, activity_type: str, meta: Dict[str, Any] = None,
                       since: Optional[str] = None) -> Dict[str, Any]:
        state = await self.get_gamification(user_id, since)
        events = state["events"]
        return {**state, "xp_earned": sum(e["xp"] for e in events), "leveled_up": False, "new_badges": []}


gamification = GamificationService()
