"""
Growth sections of the admin analytics: the investor summary, acquisition channels, the
product funnel from events, assessments, feedback and consent. Same conventions as
services/analytics_report.py (whose `q` runs SQL with the shared period parameters).

Definitions (shown on the dashboard too):
- activated:    within 7 days of signing up, had a book ready, answered a practice question
                or asked the tutor something
- Dn retention: of the users who signed up at least n days ago (last 180 days), the share
                that used the app again on or after day n
- paying user:  see analytics_report
"""

from __future__ import annotations

from typing import Any, Dict

from services.analytics_report import _f, _i, _rate

# Product funnel, in order. Each step counts distinct people (user or anonymous browser).
EVENT_FUNNEL = [
    ("signup_started", "Opened sign-up"),
    ("signup_completed", "Signed up"),
    ("upload_started", "Started an upload"),
    ("upload_succeeded", "Book ready"),
    ("quiz_started", "Started a quiz"),
    ("quiz_completed", "Finished a quiz"),
    ("paywall_shown", "Saw a paid plan"),
    ("checkout_started", "Started checkout"),
    ("payment_succeeded", "Paid"),
]

_ACTIVATED = """(
    EXISTS (SELECT 1 FROM documents x JOIN projects p ON p.id = x.project_id
            WHERE p.user_id = u.id AND x.upload_status = 'completed' AND x.created_at < u.created_at + interval '7 days')
 OR EXISTS (SELECT 1 FROM learning_events e WHERE e.user_id = u.id AND e.created_at < u.created_at + interval '7 days')
 OR EXISTS (SELECT 1 FROM chat_threads t JOIN chat_messages m ON m.thread_id = t.id
            WHERE t.user_id = u.id AND m.role = 'user' AND m.created_at < u.created_at + interval '7 days'))"""

_PAID_USER = "EXISTS (SELECT 1 FROM payments pay WHERE pay.user_id = u.id AND pay.status = 'paid')"


def _retention_n(q, n: int) -> Dict[str, Any]:
    r = q(f"""SELECT count(*) AS eligible,
                     count(*) FILTER (WHERE EXISTS (
                         SELECT 1 FROM user_active_days a WHERE a.user_id = u.id
                           AND a.day >= (u.created_at AT TIME ZONE %(tz)s)::date + {n})) AS returned
              FROM app_users u
              WHERE u.created_at < now() - interval '{n} days' AND u.created_at >= now() - interval '180 days'""")[0]
    return {"eligible": _i(r["eligible"]), "returned": _i(r["returned"]), "rate": _rate(r["returned"], r["eligible"])}


