"""
Product data the admin analytics (and an investor deck) is built on:

- product events: a small, fixed list of names, so funnels stay comparable over time
- sign-up attribution: which channel a user came from (first touch, saved once)
- consent: append-only, versioned; the latest row per kind is the current answer
- feedback: thumbs on AI answers, NPS, bug reports
- assessment attempts: one row per finished quiz, with per-question responses
- data requests: export / delete

Every write here is best-effort: analytics must never break a request.
Privacy: no chat text, no full URLs (referrer host only), no raw IP addresses.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from config.settings import settings
from db.client import async_db, get_supabase_client

logger = logging.getLogger(__name__)

# Keep this list short and the names stable: renaming one breaks every chart that uses it.
EVENTS = {
    "page_view",
    "signup_started", "signup_completed",
    "onboarding_level_chosen",
    "upload_started", "upload_succeeded", "upload_failed", "first_document_processed",
    "book_imported",
    "chat_sent",
    "quiz_started", "quiz_completed",
    "flashcards_started", "notes_generated", "mindmap_generated",
    "paywall_shown", "checkout_started", "payment_succeeded", "payment_failed",
    "feedback_given",
}

# Bump when the Terms / Privacy text changes: users are asked again
TERMS_VERSION = "terms-2026-11"
PRIVACY_VERSION = "privacy-2026-11"
PARENTAL_VERSION = "parental-2026-11"
CONSENT_KINDS = {"terms", "privacy", "marketing_email", "parental"}

# Levels that are (mostly) under 18: DPDP Act needs a parent's or guardian's consent for them
MINOR_LEVELS = {"school", "higher_secondary"}

FEEDBACK_KINDS = {"answer_rating", "nps", "bug", "idea"}
MAX_PROPS_KEYS = 20
MAX_TEXT = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(v: Any, n: int = MAX_TEXT) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s[:n] if s else None


def _clean_props(props: Any) -> Dict[str, Any]:
    """Flat, small and free of anything that looks like an email address."""
    if not isinstance(props, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in list(props.items())[:MAX_PROPS_KEYS]:
        if isinstance(v, (int, float, bool)) or v is None:
            out[str(k)[:40]] = v
        elif isinstance(v, str) and "@" not in v:
            out[str(k)[:40]] = v[:MAX_TEXT]
    return out


def hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    return hashlib.sha256((settings.SECRET_KEY + "|" + ip).encode()).hexdigest()[:32]


def _db():
    return get_supabase_client()


# ---------------------------------------------------------------- events

async def track(events: Iterable[Dict[str, Any]], user_id: Optional[str] = None,
                anon_id: Optional[str] = None, session_id: Optional[str] = None,
                platform: Optional[str] = None) -> int:
    """Save known events; unknown names are dropped. Returns how many were saved."""
    rows: List[Dict[str, Any]] = []
    for e in events:
        name = (e or {}).get("name")
        if name not in EVENTS:
            continue
        rows.append({
            "user_id": user_id, "anon_id": _clip(anon_id, 64), "session_id": _clip(session_id, 64),
            "name": name, "project_id": _uuid_or_none(e.get("project_id")),
            "props": _clean_props(e.get("props")), "platform": _clip(platform, 20),
            "path": _clip(_strip_query(e.get("path")), 200),
        })
    if not rows:
        return 0
    try:
        await async_db(lambda: _db().table("product_events").insert(rows).execute())
        return len(rows)
    except Exception as ex:
        logger.warning(f"[product_events] not saved: {ex}")
        return 0


async def track_server(name: str, user_id: Optional[str], project_id: Optional[str] = None,
                       **props: Any) -> None:
    """An event the server knows happened (payments, processing results, finished quizzes)."""
    await track([{"name": name, "project_id": project_id, "props": props}], user_id=user_id, platform="server")


async def link_anon(user_id: str, anon_id: Optional[str]) -> None:
    """Give a user's pre-sign-up events their user id (landing → sign-up funnel)."""
    if not anon_id:
        return
    try:
        await async_db(lambda: _db().pg.fetch(
            "UPDATE product_events SET user_id = %s WHERE anon_id = %s AND user_id IS NULL RETURNING id",
            (user_id, anon_id[:64])))
    except Exception as ex:
        logger.warning(f"[product_events] anon link failed: {ex}")


def _strip_query(path: Any) -> Optional[str]:
    if not path:
        return None
    return str(path).split("?", 1)[0].split("#", 1)[0]


def _uuid_or_none(v: Any) -> Optional[str]:
    import uuid
    try:
        return str(uuid.UUID(str(v))) if v else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- attribution

_SOCIAL = ("facebook", "instagram", "youtube", "whatsapp", "t.co", "twitter", "x.com", "linkedin",
           "reddit", "telegram", "snapchat", "quora", "discord", "threads.net")
_SEARCH = ("google.", "bing.", "duckduckgo", "yahoo.", "yandex", "ecosia", "baidu")


