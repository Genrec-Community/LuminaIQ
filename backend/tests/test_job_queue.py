"""Durable job queue on Postgres: exclusive claims, retries, stale reclaim, pinning, dedupe."""

import threading
import uuid

import pytest

from utils import job_queue as q


@pytest.fixture
def pg(pg_client):
    with pg_client.pool.connection() as conn:
        conn.execute("TRUNCATE jobs")
    return pg_client


def test_enqueue_and_claim(pg):
    job = q.enqueue(pg, "demo", {"n": 1}, user_id=str(uuid.uuid4()))
    assert job["status"] == "queued" and job["payload"] == {"n": 1}
    got = q.claim(pg, "w1", "host-a", ["demo"])
    assert got["id"] == job["id"] and got["status"] == "running" and got["attempts"] == 1
    assert q.claim(pg, "w1", "host-a", ["demo"]) is None


def test_claim_ignores_other_kinds(pg):
    q.enqueue(pg, "other", {})
    assert q.claim(pg, "w1", "host-a", ["demo"]) is None


def test_claim_is_exclusive(pg):
    for i in range(20):
        q.enqueue(pg, "demo", {"i": i})
    seen, lock = [], threading.Lock()

    def worker(name):
        while True:
            job = q.claim(pg, name, "host", ["demo"])
            if not job:
                return
            with lock:
                seen.append(job["id"])

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(seen) == 20 and len(set(seen)) == 20


def test_fail_retries_then_fails(pg):
    job = q.enqueue(pg, "demo", {}, max_attempts=2)
    q.claim(pg, "w", "h", ["demo"])
    again = q.fail(pg, job["id"], "boom")
    assert again["status"] == "queued" and again["error"] == "boom"
    # backoff: not claimable until run_after passes
    assert q.claim(pg, "w", "h", ["demo"]) is None
    with pg.pool.connection() as conn:
        conn.execute("UPDATE jobs SET run_after = now() WHERE id = %s", (job["id"],))
    assert q.claim(pg, "w", "h", ["demo"])["attempts"] == 2
    final = q.fail(pg, job["id"], "boom again")
    assert final["status"] == "failed" and final["finished_at"]


def test_stale_job_is_reclaimed(pg):
    job = q.enqueue(pg, "demo", {})
    q.claim(pg, "dead-worker", "h", ["demo"])
    with pg.pool.connection() as conn:
        conn.execute("UPDATE jobs SET heartbeat_at = now() - interval '10 minutes' WHERE id = %s", (job["id"],))
    assert q.reclaim_stale(pg, stale_seconds=120) == 1
    assert q.claim(pg, "w2", "h", ["demo"])["id"] == job["id"]


def test_heartbeat_keeps_job_alive(pg):
    job = q.enqueue(pg, "demo", {})
    q.claim(pg, "w", "h", ["demo"])
    q.heartbeat(pg, job["id"], "w")
    assert q.reclaim_stale(pg, stale_seconds=120) == 0


def test_pinned_job_only_claimed_by_its_host(pg):
    job = q.enqueue(pg, "demo", {"local_path": "/tmp/x"}, pinned_host="host-a")
    assert q.claim(pg, "w", "host-b", ["demo"]) is None
    assert q.claim(pg, "w", "host-a", ["demo"])["id"] == job["id"]


def test_dedupe_key_returns_existing_job(pg):
    a = q.enqueue(pg, "demo", {"x": 1}, dedupe_key="doc-1")
    b = q.enqueue(pg, "demo", {"x": 2}, dedupe_key="doc-1")
    assert a["id"] == b["id"]
    q.claim(pg, "w", "h", ["demo"])
    q.complete(pg, a["id"], {"ok": True})
    c = q.enqueue(pg, "demo", {"x": 3}, dedupe_key="doc-1")   # finished jobs don't block new ones
    assert c["id"] != a["id"]


def test_complete_stores_result_and_lists_for_user(pg):
    user = str(uuid.uuid4())
    job = q.enqueue(pg, "demo", {}, user_id=user)
    q.claim(pg, "w", "h", ["demo"])
    q.complete(pg, job["id"], {"answer": 42})
    done = q.get(pg, job["id"])
    assert done["status"] == "done" and done["result"] == {"answer": 42} and done["finished_at"]
    assert [j["id"] for j in q.list_for_user(pg, user, 10)] == [job["id"]]
    assert q.get(pg, str(uuid.uuid4())) is None