def investor(q) -> Dict[str, Any]:
    """The few numbers an investor asks for first, with how each is measured."""
    r = q("""SELECT
        (SELECT count(*) FROM app_users) AS learners,
        (SELECT count(*) FROM app_users WHERE created_at >= date_trunc('month', now() AT TIME ZONE %(tz)s) AT TIME ZONE %(tz)s) AS signups_mtd,
        (SELECT count(*) FROM app_users WHERE created_at >= (date_trunc('month', now() AT TIME ZONE %(tz)s) - interval '1 month') AT TIME ZONE %(tz)s
                                          AND created_at < date_trunc('month', now() AT TIME ZONE %(tz)s) AT TIME ZONE %(tz)s) AS signups_last_month,
        (SELECT count(*) FROM user_active_days WHERE day = %(today)s) AS dau,
        (SELECT count(DISTINCT user_id) FROM user_active_days WHERE day > %(today)s::date - 7) AS wau,
        (SELECT count(DISTINCT user_id) FROM user_active_days WHERE day > %(today)s::date - 30) AS mau,
        (SELECT count(DISTINCT user_id) FROM user_active_days WHERE day > %(today)s::date - 60 AND day <= %(today)s::date - 30) AS mau_prev,
        (SELECT COALESCE(sum(cost_usd), 0) FROM ai_calls WHERE created_at >= now() - interval '7 days') AS ai_cost_7d,
        (SELECT count(*) FROM learning_events WHERE created_at >= now() - interval '30 days') AS answers_30d,
        (SELECT count(*) FROM documents) AS books,
        (SELECT count(*) FROM learning_events) AS answers_all,
        (SELECT count(*) FROM assessment_attempts) AS quizzes_all,
        (SELECT count(DISTINCT p.user_id) FROM payments p WHERE p.status = 'paid') AS ever_paid,
        (SELECT COALESCE(sum(amount_paise), 0) FROM payments WHERE status = 'paid') AS revenue_all""")[0]
    act = q("""SELECT count(*) AS cohort, count(*) FILTER (WHERE """ + _ACTIVATED + """) AS activated,
                      count(*) FILTER (WHERE """ + _ACTIVATED + """ AND """ + _PAID_USER + """) AS activated_paid
               FROM app_users u
               WHERE u.created_at < now() - interval '7 days' AND u.created_at >= now() - interval '90 days'""")[0]
    monthly = q("""WITH m AS (SELECT generate_series(date_trunc('month', (now() AT TIME ZONE %(tz)s)::date) - interval '11 months',
                                                     date_trunc('month', (now() AT TIME ZONE %(tz)s)::date), interval '1 month')::date AS m0)
                   SELECT to_char(m0, 'YYYY-MM') AS month,
                          (SELECT count(*) FROM app_users u WHERE (u.created_at AT TIME ZONE %(tz)s)::date >= m0
                                  AND (u.created_at AT TIME ZONE %(tz)s)::date < (m0 + interval '1 month')::date) AS signups,
                          (SELECT count(DISTINCT user_id) FROM user_active_days a WHERE a.day >= m0
                                  AND a.day < (m0 + interval '1 month')::date) AS active,
                          (SELECT COALESCE(sum(amount_paise), 0) FROM payments pay WHERE pay.status = 'paid'
                                  AND (pay.created_at AT TIME ZONE %(tz)s)::date >= m0
                                  AND (pay.created_at AT TIME ZONE %(tz)s)::date < (m0 + interval '1 month')::date) AS revenue
                   FROM m ORDER BY m0""")
    wau, mau = _i(r["wau"]), _i(r["mau"])
    return {
        "learners": _i(r["learners"]),
        "signups_this_month": _i(r["signups_mtd"]),
        "signups_last_month": _i(r["signups_last_month"]),
        "dau": _i(r["dau"]), "wau": wau, "mau": mau,
        "mau_growth": round((mau - _i(r["mau_prev"])) / _i(r["mau_prev"]), 4) if _i(r["mau_prev"]) else None,
        "wau_over_mau": _rate(wau, mau),
        "retention": {"d1": _retention_n(q, 1), "d7": _retention_n(q, 7), "d30": _retention_n(q, 30)},
        "activation": {"cohort": _i(act["cohort"]), "activated": _i(act["activated"]),
                       "rate": _rate(act["activated"], act["cohort"]),
                       "paid_of_activated": _rate(act["activated_paid"], act["activated"])},
        "ai_cost_per_wau_usd": _f(float(r["ai_cost_7d"] or 0) / wau, 5) if wau else 0.0,
        "answers_per_mau_30d": _f(_i(r["answers_30d"]) / mau, 1) if mau else 0.0,
        "lifetime": {"books": _i(r["books"]), "practice_answers": _i(r["answers_all"]),
                     "quizzes_finished": _i(r["quizzes_all"]), "paying_customers": _i(r["ever_paid"]),
                     "revenue_inr": _i(r["revenue_all"]) / 100},
        "monthly": [{"month": m["month"], "signups": _i(m["signups"]), "active": _i(m["active"]),
                     "revenue_inr": _i(m["revenue"]) / 100} for m in monthly],
    }


