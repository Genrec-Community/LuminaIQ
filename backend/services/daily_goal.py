"""
One adaptive goal a day (AGENTS.md Phase 7): "answer N questions", sized to the learner.

    target = level base, nudged towards the learner's own recent pace, and raised as the
             exam gets close; always between MIN_TARGET and MAX_TARGET.
    focus  = the weakest topic in the book they used last, and how many reviews are due.

The goal is created on the first look of the day and then stays fixed. Progress counts
answers recorded today (quizzes, Power Hour, flashcard grades) plus reviews done on time.
Reaching it pays the daily_goal XP once.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from utils.logger import logger

BASE = {"school": 10, "higher_secondary": 20, "ugpg": 15, "research": 10, "general": 10}
MIN_TARGET, MAX_TARGET = 5, 40


def size_goal(level: Optional[str], pace: float, days_to_exam: Optional[int]) -> Dict[str, Any]:
    """The day's target and a short reason (pure, so it can be tested)."""
    base = BASE.get(level or "general", 10)
    reason = ["usual pace for your level"]
    target = float(base)
    if pace > 0:
        target = 0.6 * base + 0.4 * min(pace * 1.1, base * 2)
        reason = ["based on your recent pace"]
    if days_to_exam is not None and 0 <= days_to_exam <= 3:
        target *= 1.5
        reason.append("exam in a few days")
    elif days_to_exam is not None and 0 <= days_to_exam <= 14:
        target *= 1.25
        reason.append("exam coming up")
    return {"target": int(max(MIN_TARGET, min(MAX_TARGET, round(target)))), "why": ", ".join(reason)}


def _pg():
    from db.client import get_supabase_client
    return get_supabase_client().pg


async def _db(fn):
    from db.client import async_db
    return await async_db(fn)


def _days_to_exam(exam_date: Optional[str], today: date) -> Optional[int]:
    if not exam_date:
        return None
    try:
        return (date.fromisoformat(str(exam_date)[:10]) - today).days
    except ValueError:
        return None


def _bounds(today: date):
    from services.usage_service import _tz
    start = datetime.combine(today, datetime.min.time(), tzinfo=_tz())
    return start, start + timedelta(days=1)


async def progress(user_id: str, today: date) -> int:
    pg = _pg()
    start, end = _bounds(today)
    rows = await _db(lambda: pg.fetch(
        """SELECT (SELECT count(*) FROM learning_events WHERE user_id = %s AND created_at >= %s AND created_at < %s)
                + (SELECT count(*) FROM xp_events WHERE user_id = %s AND day = %s AND kind = 'review_on_time') AS n""",
        (user_id, start, end, user_id, today)))
    return int(rows[0]["n"])


async def _create(user_id: str, level: Optional[str], today: date) -> Dict[str, Any]:
    if level is None:
        # Created from a background check (e.g. after a quiz): size it for the learner's real level
        try:
            from services import levels
            level = (await levels.effective_for(user_id)).get("level")
        except Exception:
            level = None
    pg = _pg()
    start, _ = _bounds(today)
    week = await _db(lambda: pg.fetch(
        """SELECT count(*)::float / GREATEST(count(DISTINCT (created_at AT TIME ZONE 'UTC')::date), 1) AS pace
           FROM learning_events WHERE user_id = %s AND created_at >= %s AND created_at < %s""",
        (user_id, start - timedelta(days=7), start)))
    pace = float(week[0]["pace"] or 0)
    exam_date = None
    try:
        from services.user_data_service import user_data
        exam_date = (await user_data.get_settings(user_id) or {}).get("examDate")
    except Exception:
        pass
    sized = size_goal(level, pace, _days_to_exam(exam_date, today))
    focus: Dict[str, Any] = {"why": sized["why"]}
    try:
        recent = await _db(lambda: pg.fetch(
            "SELECT project_id FROM learning_events WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,)))
        if recent:
            from services.learner_model import weak_topics
            weak = await weak_topics(user_id, str(recent[0]["project_id"]), limit=1)
            if weak:
                focus.update(topic=weak[0][0], project_id=str(recent[0]["project_id"]))
        due = await _db(lambda: pg.fetch(
            "SELECT count(*) AS n FROM review_cards WHERE user_id = %s AND next_review <= now()", (user_id,)))
        focus["due_reviews"] = int(due[0]["n"])
    except Exception as e:
        logger.debug(f"[Goal] focus unavailable: {e}")
    days = _days_to_exam(exam_date, today)
    if days is not None and days >= 0:
        focus["days_to_exam"] = days
    rows = await _db(lambda: pg.fetch(
        """INSERT INTO daily_goals (user_id, day, target, focus) VALUES (%s, %s, %s, %s::jsonb)
           ON CONFLICT (user_id, day) DO UPDATE SET user_id = EXCLUDED.user_id
           RETURNING target, focus, completed_at""", (user_id, today, sized["target"], _json(focus))))
    return rows[0]


def _json(v) -> str:
    import json
    return json.dumps(v)


async def today(user_id: str, level: Optional[str] = None) -> Dict[str, Any]:
    """Today's goal with progress; reaching it pays the daily_goal XP (once)."""
    from services.gamification_service import local_today
    day = local_today()
    pg = _pg()
    rows = await _db(lambda: pg.fetch("SELECT target, focus, completed_at FROM daily_goals WHERE user_id = %s AND day = %s",
                                      (user_id, day)))
    goal = rows[0] if rows else await _create(user_id, level, day)
    done = await progress(user_id, day)
    completed = goal.get("completed_at")
    if not completed and done >= goal["target"]:
        await _db(lambda: pg.fetch("UPDATE daily_goals SET completed_at = now() WHERE user_id = %s AND day = %s",
                                   (user_id, day)))
        from services.gamification_service import gamification
        await gamification.award(user_id, "daily_goal", dedupe_key=f"goal:{day.isoformat()}")
        completed = True
    return {"day": day.isoformat(), "target": goal["target"], "progress": min(done, goal["target"]),
            "answered": done, "completed": bool(completed), "focus": goal.get("focus") or {}}
