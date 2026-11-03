"""
The platform admin's analytics dashboard: the whole journey, from sign-up to learning to
revenue, plus system health. AI spend has its own detailed tab (services/cost_report.py);
here it appears only as totals next to revenue.

Every number covers the last `days` days (local days, PLAN_TIMEZONE) and, where useful,
the same number for the period before it so the dashboard can show the change.

Definitions:
- user:          a row in app_users (written on a user's first signed-in request)
- active user:   used the app on that day (user_active_days, written by the auth dependency)
- question:      one practice answer (learning_events: quizzes, Power Hour, flashcards, reviews)
- chat question: a student message in chat
- paying user:   an active Scholar/Topper plan or an Exam Night Pass (school seats are counted
                 separately under schools)

Privacy: counts and learning data only. Chat text and memory notes never appear here.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from config.settings import settings
from db.client import async_db, get_supabase_client
from services.plans import PAID_PLANS, PLANS, plan_price

_ACTIVE_PLAN = "status IN ('active', 'authenticated', 'trialing') AND (current_period_end IS NULL OR current_period_end > now())"
LEVELS = ("school", "higher_secondary", "ugpg", "research", "general")


def _tz_name() -> str:
    return getattr(settings, "PLAN_TIMEZONE", "") or "Asia/Kolkata"


def _params(days: int) -> Dict[str, Any]:
    from services.usage_service import _tz
    tz = _tz()
    today = datetime.now(tz).date()
    d0 = today - timedelta(days=days - 1)           # first day of this period
    pd0 = d0 - timedelta(days=days)                 # first day of the period before
    start = lambda d: datetime.combine(d, datetime.min.time(), tzinfo=tz)  # noqa: E731
    week0 = today - timedelta(days=today.weekday()) - timedelta(weeks=7)   # Monday, 8 weeks ago
    return {"tz": _tz_name(), "today": today, "d0": d0, "pd0": pd0, "t0": start(d0), "p0": start(pd0),
            "w0": week0, "tw0": start(week0)}


def _i(x) -> int:
    return int(x or 0)


def _f(x, n: int = 4) -> float:
    return round(float(x or 0), n)


def _rate(part, whole) -> float:
    return round(_i(part) / _i(whole), 4) if _i(whole) else 0.0


def _change(now, before) -> Dict[str, Any]:
    now, before = float(now or 0), float(before or 0)
    return {"value": now, "previous": before,
            "change": round((now - before) / before, 4) if before else None}


# ---------------------------------------------------------------- sections

def _overview(q) -> Dict[str, Any]:
    r = q("""SELECT
        (SELECT count(*) FROM app_users) AS total_users,
        (SELECT count(*) FROM app_users WHERE created_at >= %(t0)s) AS new_users,
        (SELECT count(*) FROM app_users WHERE created_at >= %(p0)s AND created_at < %(t0)s) AS new_users_prev,
        (SELECT count(DISTINCT user_id) FROM user_active_days WHERE day >= %(d0)s) AS active,
        (SELECT count(DISTINCT user_id) FROM user_active_days WHERE day >= %(pd0)s AND day < %(d0)s) AS active_prev,
        (SELECT count(*) FROM user_active_days WHERE day = %(today)s) AS dau,
        (SELECT count(DISTINCT user_id) FROM user_active_days WHERE day > %(today)s::date - 7) AS wau,
        (SELECT count(DISTINCT user_id) FROM user_active_days WHERE day > %(today)s::date - 30) AS mau,
        (SELECT count(*) FROM user_active_days WHERE day > %(today)s::date - 7) AS active_days_7,
        (SELECT count(*) FROM learning_events WHERE created_at >= %(t0)s) AS questions,
        (SELECT count(*) FROM learning_events WHERE created_at >= %(p0)s AND created_at < %(t0)s) AS questions_prev,
        (SELECT count(*) FILTER (WHERE correct) FROM learning_events WHERE created_at >= %(t0)s) AS correct,
        (SELECT count(*) FROM chat_messages WHERE role = 'user' AND created_at >= %(t0)s) AS chats,
        (SELECT count(*) FROM chat_messages WHERE role = 'user' AND created_at >= %(p0)s AND created_at < %(t0)s) AS chats_prev,
        (SELECT count(*) FROM documents WHERE created_at >= %(t0)s) AS documents,
        (SELECT count(*) FROM documents WHERE created_at >= %(p0)s AND created_at < %(t0)s) AS documents_prev,
        (SELECT COALESCE(sum(amount_paise), 0) FROM payments WHERE status = 'paid' AND created_at >= %(t0)s) AS revenue,
        (SELECT COALESCE(sum(amount_paise), 0) FROM payments WHERE status = 'paid'
                AND created_at >= %(p0)s AND created_at < %(t0)s) AS revenue_prev,
        (SELECT COALESCE(sum(cost_usd), 0) FROM ai_calls WHERE created_at >= %(t0)s) AS ai_cost,
        (SELECT COALESCE(sum(cost_usd), 0) FROM ai_calls WHERE created_at >= %(p0)s AND created_at < %(t0)s) AS ai_cost_prev,
        (SELECT count(*) FROM user_plans WHERE (plan = ANY(%(paid)s) AND """ + _ACTIVE_PLAN + """)
                OR pass_until > now()) AS paying""")[0]
    active = _i(r["active"])
    return {
        "total_users": _i(r["total_users"]),
        "new_users": _change(r["new_users"], r["new_users_prev"]),
        "active_users": _change(active, r["active_prev"]),
        "dau": _i(r["dau"]), "wau": _i(r["wau"]), "mau": _i(r["mau"]),
        # Average daily actives over the last week / monthly actives: how habitual the app is
        "stickiness": round(_i(r["active_days_7"]) / 7 / _i(r["mau"]), 4) if _i(r["mau"]) else 0.0,
        "questions": _change(r["questions"], r["questions_prev"]),
        "accuracy": _rate(r["correct"], r["questions"]),
        "chat_questions": _change(r["chats"], r["chats_prev"]),
        "documents": _change(r["documents"], r["documents_prev"]),
        "revenue_inr": _change(_i(r["revenue"]) / 100, _i(r["revenue_prev"]) / 100),
        "ai_cost_usd": _change(_f(r["ai_cost"]), _f(r["ai_cost_prev"])),
        "ai_cost_per_active_usd": _f(float(r["ai_cost"] or 0) / active, 5) if active else 0.0,
        "paying_users": _i(r["paying"]),
        "paying_share": _rate(r["paying"], r["total_users"]),
    }


def _daily(q) -> List[Dict[str, Any]]:
    rows = q("""WITH days AS (
            SELECT d::date AS day, (d::timestamp AT TIME ZONE %(tz)s) AS b0,
                   ((d + interval '1 day')::timestamp AT TIME ZONE %(tz)s) AS b1
            FROM generate_series(%(d0)s::date, %(today)s::date, interval '1 day') AS d)
        SELECT to_char(day, 'YYYY-MM-DD') AS day,
            (SELECT count(*) FROM app_users WHERE created_at >= b0 AND created_at < b1) AS signups,
            (SELECT count(*) FROM user_active_days a WHERE a.day = days.day) AS active,
            (SELECT count(*) FROM learning_events WHERE created_at >= b0 AND created_at < b1) AS questions,
            (SELECT count(*) FROM chat_messages WHERE role = 'user' AND created_at >= b0 AND created_at < b1) AS chats,
            (SELECT COALESCE(sum(amount_paise), 0) FROM payments
                    WHERE status = 'paid' AND created_at >= b0 AND created_at < b1) AS revenue,
            (SELECT COALESCE(sum(cost_usd), 0) FROM ai_calls WHERE created_at >= b0 AND created_at < b1) AS ai_cost
        FROM days ORDER BY day""")
    return [{"day": r["day"], "signups": _i(r["signups"]), "active": _i(r["active"]),
             "questions": _i(r["questions"]), "chat_questions": _i(r["chats"]),
             "revenue_inr": _i(r["revenue"]) / 100, "ai_cost_usd": _f(r["ai_cost"], 5)} for r in rows]


FUNNEL = [
    ("signed_up", "Signed up"),
    ("chose_level", "Chose their level"),
    ("added_book", "Added a book"),
    ("book_ready", "Book ready to study"),
    ("asked", "Asked a question in chat"),
    ("practised", "Practised (quiz, flashcards…)"),
    ("came_back", "Came back another day"),
    ("paid", "Paid"),
]


def _funnel(q) -> List[Dict[str, Any]]:
    """What share of the people who signed up in this period reached each step (so far)."""
    r = q("""WITH c AS (SELECT id, (created_at AT TIME ZONE %(tz)s)::date AS d FROM app_users WHERE created_at >= %(t0)s)
        SELECT count(*) AS signed_up,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM user_settings s WHERE s.user_id = c.id
                                           AND s.settings->>'studyLevel' IS NOT NULL)
                              OR EXISTS (SELECT 1 FROM class_members m WHERE m.user_id = c.id)) AS chose_level,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM documents x JOIN projects p ON p.id = x.project_id
                                         WHERE p.user_id = c.id)) AS added_book,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM documents x JOIN projects p ON p.id = x.project_id
                                         WHERE p.user_id = c.id AND x.upload_status = 'completed')) AS book_ready,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM chat_threads t JOIN chat_messages m ON m.thread_id = t.id
                                         WHERE t.user_id = c.id AND m.role = 'user')) AS asked,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM learning_events e WHERE e.user_id = c.id)) AS practised,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM user_active_days a WHERE a.user_id = c.id AND a.day > c.d)) AS came_back,
          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = c.id AND pay.status = 'paid')) AS paid
        FROM c""")[0]
    top = _i(r["signed_up"])
    out, prev = [], top
    for key, label in FUNNEL:
        n = _i(r[key])
        out.append({"step": key, "label": label, "users": n, "of_signups": _rate(n, top),
                    "of_previous": _rate(n, prev)})
        prev = n
    return out


def _retention(q, p) -> List[Dict[str, Any]]:
    """Weekly sign-up cohorts (last 8 weeks): share of each cohort active N weeks later."""
    sizes = q("""SELECT date_trunc('week', created_at AT TIME ZONE %(tz)s)::date AS wk, count(*) AS n
                 FROM app_users WHERE created_at >= %(tw0)s GROUP BY 1""")
    active = q("""WITH c AS (SELECT id, date_trunc('week', created_at AT TIME ZONE %(tz)s)::date AS wk
                             FROM app_users WHERE created_at >= %(tw0)s)
                  SELECT c.wk, (date_trunc('week', a.day)::date - c.wk) / 7 AS w, count(DISTINCT a.user_id) AS n
                  FROM c JOIN user_active_days a ON a.user_id = c.id AND a.day >= c.wk
                  GROUP BY 1, 2""")
    size = {str(r["wk"])[:10]: _i(r["n"]) for r in sizes}
    hits: Dict[str, Dict[int, int]] = {}
    for r in active:
        hits.setdefault(str(r["wk"])[:10], {})[_i(r["w"])] = _i(r["n"])
    this_week = p["today"] - timedelta(days=p["today"].weekday())
    out = []
    for k in range(8):
        wk = p["w0"] + timedelta(weeks=k)
        key = wk.isoformat()
        n = size.get(key, 0)
        weeks_since = (this_week - wk).days // 7
        out.append({"week": key, "users": n,
                    # week 0 is the sign-up week; None = that week hasn't happened yet
                    "weeks": [None if w > weeks_since else _rate(hits.get(key, {}).get(w, 0), n)
                              for w in range(8)]})
    return out


def _engagement(q) -> Dict[str, Any]:
    features = q("""SELECT feature, count(DISTINCT user_id) AS users,
                           count(*) FILTER (WHERE kind = 'llm') AS model_calls,
                           count(*) FILTER (WHERE cache_hit) AS cache_hits
                    FROM ai_calls WHERE created_at >= %(t0)s AND kind IN ('llm', 'cache')
                    GROUP BY feature ORDER BY count(DISTINCT user_id) DESC, count(*) DESC LIMIT 30""")
    practice = q("""SELECT COALESCE(source, kind, 'other') AS source, count(*) AS answers,
                           count(DISTINCT user_id) AS users, count(*) FILTER (WHERE correct) AS correct
                    FROM learning_events WHERE created_at >= %(t0)s
                    GROUP BY 1 ORDER BY count(*) DESC LIMIT 20""")
    depth = q("""SELECT count(*) AS days, count(DISTINCT user_id) AS users FROM user_active_days WHERE day >= %(d0)s""")[0]
    habit = q("""WITH per AS (SELECT user_id, count(*) AS n FROM user_active_days WHERE day >= %(d0)s GROUP BY user_id)
                 SELECT count(*) FILTER (WHERE n = 1) AS one, count(*) FILTER (WHERE n BETWEEN 2 AND 3) AS few,
                        count(*) FILTER (WHERE n BETWEEN 4 AND 9) AS regular, count(*) FILTER (WHERE n >= 10) AS daily
                 FROM per""")[0]
    top = q("""WITH le AS (SELECT user_id, count(*) AS answers, count(*) FILTER (WHERE correct) AS correct,
                                  COALESCE(sum(GREATEST(p_known_after - p_known_before, 0)), 0) * 100 AS mastery
                           FROM learning_events WHERE created_at >= %(t0)s GROUP BY user_id),
                    ch AS (SELECT t.user_id, count(*) AS chats FROM chat_messages m JOIN chat_threads t ON t.id = m.thread_id
                           WHERE m.role = 'user' AND m.created_at >= %(t0)s GROUP BY t.user_id),
                    ad AS (SELECT user_id, count(*) AS days FROM user_active_days WHERE day >= %(d0)s GROUP BY user_id),
                    xp AS (SELECT user_id, sum(xp) AS xp FROM xp_events WHERE day >= %(d0)s GROUP BY user_id)
               SELECT ad.user_id::text AS user_id, u.email, ad.days, COALESCE(le.answers, 0) AS answers,
                      COALESCE(le.correct, 0) AS correct, COALESCE(le.mastery, 0) AS mastery,
                      COALESCE(ch.chats, 0) AS chats, COALESCE(xp.xp, 0) AS xp
               FROM ad LEFT JOIN app_users u ON u.id = ad.user_id LEFT JOIN le ON le.user_id = ad.user_id
                    LEFT JOIN ch ON ch.user_id = ad.user_id LEFT JOIN xp ON xp.user_id = ad.user_id
               ORDER BY COALESCE(le.answers, 0) + COALESCE(ch.chats, 0) DESC, ad.days DESC LIMIT 15""")
    return {
        "avg_active_days": _f(_i(depth["days"]) / _i(depth["users"]), 2) if _i(depth["users"]) else 0.0,
        "habit": {"one_day": _i(habit["one"]), "two_three": _i(habit["few"]),
                  "four_nine": _i(habit["regular"]), "ten_plus": _i(habit["daily"])},
        "features": [{"feature": r["feature"], "users": _i(r["users"]), "model_calls": _i(r["model_calls"]),
                      "cache_hits": _i(r["cache_hits"])} for r in features],
        "practice": [{"source": r["source"], "answers": _i(r["answers"]), "users": _i(r["users"]),
                      "accuracy": _rate(r["correct"], r["answers"])} for r in practice],
        "top_learners": [{"user_id": r["user_id"], "email": r["email"], "active_days": _i(r["days"]),
                          "answers": _i(r["answers"]), "accuracy": _rate(r["correct"], r["answers"]),
                          "mastery_points": _f(r["mastery"], 1), "chat_questions": _i(r["chats"]),
                          "xp": _i(r["xp"])} for r in top],
    }


_LEVEL_SQL = """COALESCE(
    (SELECT ic.level FROM class_members m JOIN institution_classes ic ON ic.id = m.class_id
     WHERE m.user_id = u.id AND ic.level IS NOT NULL LIMIT 1),
    (SELECT s.settings->>'studyLevel' FROM user_settings s WHERE s.user_id = u.id LIMIT 1),
    'not_set')"""


def _learning(q) -> Dict[str, Any]:
    t = q("""SELECT count(*) AS answers, count(*) FILTER (WHERE correct) AS correct,
                    count(*) FILTER (WHERE hinted) AS hinted, count(DISTINCT user_id) AS learners,
                    COALESCE(sum(GREATEST(p_known_after - p_known_before, 0)), 0) * 100 AS mastery
             FROM learning_events WHERE created_at >= %(t0)s""")[0]
    m = q("""SELECT
        (SELECT count(*) FROM learner_mistakes WHERE created_at >= %(t0)s) AS opened,
        (SELECT count(*) FROM learner_mistakes WHERE fixed_at >= %(t0)s) AS fixed,
        (SELECT count(*) FROM learner_mistakes WHERE created_at >= %(t0)s AND misconception IS NOT NULL) AS tagged,
        (SELECT count(*) FROM topic_mastery WHERE p_known >= 0.95 AND updated_at >= %(t0)s) AS mastered,
        (SELECT count(*) FROM daily_goals WHERE day >= %(d0)s) AS goals,
        (SELECT count(*) FROM daily_goals WHERE day >= %(d0)s AND completed_at IS NOT NULL) AS goals_done,
        (SELECT count(*) FROM review_cards WHERE next_review <= now()) AS reviews_due""")[0]
    xp = q("""SELECT kind, count(*) AS n, COALESCE(sum(xp), 0) AS xp, count(DISTINCT user_id) AS users
              FROM xp_events WHERE day >= %(d0)s GROUP BY kind ORDER BY sum(xp) DESC""")
    by_level = q("""WITH lv AS (SELECT u.id, """ + _LEVEL_SQL + """ AS level FROM app_users u),
                         act AS (SELECT DISTINCT user_id FROM user_active_days WHERE day >= %(d0)s),
                         le AS (SELECT user_id, count(*) AS n, count(*) FILTER (WHERE correct) AS c,
                                       COALESCE(sum(GREATEST(p_known_after - p_known_before, 0)), 0) * 100 AS g
                                FROM learning_events WHERE created_at >= %(t0)s GROUP BY user_id)
                    SELECT lv.level, count(*) AS users, count(act.user_id) AS active,
                           COALESCE(sum(le.n), 0) AS answers, COALESCE(sum(le.c), 0) AS correct,
                           COALESCE(sum(le.g), 0) AS mastery
                    FROM lv LEFT JOIN act ON act.user_id = lv.id LEFT JOIN le ON le.user_id = lv.id
                    GROUP BY lv.level""")
    hardest = q("""SELECT topic, count(*) AS answers, count(*) FILTER (WHERE correct) AS correct,
                          count(DISTINCT user_id) AS learners
                   FROM learning_events WHERE created_at >= %(t0)s AND topic IS NOT NULL AND topic <> ''
                   GROUP BY topic HAVING count(*) >= 5
                   ORDER BY count(*) FILTER (WHERE correct)::float / count(*), count(*) DESC LIMIT 10""")
    order = {lv: i for i, lv in enumerate(LEVELS + ("not_set",))}
    return {
        "answers": _i(t["answers"]), "learners": _i(t["learners"]),
        "accuracy": _rate(t["correct"], t["answers"]), "hinted_share": _rate(t["hinted"], t["answers"]),
        "mastery_points": _f(t["mastery"], 1),
        "mastery_per_learner": _f(float(t["mastery"] or 0) / _i(t["learners"]), 1) if _i(t["learners"]) else 0.0,
        "topics_mastered": _i(m["mastered"]),
        "mistakes": {"opened": _i(m["opened"]), "fixed": _i(m["fixed"]), "tagged": _i(m["tagged"])},
        "goals": {"set": _i(m["goals"]), "completed": _i(m["goals_done"]), "rate": _rate(m["goals_done"], m["goals"])},
        "reviews_due_now": _i(m["reviews_due"]),
        "xp_by_kind": [{"kind": r["kind"], "events": _i(r["n"]), "xp": _i(r["xp"]), "users": _i(r["users"])} for r in xp],
        "by_level": sorted([{"level": r["level"], "users": _i(r["users"]), "active": _i(r["active"]),
                             "answers": _i(r["answers"]), "accuracy": _rate(r["correct"], r["answers"]),
                             "mastery_per_active": _f(float(r["mastery"] or 0) / _i(r["active"]), 1) if _i(r["active"]) else 0.0}
                            for r in by_level], key=lambda r: order.get(r["level"], 99)),
        "hardest_topics": [{"topic": r["topic"], "answers": _i(r["answers"]), "learners": _i(r["learners"]),
                            "accuracy": _rate(r["correct"], r["answers"])} for r in hardest],
    }


def _revenue(q) -> Dict[str, Any]:
    from services.institution_service import state as school_state
    payments = q("""SELECT kind, plan, count(*) AS n, COALESCE(sum(amount_paise), 0) AS paise
                    FROM payments WHERE status = 'paid' AND created_at >= %(t0)s
                    GROUP BY kind, plan ORDER BY sum(amount_paise) DESC""")
    subs = q("""SELECT plan, COALESCE(billing_cycle, 'monthly') AS cycle, count(*) AS n,
                       count(*) FILTER (WHERE cancel_at_period_end) AS cancelling
                FROM user_plans WHERE plan = ANY(%(paid)s) AND """ + _ACTIVE_PLAN + """
                GROUP BY 1, 2""")
    misc = q("""SELECT
        (SELECT count(*) FROM user_plans WHERE pass_until > now()) AS passes,
        (SELECT count(*) FROM (SELECT user_id FROM payments WHERE status = 'paid' GROUP BY user_id
                               HAVING min(created_at) >= %(t0)s) f) AS new_payers,
        (SELECT count(*) FROM payments WHERE status IN ('failed') AND created_at >= %(t0)s) AS failed""")[0]
    schools = q("""SELECT i.approval_status, i.status, i.paid_until, i.seats,
                          (SELECT count(*) FROM institution_members m WHERE m.institution_id = i.id
                                  AND m.role = 'student' AND NOT m.disabled) AS students
                   FROM institutions i""")
    mrr = 0.0
    plans = []
    for r in subs:
        n = _i(r["n"])
        price = plan_price(r["plan"], r["cycle"]) if r["plan"] in PLANS else 0
        monthly = price if r["cycle"] == "monthly" else price / 12
        mrr += monthly * n
        plans.append({"plan": r["plan"], "cycle": r["cycle"], "subscribers": n,
                      "cancelling": _i(r["cancelling"]), "mrr_inr": round(monthly * n)})
    by_state: Dict[str, Dict[str, int]] = {}
    seat_price = PLANS.get("institution", {}).get("price_inr", 0)
    school_mrr = 0
    for s in schools:
        st = school_state(s)
        b = by_state.setdefault(st, {"schools": 0, "seats": 0, "students": 0})
        b["schools"] += 1
        b["seats"] += _i(s["seats"])
        b["students"] += _i(s["students"])
        if st == "active":
            school_mrr += _i(s["seats"]) * seat_price
    return {
        "payments": [{"kind": r["kind"], "plan": r["plan"], "count": _i(r["n"]), "amount_inr": _i(r["paise"]) / 100}
                     for r in payments],
        "subscriptions": sorted(plans, key=lambda p: -p["mrr_inr"]),
        "mrr_inr": round(mrr), "school_mrr_inr": school_mrr,
        "pass_holders": _i(misc["passes"]), "new_payers": _i(misc["new_payers"]),
        "failed_payments": _i(misc["failed"]),
        "schools": [{"state": k, **v} for k, v in sorted(by_state.items())],
    }


def _health(q) -> Dict[str, Any]:
    jobs = q("""SELECT kind, count(*) AS n, count(*) FILTER (WHERE status = 'failed') AS failed,
                       count(*) FILTER (WHERE status = 'done') AS done,
                       COALESCE(avg(EXTRACT(EPOCH FROM finished_at - created_at)) FILTER (WHERE status = 'done'), 0) AS secs,
                       COALESCE(max(attempts), 0) AS max_attempts
                FROM jobs WHERE created_at >= %(t0)s GROUP BY kind ORDER BY count(*) DESC LIMIT 25""")
    queue = q("""SELECT count(*) FILTER (WHERE status = 'queued') AS queued,
                        count(*) FILTER (WHERE status = 'running') AS running,
                        COALESCE(EXTRACT(EPOCH FROM now() - min(created_at) FILTER (WHERE status = 'queued' AND run_after <= now())), 0) AS oldest
                 FROM jobs WHERE status IN ('queued', 'running')""")[0]
    docs = q("""SELECT upload_status AS status, count(*) AS n FROM documents WHERE created_at >= %(t0)s
                GROUP BY 1 ORDER BY count(*) DESC""")
    ai = q("""SELECT count(*) AS calls, count(*) FILTER (WHERE NOT ok) AS errors,
                     COALESCE(avg(latency_ms), 0) AS avg_ms,
                     COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0) AS p95_ms
              FROM ai_calls WHERE created_at >= %(t0)s AND kind = 'llm'""")[0]
    safety = q("""SELECT level, category, count(*) AS n FROM safety_events WHERE created_at >= %(t0)s
                  GROUP BY 1, 2 ORDER BY count(*) DESC""")
    total_docs = sum(_i(r["n"]) for r in docs)
    failed_docs = sum(_i(r["n"]) for r in docs if r["status"] == "failed")
    return {
        "jobs": [{"kind": r["kind"], "total": _i(r["n"]), "failed": _i(r["failed"]), "done": _i(r["done"]),
                  "failure_rate": _rate(r["failed"], r["n"]), "avg_seconds": _f(r["secs"], 1),
                  "max_attempts": _i(r["max_attempts"])} for r in jobs],
        "queue": {"queued": _i(queue["queued"]), "running": _i(queue["running"]),
                  "oldest_waiting_seconds": _i(queue["oldest"])},
        "documents": {"total": total_docs, "failed": failed_docs, "failure_rate": _rate(failed_docs, total_docs),
                      "by_status": [{"status": r["status"] or "unknown", "count": _i(r["n"])} for r in docs]},
        "ai": {"calls": _i(ai["calls"]), "errors": _i(ai["errors"]), "error_rate": _rate(ai["errors"], ai["calls"]),
               "avg_latency_ms": _i(ai["avg_ms"]), "p95_latency_ms": _i(ai["p95_ms"])},
        "safety": [{"level": r["level"], "category": r["category"], "count": _i(r["n"])} for r in safety],
    }


async def report(days: int = 30) -> Dict[str, Any]:
    days = max(1, min(int(days or 30), 365))
    p = _params(days)
    p["paid"] = list(PAID_PLANS)
    pg = get_supabase_client().pg

    def q(sql: str):
        return pg.fetch(sql, p)

    def run():
        return {
            "overview": _overview(q),
            "daily": _daily(q),
            "funnel": _funnel(q),
            "retention": _retention(q, p),
            "engagement": _engagement(q),
            "learning": _learning(q),
            "revenue": _revenue(q),
            "health": _health(q),
        }

    out = await async_db(run)
    return {"days": days, "from": p["d0"].isoformat(), "to": p["today"].isoformat(),
            "timezone": p["tz"], "generated_at": datetime.now(p["t0"].tzinfo).isoformat(timespec="seconds"), **out}