def acquisition(q) -> Dict[str, Any]:
    """Where this period's sign-ups came from, and how well each channel activates and pays."""
    rows = q("""SELECT COALESCE(a.channel, 'unknown') AS channel, count(*) AS signups,
                       count(*) FILTER (WHERE """ + _ACTIVATED + """) AS activated,
                       count(*) FILTER (WHERE """ + _PAID_USER + """) AS paid
                FROM app_users u LEFT JOIN signup_attribution a ON a.user_id = u.id
                WHERE u.created_at >= %(t0)s GROUP BY 1 ORDER BY count(*) DESC""")
    sources = q("""SELECT COALESCE(a.utm_source, a.referrer_host, '(direct)') AS source,
                          COALESCE(a.utm_campaign, '') AS campaign, count(*) AS signups
                   FROM signup_attribution a JOIN app_users u ON u.id = a.user_id
                   WHERE u.created_at >= %(t0)s GROUP BY 1, 2 ORDER BY count(*) DESC LIMIT 15""")
    total = sum(_i(r["signups"]) for r in rows)
    known = sum(_i(r["signups"]) for r in rows if r["channel"] != "unknown")
    return {
        "tracked_share": _rate(known, total),
        "channels": [{"channel": r["channel"], "signups": _i(r["signups"]), "activated": _i(r["activated"]),
                      "activation_rate": _rate(r["activated"], r["signups"]),
                      "paid": _i(r["paid"])} for r in rows],
        "top_sources": [{"source": r["source"], "campaign": r["campaign"], "signups": _i(r["signups"])}
                        for r in sources],
    }


def product_funnel(q) -> Dict[str, Any]:
    """Distinct people reaching each tracked step in the period, plus top pages."""
    counts = {r["name"]: r for r in q(
        """SELECT name, count(*) AS events,
                  count(DISTINCT COALESCE(user_id::text, anon_id)) AS people
           FROM product_events WHERE created_at >= %(t0)s GROUP BY name""")}
    steps, prev = [], None
    for key, label in EVENT_FUNNEL:
        n = _i(counts.get(key, {}).get("people"))
        steps.append({"step": key, "label": label, "people": n,
                      "of_previous": _rate(n, prev) if prev is not None else None})
        prev = n
    pages = q("""SELECT path, count(*) AS views, count(DISTINCT COALESCE(user_id::text, anon_id)) AS people
                 FROM product_events WHERE name = 'page_view' AND created_at >= %(t0)s AND path IS NOT NULL
                 GROUP BY path ORDER BY count(*) DESC LIMIT 12""")
    platforms = q("""SELECT COALESCE(platform, 'unknown') AS platform, count(DISTINCT COALESCE(user_id::text, anon_id)) AS people
                     FROM product_events WHERE created_at >= %(t0)s AND platform <> 'server'
                     GROUP BY 1 ORDER BY 2 DESC""")
    up = _i(counts.get("upload_succeeded", {}).get("events"))
    down = _i(counts.get("upload_failed", {}).get("events"))
    return {
        "steps": steps,
        "events": sorted([{"name": k, "events": _i(v["events"]), "people": _i(v["people"])} for k, v in counts.items()],
                         key=lambda e: -e["events"]),
        "upload_failure_rate": _rate(down, up + down),
        "top_pages": [{"path": r["path"], "views": _i(r["views"]), "people": _i(r["people"])} for r in pages],
        "platforms": [{"platform": r["platform"], "people": _i(r["people"])} for r in platforms],
    }


def assessments(q) -> Dict[str, Any]:
    t = q("""SELECT count(*) AS attempts, count(DISTINCT user_id) AS learners,
                    COALESCE(avg(score_pct), 0) AS avg_score,
                    COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_seconds), 0) AS median_secs,
                    COALESCE(sum(question_count), 0) AS questions
             FROM assessment_attempts WHERE started_at >= %(t0)s""")[0]
    started = q("""SELECT count(*) AS n FROM product_events WHERE name = 'quiz_started' AND created_at >= %(t0)s""")[0]
    # Learning outcome: first vs latest score for learners who took 2+ quizzes on the same topic
    gain = q("""WITH a AS (SELECT user_id, topic, score_pct,
                                  row_number() OVER (PARTITION BY user_id, topic ORDER BY started_at) AS first_n,
                                  row_number() OVER (PARTITION BY user_id, topic ORDER BY started_at DESC) AS last_n,
                                  count(*) OVER (PARTITION BY user_id, topic) AS n
                           FROM assessment_attempts WHERE score_pct IS NOT NULL AND topic IS NOT NULL)
                SELECT count(*) AS pairs,
                       COALESCE(avg(l.score_pct - f.score_pct), 0) AS avg_gain,
                       count(*) FILTER (WHERE l.score_pct > f.score_pct) AS improved
                FROM a f JOIN a l ON l.user_id = f.user_id AND l.topic = f.topic AND l.last_n = 1
                WHERE f.first_n = 1 AND f.n >= 2""")[0]
    by_kind = q("""SELECT kind, count(*) AS n, COALESCE(avg(score_pct), 0) AS avg_score
                   FROM assessment_attempts WHERE started_at >= %(t0)s GROUP BY kind ORDER BY count(*) DESC""")
    attempts, s = _i(t["attempts"]), _i(started["n"])
    return {
        "attempts": attempts, "learners": _i(t["learners"]), "questions": _i(t["questions"]),
        "avg_score_pct": _f(t["avg_score"], 1), "median_seconds": _i(t["median_secs"]),
        "started": s, "completion_rate": _rate(attempts, s) if s else None,
        "improvement": {"learner_topics": _i(gain["pairs"]), "avg_gain_points": _f(gain["avg_gain"], 1),
                        "improved_share": _rate(gain["improved"], gain["pairs"])},
        "by_kind": [{"kind": r["kind"], "attempts": _i(r["n"]), "avg_score_pct": _f(r["avg_score"], 1)} for r in by_kind],
    }


