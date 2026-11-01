"""
The learner model (AGENTS.md Phase 5, layer 2): what a student knows and gets wrong.

    snap = await learner_model.snapshot(user_id, project_id, across_books=True)
    snap.weak / snap.strong     # [(topic, mastery 0..1)], from topic_mastery (with forgetting)
    snap.mistakes               # recent wrong answers, with the misconception when one was identified
    await learner_model.record_mistakes(user_id, project_id, topic, wrong_answers)   # after a quiz

Built only from learning data (quizzes, recalls, flashcards), never from chats, so it's
safe for every level, including Class 5-10. Teachers may see this layer (progress),
never chats or memory notes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import logger

WEAK_BELOW = 0.5
STRONG_FROM = 0.8
MIN_ATTEMPTS = 2


@dataclass
class Snapshot:
    weak: List[Tuple[str, float]] = field(default_factory=list)
    strong: List[Tuple[str, float]] = field(default_factory=list)
    other_books_weak: List[Tuple[str, float]] = field(default_factory=list)
    mistakes: List[Dict[str, Any]] = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.weak or self.strong or self.other_books_weak or self.mistakes)


def _pg():
    from db.client import get_supabase_client
    return get_supabase_client().pg


async def _db(fn):
    from db.client import async_db
    return await async_db(fn)


def _rank(rows: List[Dict[str, Any]]) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    from services.learning_engine import effective_mastery
    scored = [(r["topic"], effective_mastery(r)) for r in rows if int(r.get("attempts") or 0) >= MIN_ATTEMPTS]
    weak = sorted([s for s in scored if s[1] < WEAK_BELOW], key=lambda s: s[1])
    strong = sorted([s for s in scored if s[1] >= STRONG_FROM], key=lambda s: -s[1])
    return weak, strong


async def weak_topics(user_id: str, project_id: str, limit: int = 5) -> List[Tuple[str, float]]:
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        "SELECT * FROM topic_mastery WHERE user_id = %s AND project_id = %s", (user_id, project_id)))
    return _rank(rows)[0][:limit]


async def snapshot(user_id: str, project_id: str, across_books: bool = True) -> Snapshot:
    """Everything layer 2 knows about this student for this book (and others, if allowed)."""
    snap = Snapshot()
    if not user_id:
        return snap
    pg = _pg()
    try:
        rows = await _db(lambda: pg.fetch("SELECT * FROM topic_mastery WHERE user_id = %s", (user_id,)))
        here = [r for r in rows if str(r["project_id"]) == str(project_id)]
        snap.weak, snap.strong = (lambda w_s: (w_s[0][:5], w_s[1][:3]))(_rank(here))
        if across_books:
            elsewhere = [r for r in rows if str(r["project_id"]) != str(project_id)]
            snap.other_books_weak = _rank(elsewhere)[0][:3]
        scope = "" if across_books else "AND project_id = %s"
        params = (user_id,) if across_books else (user_id, project_id)
        snap.mistakes = await _db(lambda: pg.fetch(
            f"""SELECT topic, question, wrong_answer, correct_answer, misconception FROM learner_mistakes
                WHERE user_id = %s AND fixed_at IS NULL {scope}
                ORDER BY created_at DESC LIMIT 5""", params))
    except Exception as e:
        logger.debug(f"[LearnerModel] snapshot unavailable: {e}")
    return snap


async def record_mistakes(user_id: str, project_id: str, topic: str, wrong: List[Dict[str, str]]) -> List[str]:
    """
    Store wrong answers ({question, wrong_answer, correct_answer}) and queue misconception
    tagging. A question answered correctly now marks its earlier mistake as fixed.
    """
    if not user_id:
        return []
    pg = _pg()
    ids: List[str] = []
    try:
        for w in wrong:
            rows = await _db(lambda w=w: pg.fetch(
                """INSERT INTO learner_mistakes (user_id, project_id, topic, question, wrong_answer, correct_answer)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (user_id, project_id, topic or "", (w.get("question") or "")[:2000],
                 (w.get("wrong_answer") or "")[:500], (w.get("correct_answer") or "")[:500])))
            ids.append(str(rows[0]["id"]))
    except Exception as e:
        logger.warning(f"[LearnerModel] mistakes not recorded: {e}")
        return ids
    if ids:
        try:
            from services.jobs import enqueue
            await enqueue("tag_mistakes", {"ids": ids}, user_id=user_id)
        except Exception as e:
            logger.debug(f"[LearnerModel] tagging not queued: {e}")
    return ids


async def mark_fixed(user_id: str, project_id: str, questions: List[str]) -> int:
    """Questions now answered correctly: their open mistakes are fixed."""
    if not user_id or not questions:
        return 0
    pg = _pg()
    try:
        rows = await _db(lambda: pg.fetch(
            """UPDATE learner_mistakes SET fixed_at = now()
               WHERE user_id = %s AND project_id = %s AND fixed_at IS NULL AND question = ANY(%s)
               RETURNING id""", (user_id, project_id, list(questions))))
    except Exception as e:
        logger.debug(f"[LearnerModel] fix marking skipped: {e}")
        return 0
    from services.gamification_service import gamification
    for r in rows:
        await gamification.award(user_id, "mistake_fixed", dedupe_key=f"fixed:{r['id']}",
                                 meta={"project_id": project_id})
    return len(rows)


_TAG_PROMPT = (
    "For each wrong answer below, name the student's likely misconception in at most 15 words "
    "(e.g. 'confuses mass with weight'). If it looks like a slip or you can't tell, use an empty string. "
    'Reply with a JSON array of strings, one per item, in order, and nothing else.'
)


async def tag_mistakes(ids: List[str]) -> int:
    """Fill in misconceptions for these mistakes with one small-model call."""
    from services.llm_service import llm_service
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        "SELECT id, topic, question, wrong_answer, correct_answer FROM learner_mistakes "
        "WHERE id = ANY(%s::uuid[]) AND misconception IS NULL ORDER BY created_at", (list(ids),)))
    if not rows:
        return 0
    items = "\n".join(f"{i + 1}. Topic: {r['topic']}\n   Question: {r['question'][:400]}\n"
                      f"   Student answered: {r['wrong_answer']}\n   Correct answer: {r['correct_answer']}"
                      for i, r in enumerate(rows))
    out = await llm_service.chat_completion(
        [{"role": "system", "content": _TAG_PROMPT}, {"role": "user", "content": items}],
        temperature=0, max_tokens=60 * len(rows) + 50, task="memory")
    try:
        start, end = out.index("["), out.rindex("]") + 1
        tags = json.loads(out[start:end])
    except Exception:
        tags = []
    done = 0
    for r, tag in zip(rows, tags):
        tag = str(tag or "").strip()[:200]
        await _db(lambda r=r, tag=tag: pg.fetch(
            "UPDATE learner_mistakes SET misconception = %s WHERE id = %s", (tag, r["id"])))
        done += 1
    return done
