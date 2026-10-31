"""
Apply db/schema/NNNN_name.sql files in order, each once, each in its own transaction.

Safe with many app instances starting at once (autoscaling): a Postgres advisory
lock makes the others wait while one applies, then they find nothing to do.

    uv run python -m db.migrate          # uses DATABASE_URL
"""

import sys
from pathlib import Path
from typing import List, Optional

import psycopg

SCHEMA_DIR = Path(__file__).parent / "schema"
_LOCK_ID = 7_340_112   # any constant shared by every instance


def pending_files(applied: set) -> List[Path]:
    return [f for f in sorted(SCHEMA_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")) if f.stem not in applied]


def migrate(conninfo: Optional[str] = None) -> List[str]:
    """Apply what's missing; returns the versions applied."""
    if conninfo is None:
        from config.settings import settings
        conninfo = settings.DATABASE_URL
    if not conninfo:
        raise RuntimeError("DATABASE_URL is not set")

    done: List[str] = []
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_ID,))
        try:
            conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                                version    TEXT PRIMARY KEY,
                                applied_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
            applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
            for f in pending_files(applied):
                with conn.transaction():
                    conn.execute(f.read_text())
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (f.stem,))
                done.append(f.stem)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))
    return done


if __name__ == "__main__":
    applied = migrate()
    print("Applied: " + (", ".join(applied) if applied else "nothing (up to date)"))
    sys.exit(0)