def channel_for(a: Dict[str, Any]) -> str:
    """One label per sign-up, from UTM first, then invite/referral codes, then the referrer."""
    medium = (a.get("utm_medium") or "").lower()
    source = (a.get("utm_source") or "").lower()
    host = (a.get("referrer_host") or "").lower()
    if medium in ("cpc", "ppc", "paid", "paid_social", "display", "ads") or "ads" in source:
        return "paid"
    if a.get("invite_code"):
        return "school"
    if a.get("referral_code") or medium == "referral":
        return "referral"
    if medium == "email" or source in ("email", "newsletter"):
        return "email"
    if medium in ("social", "organic_social") or any(s in source for s in _SOCIAL):
        return "social"
    if medium == "organic" or any(s in source for s in _SEARCH):
        return "search"
    if source:
        return "other"
    if host:
        if any(s in host for s in _SEARCH):
            return "search"
        if any(s in host for s in _SOCIAL):
            return "social"
        if "luminaiq" in host:
            return "direct"
        return "referral"
    return "direct"


def _host(url: Any) -> Optional[str]:
    if not url:
        return None
    try:
        h = urlparse(str(url)).hostname
        return h.lower()[:120] if h else None
    except ValueError:
        return None


async def save_attribution(user_id: str, data: Dict[str, Any], country: Optional[str] = None) -> bool:
    """First touch only: a second call for the same user changes nothing. Returns True when saved."""
    row = {
        "user_id": user_id,
        **{k: _clip(data.get(k), 120) for k in ("utm_source", "utm_medium", "utm_campaign", "utm_content",
                                                 "utm_term", "referral_code", "invite_code")},
        "referrer_host": _host(data.get("referrer")) or _clip(data.get("referrer_host"), 120),
        "landing_path": _clip(_strip_query(data.get("landing_path")), 200),
        "platform": _clip(data.get("platform"), 20),
        "country": _clip(country, 8),
        "first_seen_at": _clip(data.get("first_seen_at"), 40),
    }
    row["channel"] = channel_for(row)
    try:
        rows = await async_db(lambda: _db().pg.fetch(
            """INSERT INTO signup_attribution (user_id, channel, utm_source, utm_medium, utm_campaign, utm_content,
                   utm_term, referrer_host, landing_path, referral_code, invite_code, platform, country, first_seen_at)
               VALUES (%(user_id)s, %(channel)s, %(utm_source)s, %(utm_medium)s, %(utm_campaign)s, %(utm_content)s,
                   %(utm_term)s, %(referrer_host)s, %(landing_path)s, %(referral_code)s, %(invite_code)s,
                   %(platform)s, %(country)s, %(first_seen_at)s::timestamptz)
               ON CONFLICT (user_id) DO NOTHING RETURNING user_id""", row))
    except Exception as ex:
        logger.warning(f"[attribution] not saved: {ex}")
        return False
    if rows:
        await link_anon(user_id, data.get("anon_id"))
        await track_server("signup_completed", user_id, channel=row["channel"])
    return bool(rows)


# ---------------------------------------------------------------- consent

def required_kinds(level: Optional[str], managed: bool) -> List[str]:
    """What a user must have agreed to. School-created accounts are covered by the school's agreement."""
    if managed:
        return []
    kinds = ["terms", "privacy"]
    if level in MINOR_LEVELS:
        kinds.append("parental")
    return kinds


def current_version(kind: str) -> str:
    return {"terms": TERMS_VERSION, "privacy": PRIVACY_VERSION, "parental": PARENTAL_VERSION}.get(kind, "v1")


