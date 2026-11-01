"""
Which students are stuck (AGENTS.md Phase 7, teacher view).

Built only from learning data: practice activity, mastery changes and open mistakes.
Teachers never see chats or memory notes (owner decision 13).

    signals = await stuck_signals({(user_id, project_id), ...})
    -> {(user_id, project_id): [{"reason": "inactive" | "falling" | "mistakes", "detail": "..."}]}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List, Tuple

from db.client import async_db, get_supabase_client

INACTIVE_DAYS = 7
FALLING_DRIFT = -0.15     # summed mastery change over 14 days (one topic dropping 15 points, or several a little)
MISTAKES_OPEN = 3


def judge(last_practice, week_answers: int, drift: float, open_mistakes: int, top_topic: str,
          now: datetime) -> List[Dict[str, str]]:
    """The reasons a student needs help (pure, so it can be tested)."""
    out = []
    if week_answers == 0:
        if last_practice is None:
            out.append({"reason": "inactive", "detail": "Hasn't started practising yet"})
        else:
            days = (now - last_practice).days
            out.append({"reason": "inactive", "detail": f"No practice for {days} days"})
    if drift <= FALLING_DRIFT:
        out.append({"reason": "falling", "detail": "Mastery is slipping on recent topics"})
    if open_mistakes >= MISTAKES_OPEN:
        where = f", mostly on {top_topic}" if top_topic else ""
        out.append({"reason": "mistakes", "detail": f"{open_mistakes} mistakes not fixed yet{where}"})
    return out


async def stuck_signals(pairs: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], List[Dict[str, str]]]:
    pairs = [(str(u), str(p)) for u, p in pairs if u and p]
    if not pairs:
        return {}
    pids = sorted({p for _, p in pairs})
    pg = get_supabase_client().pg

    def run():
        practice = pg.fetch(
            """SELECT user_id::text, project_id::text, max(created_at) AS last,
                      count(*) FILTER (WHERE created_at >= now() - interval '7 days') AS week,
                      COALESCE(sum(p_known_after - p_known_before)
                               FILTER (WHERE created_at >= now() - interval '14 days'), 0) AS drift
               FROM learning_events WHERE project_id = ANY(%s::uuid[]) GROUP BY 1, 2""", (pids,))
        mistakes = pg.fetch(
            """SELECT user_id::text, project_id::text, count(*) AS n,
                      mode() WITHIN GROUP (ORDER BY topic) AS topic
               FROM learner_mistakes WHERE project_id = ANY(%s::uuid[]) AND fixed_at IS NULL
                 AND created_at >= now() - interval '14 days' GROUP BY 1, 2""", (pids,))
        return practice, mistakes

    practice, mistakes = await async_db(run)
    p = {(r["user_id"], r["project_id"]): r for r in practice}
    m = {(r["user_id"], r["project_id"]): r for r in mistakes}
    now = datetime.now(timezone.utc)
    out = {}
    for key in pairs:
        pr, mi = p.get(key) or {}, m.get(key) or {}
        last = pr.get("last")
        if isinstance(last, str):
            last = datetime.fromisoformat(last.replace("Z", "+00:00"))
        out[key] = judge(last, int(pr.get("week") or 0), float(pr.get("drift") or 0),
                         int(mi.get("n") or 0), mi.get("topic") or "", now)
    return out
