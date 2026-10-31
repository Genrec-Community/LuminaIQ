"""
Durable background jobs in Postgres.

Any web or worker process can enqueue; workers claim with FOR UPDATE SKIP LOCKED,
so each job runs once even with many workers. A running job sends heartbeats;
if its worker dies, `reclaim_stale` puts it back in the queue. Failures retry
with backoff until max_attempts. Functions are synchronous: call them through
db.client.async_db from async code. `pg` is a db.pg.PgClient.
"""

import json
from typing import Any, Dict, List, Optional, Sequence

_COLUMNS = ("id, kind, payload, status, attempts, max_attempts, run_after, pinned_host, locked_by, "
            "heartbeat_at, result, error, user_id, dedupe_key, created_at, updated_at, finished_at")


def _one(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return rows[0] if rows else None


def enqueue(pg, kind: str, payload: Dict[str, Any], *, user_id: Optional[str] = None,
            dedupe_key: Optional[str] = None, max_attempts: int = 3,
            pinned_host: Optional[str] = None) -> Dict[str, Any]:
    """Add a job. With a dedupe_key, a job already queued or running under that key is returned instead."""
    row = _one(pg.fetch(
        f"""INSERT INTO jobs (kind, payload, user_id, dedupe_key, max_attempts, pinned_host)
            VALUES (%s, %s::jsonb, %s::uuid, %s, %s, %s)
            ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL AND status IN ('queued', 'running')
            DO NOTHING
            RETURNING {_COLUMNS}""",
        (kind, json.dumps(payload), user_id, dedupe_key, max_attempts, pinned_host)))
    if row:
        return row
    return _one(pg.fetch(
        f"SELECT {_COLUMNS} FROM jobs WHERE dedupe_key = %s AND status IN ('queued', 'running') LIMIT 1",
        (dedupe_key,)))


def claim(pg, worker_id: str, host: str, kinds: Sequence[str]) -> Optional[Dict[str, Any]]:
    """Take the oldest ready job of one of `kinds` (pinned jobs only on their own host)."""
    return _one(pg.fetch(
        f"""UPDATE jobs SET status = 'running', attempts = attempts + 1, locked_by = %s,
                   heartbeat_at = now(), updated_at = now()
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'queued' AND run_after <= now() AND kind = ANY(%s)
                  AND (pinned_host IS NULL OR pinned_host = %s)
                ORDER BY run_after, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1)
            RETURNING {_COLUMNS}""",
        (worker_id, list(kinds), host)))


def heartbeat(pg, job_id: str, worker_id: str) -> None:
    pg.fetch("UPDATE jobs SET heartbeat_at = now() WHERE id = %s AND locked_by = %s AND status = 'running'",
             (job_id, worker_id))


def complete(pg, job_id: str, result: Any = None) -> None:
    pg.fetch("""UPDATE jobs SET status = 'done', result = %s::jsonb, error = NULL, locked_by = NULL,
                       finished_at = now(), updated_at = now() WHERE id = %s""",
             (json.dumps(result), job_id))


def fail(pg, job_id: str, error: str) -> Dict[str, Any]:
    """Requeue with backoff (10 s, 20 s, 40 s ... up to 5 min) or give up after max_attempts."""
    return _one(pg.fetch(
        f"""UPDATE jobs SET
                status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
                run_after = now() + make_interval(secs => LEAST(300, 10 * power(2, attempts - 1))),
                finished_at = CASE WHEN attempts >= max_attempts THEN now() END,
                error = %s, locked_by = NULL, updated_at = now()
            WHERE id = %s RETURNING {_COLUMNS}""",
        (error[:4000], job_id)))


def reclaim_stale(pg, stale_seconds: int) -> int:
    """Put back running jobs whose worker stopped sending heartbeats."""
    rows = pg.fetch(
        """UPDATE jobs SET status = 'queued', locked_by = NULL, run_after = now(), updated_at = now(),
                  error = 'worker stopped responding; retrying'
           WHERE status = 'running' AND heartbeat_at < now() - make_interval(secs => %s)
           RETURNING id""",
        (stale_seconds,))
    return len(rows)


def get(pg, job_id: str) -> Optional[Dict[str, Any]]:
    try:
        return _one(pg.fetch(f"SELECT {_COLUMNS} FROM jobs WHERE id = %s::uuid", (job_id,)))
    except Exception:
        return None   # not a UUID


def list_for_user(pg, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    return pg.fetch(f"SELECT {_COLUMNS} FROM jobs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                    (user_id, limit))