def feedback(q) -> Dict[str, Any]:
    r = q("""SELECT
        count(*) FILTER (WHERE kind = 'answer_rating' AND rating = 1) AS up,
        count(*) FILTER (WHERE kind = 'answer_rating' AND rating = -1) AS down,
        count(*) FILTER (WHERE kind = 'nps') AS nps_n,
        count(*) FILTER (WHERE kind = 'nps' AND rating >= 9) AS promoters,
        count(*) FILTER (WHERE kind = 'nps' AND rating <= 6) AS detractors,
        count(*) FILTER (WHERE kind = 'bug') AS bugs,
        count(*) FILTER (WHERE kind = 'idea') AS ideas
        FROM feedback WHERE created_at >= %(t0)s""")[0]
    by_target = q("""SELECT COALESCE(target_type, 'other') AS target, count(*) FILTER (WHERE rating = 1) AS up,
                            count(*) FILTER (WHERE rating = -1) AS down
                     FROM feedback WHERE kind = 'answer_rating' AND created_at >= %(t0)s GROUP BY 1 ORDER BY count(*) DESC""")
    up, down, n = _i(r["up"]), _i(r["down"]), _i(r["nps_n"])
    return {
        "ratings": {"up": up, "down": down, "helpful_rate": _rate(up, up + down)},
        "nps": {"responses": n, "score": round((_i(r["promoters"]) - _i(r["detractors"])) / n * 100) if n else None},
        "bugs": _i(r["bugs"]), "ideas": _i(r["ideas"]),
        "by_target": [{"target": x["target"], "up": _i(x["up"]), "down": _i(x["down"])} for x in by_target],
    }


def consent(q) -> Dict[str, Any]:
    r = q("""WITH latest AS (SELECT DISTINCT ON (user_id, kind) user_id, kind, granted
                             FROM consent_records ORDER BY user_id, kind, created_at DESC)
             SELECT
               (SELECT count(DISTINCT user_id) FROM latest WHERE kind = 'terms' AND granted) AS terms,
               (SELECT count(DISTINCT user_id) FROM latest WHERE kind = 'parental' AND granted) AS parental,
               (SELECT count(DISTINCT user_id) FROM latest WHERE kind = 'marketing_email' AND granted) AS marketing,
               (SELECT count(*) FROM data_requests WHERE status = 'pending') AS pending_requests""")[0]
    return {"accepted_terms": _i(r["terms"]), "guardian_consents": _i(r["parental"]),
            "marketing_opt_in": _i(r["marketing"]), "pending_data_requests": _i(r["pending_requests"])}


SECTIONS = {
    "investor": investor,
    "acquisition": acquisition,
    "product_funnel": product_funnel,
    "assessments": assessments,
    "feedback": feedback,
    "consent": consent,
}


def all_sections(q) -> Dict[str, Any]:
    """Each section on its own: one failing (e.g. before its migration ran) doesn't hide the rest."""
    import logging
    out: Dict[str, Any] = {}
    for name, fn in SECTIONS.items():
        try:
            out[name] = fn(q)
        except Exception as e:
            logging.getLogger(__name__).warning(f"[analytics] {name} unavailable: {e}")
            out[name] = None
    return out