async def consent_state(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Latest answer per kind."""
    rows = await async_db(lambda: _db().pg.fetch(
        """SELECT DISTINCT ON (kind) kind, version, granted, granted_by, created_at
           FROM consent_records WHERE user_id = %s ORDER BY kind, created_at DESC""", (user_id,)))
    return {r["kind"]: {"version": r["version"], "granted": r["granted"], "granted_by": r["granted_by"],
                        "at": r.get("created_at")} for r in rows}


async def missing_consent(user_id: str, level: Optional[str], managed: bool) -> List[str]:
    state = await consent_state(user_id)
    out = []
    for kind in required_kinds(level, managed):
        s = state.get(kind)
        if not s or not s["granted"] or s["version"] != current_version(kind):
            out.append(kind)
    return out


async def record_consent(user_id: str, kind: str, granted: bool, method: str,
                         granted_by: str = "self", guardian_name: Optional[str] = None,
                         guardian_email: Optional[str] = None, ip: Optional[str] = None,
                         user_agent: Optional[str] = None) -> None:
    if kind not in CONSENT_KINDS:
        raise ValueError(f"unknown consent kind: {kind}")
    row = {"user_id": user_id, "kind": kind, "version": current_version(kind), "granted": bool(granted),
           "method": _clip(method, 40), "granted_by": granted_by if granted_by in ("self", "guardian", "institution") else "self",
           "guardian_name": _clip(guardian_name, 120), "guardian_email": _clip(guardian_email, 200),
           "ip_hash": hash_ip(ip), "user_agent": _clip(user_agent, 200)}
    await async_db(lambda: _db().table("consent_records").insert(row).execute())


# ---------------------------------------------------------------- feedback

async def record_feedback(user_id: str, kind: str, rating: Optional[int] = None, comment: Optional[str] = None,
                          target_type: Optional[str] = None, target_id: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None) -> None:
    if kind not in FEEDBACK_KINDS:
        raise ValueError(f"unknown feedback kind: {kind}")
    if kind == "answer_rating" and rating not in (-1, 1):
        raise ValueError("answer ratings are -1 or 1")
    if kind == "nps" and (rating is None or not 0 <= rating <= 10):
        raise ValueError("NPS is 0 to 10")
    row = {"user_id": user_id, "kind": kind, "rating": rating, "comment": _clip(comment, 2000),
           "target_type": _clip(target_type, 40), "target_id": _clip(target_id, 80),
           "context": _clean_props(context)}
    if kind == "answer_rating" and target_type and target_id:
        # Changing your mind replaces the earlier thumbs
        await async_db(lambda: _db().pg.fetch(
            """INSERT INTO feedback (user_id, kind, rating, comment, target_type, target_id, context)
               VALUES (%(user_id)s, %(kind)s, %(rating)s, %(comment)s, %(target_type)s, %(target_id)s, %(context)s)
               ON CONFLICT (user_id, target_type, target_id) WHERE kind = 'answer_rating'
               DO UPDATE SET rating = EXCLUDED.rating, comment = COALESCE(EXCLUDED.comment, feedback.comment),
                             created_at = now()
               RETURNING id""", {**row, "context": _json(row["context"])}))
    else:
        await async_db(lambda: _db().table("feedback").insert(row).execute())
    await track_server("feedback_given", user_id, kind=kind, rating=rating)


def _json(v: Any):
    from psycopg.types.json import Jsonb
    return Jsonb(v)


# ---------------------------------------------------------------- assessments

async def record_attempt(user_id: str, kind: str, *, project_id: Optional[str], source_id: Optional[str],
                         topic: Optional[str], difficulty: Optional[str],
                         responses: List[Dict[str, Any]], question_count: int,
                         started_at: Optional[str] = None, duration_seconds: Optional[int] = None) -> Optional[str]:
    """A finished test: the attempt plus one response row per question."""
    answered = sum(1 for r in responses if r.get("chosen"))
    correct = sum(1 for r in responses if r.get("is_correct"))
    now = datetime.now(timezone.utc)
    start = _parse_time(started_at)
    if duration_seconds is None and start:
        duration_seconds = int((now - start).total_seconds())
    if duration_seconds is not None and not 0 <= duration_seconds <= 6 * 3600:
        duration_seconds = None   # a tab left open overnight isn't a test duration
    attempt = {
        "user_id": user_id, "project_id": _uuid_or_none(project_id), "kind": kind,
        "source_id": _uuid_or_none(source_id), "topic": _clip(topic), "difficulty": _clip(difficulty, 20),
        "status": "completed", "question_count": question_count, "answered_count": answered,
        "correct_count": correct,
        "score_pct": round(correct / question_count * 100, 2) if question_count else None,
        "started_at": (start or now).isoformat(), "completed_at": now.isoformat(),
        "duration_seconds": duration_seconds,
    }
    try:
        res = await async_db(lambda: _db().table("assessment_attempts").insert(attempt).execute())
        attempt_id = res.data[0]["id"]
        rows = [{"attempt_id": attempt_id, "position": i, "topic": _clip(r.get("topic") or topic),
                 "chosen": _clip(r.get("chosen"), 40), "correct_answer": _clip(r.get("correct_answer"), 40),
                 "is_correct": bool(r.get("is_correct"))} for i, r in enumerate(responses)]
        if rows:
            await async_db(lambda: _db().table("attempt_responses").insert(rows).execute())
        await track_server("quiz_completed", user_id, project_id, kind=kind, score_pct=attempt["score_pct"],
                           questions=question_count, duration_seconds=duration_seconds)
        return attempt_id
    except Exception as ex:
        logger.warning(f"[attempts] not saved: {ex}")
        return None


def _parse_time(v: Any) -> Optional[datetime]:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------- data requests

async def request_data(user_id: str, kind: str, note: Optional[str] = None) -> Dict[str, Any]:
    if kind not in ("export", "delete"):
        raise ValueError("kind must be export or delete")
    existing = await async_db(lambda: _db().pg.fetch(
        "SELECT id, kind, status, requested_at FROM data_requests WHERE user_id = %s AND kind = %s AND status = 'pending'",
        (user_id, kind)))
    if existing:
        r = existing[0]
        return {"id": r["id"], "kind": r["kind"], "status": r["status"], "requested_at": r["requested_at"]}
    res = await async_db(lambda: _db().table("data_requests").insert(
        {"user_id": user_id, "kind": kind, "note": _clip(note, 1000)}).execute())
    r = res.data[0]
    return {"id": r["id"], "kind": r["kind"], "status": r["status"], "requested_at": str(r["requested_at"])}
