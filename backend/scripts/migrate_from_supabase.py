"""
Copy LuminaIQ's app data from the Supabase database into our own Postgres (AWS RDS).

Sign-in and file storage stay on Supabase, so user ids, file paths and stored book text
are unchanged. Only table rows move. Book vectors aren't copied (Qdrant → pgvector):
every completed document gets a re-index job, and the worker rebuilds its passages from
the stored text. Until then, search falls back to that text, so books keep working.

    # see what would happen (creates the empty schema, copies no rows)
    uv run python -m scripts.migrate_from_supabase --dry-run
    # copy, verify counts and queue re-indexing
    uv run python -m scripts.migrate_from_supabase

Connections come from SOURCE_DATABASE_URL (Supabase: Settings → Database → connection
string, session mode, with ?sslmode=require) and DATABASE_URL (the target), or --source /
--target. Safe to run again: rows that already exist are skipped (ON CONFLICT DO NOTHING).

Live Supabase and the new schema differ in a few places, handled here:
- jsonb → text (mcq_tests.questions, subjective_tests.questions/results,
  answer_evaluations.ai_feedback): the app stored json.dumps() output inside jsonb, i.e. a
  JSON *string*. That string is unwrapped; any other JSON value becomes its text.
- text[] → jsonb (completed_topics, topics_visited, exam topics): becomes a JSON array.
- timestamptz → date (exam_schedules.exam_date): the date in India.
- Columns only Supabase has are left behind (the report lists them); nothing reads them.
- Rows whose parent row is gone (e.g. a document of a deleted project) can't satisfy the
  new foreign keys; they're skipped and counted in the report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import psycopg
from psycopg import errors, sql

# Tables that start empty on the new database: rebuilt (chunks), operational state, or
# Supabase-only leftovers.
SKIP_TABLES = {
    "schema_migrations", "jobs", "cache_entries", "rate_limit_counters", "chunks",
    "document_chunks", "ai_calls", "answer_cache",
}
BATCH = 500
INDIA = "Asia/Kolkata"


@dataclass
class TablePlan:
    name: str
    columns: List[str]                                  # target column names copied
    select_exprs: List[sql.Composable]                  # source expressions, same order
    conversions: List[str] = field(default_factory=list)
    dropped: List[str] = field(default_factory=list)    # source-only columns
    defaults: Dict[str, str] = field(default_factory=dict)  # required target column → its default


@dataclass
class TableResult:
    name: str
    source: int = 0
    inserted: int = 0
    existing: int = 0     # already in the target (re-run)
    skipped: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


# ----------------------------------------------------------------------------- planning

def _columns(conn: psycopg.Connection, schema: str) -> Dict[str, Dict[str, Tuple[str, str]]]:
    """{table: {column: (data_type, udt_name)}} for ordinary tables in `schema`."""
    rows = conn.execute(
        """SELECT c.table_name, c.column_name, c.data_type, c.udt_name
           FROM information_schema.columns c
           JOIN information_schema.tables t
             ON t.table_schema = c.table_schema AND t.table_name = c.table_name
           WHERE c.table_schema = %s AND t.table_type = 'BASE TABLE'
           ORDER BY c.table_name, c.ordinal_position""", (schema,)).fetchall()
    out: Dict[str, Dict[str, Tuple[str, str]]] = defaultdict(dict)
    for table, col, dtype, udt in rows:
        out[table][col] = (dtype, udt)
    return out


def _required_defaults(conn: psycopg.Connection) -> Dict[str, Dict[str, str]]:
    """{table: {column: default}} for NOT NULL target columns that have a default."""
    rows = conn.execute(
        """SELECT table_name, column_name, column_default FROM information_schema.columns
           WHERE table_schema = 'public' AND is_nullable = 'NO' AND column_default IS NOT NULL""").fetchall()
    out: Dict[str, Dict[str, str]] = defaultdict(dict)
    for t, c, d in rows:
        out[t][c] = d
    return out


def _fk_parents(conn: psycopg.Connection) -> Dict[str, set]:
    rows = conn.execute(
        """SELECT conrelid::regclass::text, confrelid::regclass::text
           FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace""").fetchall()
    parents: Dict[str, set] = defaultdict(set)
    for child, parent in rows:
        if child != parent:
            parents[child].add(parent)
    return parents


def _order(tables: List[str], parents: Dict[str, set]) -> List[str]:
    """Parents before children (tables outside the copy set don't constrain the order)."""
    todo, done, ordered = set(tables), set(), []
    while todo:
        ready = sorted(t for t in todo if not (parents.get(t, set()) & todo) - done)
        if not ready:                      # a cycle: copy the rest in name order
            ready = sorted(todo)
        for t in ready:
            ordered.append(t)
            done.add(t)
            todo.discard(t)
    return ordered


def _expr(col: str, src: Tuple[str, str], dst: Tuple[str, str]) -> Tuple[sql.Composable, Optional[str]]:
    ident = sql.Identifier(col)
    (sdt, sudt), (ddt, dudt) = src, dst
    if sdt == "jsonb" and ddt in ("text", "character varying"):
        return (sql.SQL("CASE WHEN jsonb_typeof({c}) = 'string' THEN {c} #>> '{{}}' ELSE {c}::text END")
                .format(c=ident), f"{col}: jsonb → text (JSON strings unwrapped)")
    if sdt == "ARRAY" and ddt in ("jsonb", "json"):
        return sql.SQL("to_jsonb({})").format(ident), f"{col}: {sudt.lstrip('_')}[] → jsonb array"
    if sdt.startswith("timestamp") and ddt == "date":
        return (sql.SQL("({} AT TIME ZONE {})::date").format(ident, sql.Literal(INDIA)),
                f"{col}: timestamp → date ({INDIA})")
    if (sdt, sudt) != (ddt, dudt) and not ({sdt, ddt} <= {"text", "character varying"}):
        return ident, f"{col}: {sudt} → {dudt}"
    return ident, None


def plan(src: psycopg.Connection, dst: psycopg.Connection, source_schema: str) -> Tuple[List[TablePlan], List[str]]:
    scols, dcols = _columns(src, source_schema), _columns(dst, "public")
    common = [t for t in scols if t in dcols and t not in SKIP_TABLES]
    required = _required_defaults(dst)
    plans = {}
    for t in common:
        cols, exprs, conv = [], [], []
        for col, dst_type in dcols[t].items():
            if col not in scols[t]:
                continue
            e, note = _expr(col, scols[t][col], dst_type)
            cols.append(col)
            exprs.append(e)
            if note:
                conv.append(note)
        dropped = [c for c in scols[t] if c not in dcols[t]]
        defaults = {c: d for c, d in required.get(t, {}).items() if c in cols}
        plans[t] = TablePlan(t, cols, exprs, conv, dropped, defaults)
    ordered = _order(list(plans), _fk_parents(dst))
    source_only = sorted(t for t in scols if t not in dcols)
    return [plans[t] for t in ordered], source_only


# ----------------------------------------------------------------------------- copying

def _insert_sql(p: TablePlan) -> sql.Composed:
    """A null in a column the new schema requires takes that column's default instead of
    rejecting the row (e.g. an old plan row without updated_at)."""
    cols = sql.SQL(", ").join(map(sql.Identifier, p.columns))
    values = sql.SQL(", ").join(
        sql.SQL("COALESCE({c}, {d})").format(c=sql.Identifier(c), d=sql.SQL(p.defaults[c]))
        if c in p.defaults else sql.Identifier(c) for c in p.columns)
    return sql.SQL(
        "INSERT INTO {t} ({cols}) SELECT {vals} FROM json_populate_recordset(NULL::{t}, %s::json) "
        "ON CONFLICT DO NOTHING").format(t=sql.Identifier(p.name), cols=cols, vals=values)


def _reason(e: Exception) -> str:
    if isinstance(e, errors.ForeignKeyViolation):
        return "parent row missing"
    if isinstance(e, errors.NotNullViolation):
        return "required value missing"
    return type(e).__name__


def copy_table(src: psycopg.Connection, dst: psycopg.Connection, p: TablePlan,
               source_schema: str) -> TableResult:
    res = TableResult(p.name)
    if not p.columns:
        return res
    select = sql.SQL("SELECT row_to_json(x)::text FROM (SELECT {exprs} FROM {s}.{t}) x").format(
        exprs=sql.SQL(", ").join(sql.SQL("{} AS {}").format(e, sql.Identifier(c))
                                 for e, c in zip(p.select_exprs, p.columns)),
        s=sql.Identifier(source_schema), t=sql.Identifier(p.name))
    insert = _insert_sql(p)
    with src.cursor(name=f"copy_{p.name}") as cur:
        cur.itersize = BATCH
        cur.execute(select)
        batch: List[str] = []

        def flush():
            if not batch:
                return
            payload = "[" + ",".join(batch) + "]"
            try:
                with dst.transaction():
                    n = dst.execute(insert, (payload,)).rowcount
                res.inserted += n
                res.existing += len(batch) - n
            except psycopg.Error:
                # Find the bad rows one by one; the rest still go in.
                for row in batch:
                    try:
                        with dst.transaction():
                            n = dst.execute(insert, ("[" + row + "]",)).rowcount
                        res.inserted += n
                        res.existing += 1 - n
                    except psycopg.Error as e:
                        res.skipped[_reason(e)] += 1
            batch.clear()

        for (row,) in cur:
            res.source += 1
            batch.append(row)
            if len(batch) >= BATCH:
                flush()
        flush()
    return res


def copy_app_users(src: psycopg.Connection, dst: psycopg.Connection, auth_schema: str) -> TableResult:
    """Signed-in users live in Supabase auth; the app keeps (id, email) for its own joins."""
    res = TableResult("app_users (from auth.users)")
    rows = src.execute(sql.SQL(
        "SELECT json_build_object('id', id, 'email', email, 'created_at', created_at, "
        "'last_seen_at', last_sign_in_at)::text FROM {}.users").format(sql.Identifier(auth_schema))).fetchall()
    res.source = len(rows)
    if rows:
        payload = "[" + ",".join(r[0] for r in rows) + "]"
        with dst.transaction():
            n = dst.execute(
                "INSERT INTO app_users (id, email, created_at, last_seen_at) "
                "SELECT id, email, coalesce(created_at, now()), coalesce(last_seen_at, created_at, now()) "
                "FROM json_populate_recordset(NULL::app_users, %s::json) ON CONFLICT (id) DO NOTHING",
                (payload,)).rowcount
        res.inserted, res.existing = n, len(rows) - n
    return res


# ----------------------------------------------------------------------------- after the copy

FOLLOW_UPS = [
    ("chat threads for old messages", """
        INSERT INTO chat_threads (project_id, user_id, title, created_at, updated_at)
        SELECT p.id, p.user_id, 'Earlier chat', min(m.created_at), max(m.created_at)
        FROM chat_messages m JOIN projects p ON p.id = m.project_id
        WHERE m.thread_id IS NULL
          AND NOT EXISTS (SELECT 1 FROM chat_threads t WHERE t.project_id = p.id AND t.title = 'Earlier chat')
        GROUP BY p.id, p.user_id"""),
    ("messages linked to their chat", """
        UPDATE chat_messages m SET thread_id = t.id FROM chat_threads t
        WHERE m.thread_id IS NULL AND t.project_id = m.project_id AND t.title = 'Earlier chat'"""),
    ("active days from earlier activity", f"""
        INSERT INTO user_active_days (user_id, day)
        SELECT user_id, day FROM (
            SELECT id AS user_id, (last_seen_at AT TIME ZONE '{INDIA}')::date AS day FROM app_users WHERE last_seen_at IS NOT NULL
            UNION SELECT user_id, (created_at AT TIME ZONE '{INDIA}')::date FROM learning_events WHERE user_id IS NOT NULL
            UNION SELECT user_id, activity_date FROM study_activity WHERE user_id IS NOT NULL
        ) seen
        ON CONFLICT DO NOTHING"""),
]


def queue_reindex(dst: psycopg.Connection) -> int:
    """One re-index job per completed document (same payload and dedupe key as the app uses)."""
    docs = dst.execute(
        """SELECT d.id, d.project_id, d.filename, d.text_storage_path, p.user_id
           FROM documents d JOIN projects p ON p.id = d.project_id
           WHERE d.upload_status = 'completed'
             AND NOT EXISTS (SELECT 1 FROM chunks c WHERE c.document_id = d.id)""").fetchall()
    queued = 0
    for doc_id, project_id, filename, path, user_id in docs:
        payload = {"document": {"id": str(doc_id), "project_id": str(project_id),
                                "filename": filename, "text_storage_path": path}}
        with dst.transaction():
            n = dst.execute(
                """INSERT INTO jobs (kind, payload, user_id, dedupe_key, max_attempts)
                   VALUES ('reindex_document', %s::jsonb, %s, %s, 5)
                   ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL AND status IN ('queued', 'running')
                   DO NOTHING""",
                (json.dumps(payload), user_id, f"reindex_document:{doc_id}")).rowcount
        queued += n
    return queued


# ----------------------------------------------------------------------------- report

def _print_plan(plans: List[TablePlan], source_only: List[str], counts: Dict[str, int]) -> None:
    print(f"\n{len(plans)} tables to copy (in this order):")
    for p in plans:
        print(f"  {p.name:28} {counts.get(p.name, 0):>7} rows")
        for c in p.conversions:
            print(f"      converts {c}")
        if p.dropped:
            print(f"      leaves behind: {', '.join(p.dropped)}")
    if source_only:
        print(f"Not copied (no table in the new schema): {', '.join(source_only)}")


def _print_results(results: List[TableResult]) -> bool:
    ok = True
    print(f"\n{'table':32} {'source':>7} {'copied':>7} {'already':>8}  skipped")
    for r in results:
        skipped = sum(r.skipped.values())
        note = ", ".join(f"{n} {why}" for why, n in r.skipped.items())
        print(f"{r.name:32} {r.source:>7} {r.inserted:>7} {r.existing:>8}  {skipped or ''} {note}")
        if r.inserted + r.existing + skipped != r.source:
            ok = False
    return ok


def run(source: str, target: str, *, dry_run: bool = False, reindex: bool = True,
        source_schema: str = "public", auth_schema: str = "auth", apply_schema: bool = True) -> int:
    if apply_schema:  # creates empty tables only (the app does the same on startup), also on a dry run
        from db.migrate import migrate
        applied = migrate(target)
        print(f"Target schema: {', '.join(applied) if applied else 'already up to date'}")

    with psycopg.connect(source) as src, psycopg.connect(target, autocommit=True) as dst:
        src.read_only = True
        plans, source_only = plan(src, dst, source_schema)
        counts = {p.name: src.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
            sql.Identifier(source_schema), sql.Identifier(p.name))).fetchone()[0] for p in plans}
        _print_plan(plans, source_only, counts)
        if dry_run:
            users = src.execute(sql.SQL("SELECT count(*) FROM {}.users").format(sql.Identifier(auth_schema))).fetchone()[0]
            print(f"\nDry run: no rows written. {users} sign-in accounts would become app_users.")
            return 0

        results = [copy_app_users(src, dst, auth_schema)]
        for p in plans:
            results.append(copy_table(src, dst, p, source_schema))
            print(f"  copied {p.name}")
        for label, stmt in FOLLOW_UPS:
            n = dst.execute(stmt).rowcount
            print(f"  {label}: {n}")
        ok = _print_results(results)
        if reindex:
            print(f"\nQueued {queue_reindex(dst)} books for re-indexing (the worker rebuilds their passages).")
    print("\nDone." if ok else "\nCounts don't add up: see the table above.")
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", default=os.environ.get("SOURCE_DATABASE_URL"), help="Supabase Postgres URL")
    ap.add_argument("--target", default=os.environ.get("DATABASE_URL"), help="new Postgres URL")
    ap.add_argument("--dry-run", action="store_true", help="show the plan and row counts, write nothing")
    ap.add_argument("--no-reindex", action="store_true", help="don't queue re-index jobs")
    ap.add_argument("--source-schema", default="public")
    ap.add_argument("--auth-schema", default="auth")
    a = ap.parse_args(argv)
    if not a.source or not a.target:
        ap.error("set SOURCE_DATABASE_URL and DATABASE_URL (or --source / --target)")
    if a.source == a.target and a.source_schema == "public":
        ap.error("source and target are the same database")
    return run(a.source, a.target, dry_run=a.dry_run, reindex=not a.no_reindex,
               source_schema=a.source_schema, auth_schema=a.auth_schema)


if __name__ == "__main__":
    sys.exit(main())
