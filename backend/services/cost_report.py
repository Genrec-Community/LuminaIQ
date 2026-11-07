"""
The platform admin's AI cost dashboard (AGENTS.md Phase 4), from ai_calls.

Cache hit rate = cache hits / (cache hits + model calls) for the features that can be
served from a cache. A "cache hit" is a quiz/flashcard pool draw, a shared note or
mindmap, or a cached first-question answer; "saved" is what those would have cost.
"""

from __future__ import annotations

from typing import Any, Dict

from db.client import async_db, get_supabase_client


def _f(x) -> float:
    return round(float(x or 0), 6)


async def report(days: int = 30) -> Dict[str, Any]:
    days = max(1, min(int(days or 30), 365))
    pg = get_supabase_client().pg
    since = "now() - make_interval(days => %s)"

    def q(sql, *params):
        return pg.fetch(sql, (days, *params))

    def run():
        totals = q(f"""SELECT count(*) FILTER (WHERE NOT cache_hit) AS calls,
                              count(*) FILTER (WHERE cache_hit) AS cache_hits,
                              count(*) FILTER (WHERE kind = 'llm') AS llm_calls,
                              count(*) FILTER (WHERE NOT ok) AS errors,
                              COALESCE(sum(input_tokens + output_tokens), 0) AS tokens,
                              COALESCE(sum(cached_tokens), 0) AS provider_cached_tokens,
                              COALESCE(sum(cost_usd), 0) AS cost_usd,
                              COALESCE(sum(saved_usd), 0) AS saved_usd,
                              COALESCE(avg(latency_ms) FILTER (WHERE kind = 'llm'), 0) AS avg_llm_latency_ms,
                              count(DISTINCT user_id) AS users
                       FROM ai_calls WHERE created_at >= {since}""")[0]
        by_feature = q(f"""SELECT feature,
                                  count(*) FILTER (WHERE kind = 'llm') AS llm_calls,
                                  count(*) FILTER (WHERE cache_hit) AS cache_hits,
                                  COALESCE(sum(cost_usd), 0) AS cost_usd,
                                  COALESCE(sum(saved_usd), 0) AS saved_usd,
                                  COALESCE(sum(input_tokens + output_tokens), 0) AS tokens
                           FROM ai_calls WHERE created_at >= {since}
                           GROUP BY feature ORDER BY sum(cost_usd) DESC, count(*) DESC LIMIT 40""")
        by_model = q(f"""SELECT kind, role, model, count(*) AS calls,
                                COALESCE(sum(input_tokens), 0) AS input_tokens,
                                COALESCE(sum(output_tokens), 0) AS output_tokens,
                                COALESCE(sum(cached_tokens), 0) AS cached_tokens,
                                COALESCE(sum(cost_usd), 0) AS cost_usd,
                                COALESCE(avg(latency_ms), 0) AS avg_latency_ms,
                                count(*) FILTER (WHERE NOT ok) AS errors
                         FROM ai_calls WHERE created_at >= {since} AND NOT cache_hit
                         GROUP BY kind, role, model ORDER BY sum(cost_usd) DESC, count(*) DESC LIMIT 40""")
        by_user = q(f"""SELECT a.user_id::text AS user_id, u.email,
                               count(*) FILTER (WHERE NOT a.cache_hit) AS calls,
                               count(*) FILTER (WHERE a.cache_hit) AS cache_hits,
                               COALESCE(sum(a.input_tokens + a.output_tokens), 0) AS tokens,
                               COALESCE(sum(a.cost_usd), 0) AS cost_usd
                        FROM ai_calls a LEFT JOIN app_users u ON u.id = a.user_id
                        WHERE a.created_at >= {since} AND a.user_id IS NOT NULL
                        GROUP BY a.user_id, u.email ORDER BY sum(a.cost_usd) DESC, count(*) DESC LIMIT 25""")
        daily = q(f"""SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS day,
                             count(*) FILTER (WHERE kind = 'llm') AS llm_calls,
                             count(*) FILTER (WHERE cache_hit) AS cache_hits,
                             COALESCE(sum(cost_usd), 0) AS cost_usd,
                             COALESCE(sum(saved_usd), 0) AS saved_usd
                      FROM ai_calls WHERE created_at >= {since}
                      GROUP BY 1 ORDER BY 1""")
        return totals, by_feature, by_model, by_user, daily

    totals, by_feature, by_model, by_user, daily = await async_db(run)

    def rate(hits, calls):
        hits, calls = int(hits or 0), int(calls or 0)
        return round(hits / (hits + calls), 4) if hits + calls else 0.0

    return {
        "days": days,
        "totals": {
            "calls": int(totals["calls"]), "cache_hits": int(totals["cache_hits"]),
            "llm_calls": int(totals["llm_calls"]), "errors": int(totals["errors"]),
            "tokens": int(totals["tokens"]), "provider_cached_tokens": int(totals["provider_cached_tokens"]),
            "cost_usd": _f(totals["cost_usd"]), "saved_usd": _f(totals["saved_usd"]),
            "avg_llm_latency_ms": int(totals["avg_llm_latency_ms"] or 0), "users": int(totals["users"]),
            "cache_hit_rate": rate(totals["cache_hits"], totals["llm_calls"]),
        },
        "by_feature": [{**r, "cost_usd": _f(r["cost_usd"]), "saved_usd": _f(r["saved_usd"]),
                        "tokens": int(r["tokens"]), "cache_hit_rate": rate(r["cache_hits"], r["llm_calls"])}
                       for r in by_feature],
        "by_model": [{**r, "cost_usd": _f(r["cost_usd"]), "avg_latency_ms": int(r["avg_latency_ms"] or 0),
                      "input_tokens": int(r["input_tokens"]), "output_tokens": int(r["output_tokens"]),
                      "cached_tokens": int(r["cached_tokens"])} for r in by_model],
        "by_user": [{**r, "cost_usd": _f(r["cost_usd"]), "tokens": int(r["tokens"])} for r in by_user],
        "daily": [{**r, "cost_usd": _f(r["cost_usd"]), "saved_usd": _f(r["saved_usd"]),
                   "cache_hit_rate": rate(r["cache_hits"], r["llm_calls"])} for r in daily],
    }
