"""Copying live Supabase data into the new Postgres (scripts/migrate_from_supabase.py).

The source database mimics the live Supabase tables (same column types, including the
ones that differ from the new schema) plus Supabase's auth.users.
"""

import json
import os
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

U1, U2 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
P1, P_GONE = "aaaaaaaa-0000-0000-0000-000000000001", "aaaaaaaa-0000-0000-0000-000000000099"
D1, D_ORPHAN = "dddddddd-0000-0000-0000-000000000001", "dddddddd-0000-0000-0000-000000000009"

SOURCE_DDL = """
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY, email text, created_at timestamptz, last_sign_in_at timestamptz);
CREATE TABLE projects (id uuid, created_at timestamptz, name text, user_id uuid, updated_at timestamptz);
CREATE TABLE documents (id uuid, project_id uuid, filename text, file_type text, file_size integer, upload_status text,
  error_message text, created_at timestamptz, user_id uuid, topics jsonb, updated_at timestamptz, file_url text,
  text_storage_path text, topic_outline jsonb, progress jsonb);
CREATE TABLE chat_messages (id uuid, project_id uuid, role text, content text, sources jsonb, created_at timestamptz);
CREATE TABLE mcq_tests (id uuid, project_id uuid, chapter_name text, questions jsonb, created_at timestamptz);
CREATE TABLE learning_progress (id uuid, user_id uuid, project_id uuid, completed_topics text[], updated_at timestamptz);
CREATE TABLE user_plans (user_id uuid, plan text, status text, source text, billing_cycle text,
  current_period_end timestamptz, cancel_at_period_end boolean, razorpay_subscription_id text,
  razorpay_customer_id text, institution_id uuid, updated_at timestamptz, pass_until timestamptz,
  current_period_start timestamptz, last_payment_at timestamptz);
CREATE TABLE book_imports (id uuid, book_id uuid, user_id uuid, project_id uuid, document_id uuid, imported_at timestamptz);
CREATE TABLE document_chunks (id uuid, document_id uuid, chunk_text text);
"""

SOURCE_ROWS = f"""
INSERT INTO auth.users VALUES ('{U1}', 'a@example.com', now() - interval '9 days', now()),
                              ('{U2}', 'b@example.com', now() - interval '3 days', NULL);
INSERT INTO projects VALUES ('{P1}', now(), 'Biology', '{U1}', now());
INSERT INTO documents (id, project_id, filename, upload_status, user_id, topics, text_storage_path)
  VALUES ('{D1}', '{P1}', 'bio.pdf', 'completed', '{U1}', '["Cell"]', '{P1}/{D1}.txt'),
         ('{D_ORPHAN}', '{P_GONE}', 'gone.pdf', 'completed', '{U1}', '[]', NULL);
INSERT INTO chat_messages VALUES (gen_random_uuid(), '{P1}', 'user', 'What is a cell?', NULL, now() - interval '1 min'),
                                 (gen_random_uuid(), '{P1}', 'assistant', 'A cell is...', '[]', now()),
                                 (gen_random_uuid(), '{P_GONE}', 'user', 'lost', NULL, now());
-- the app stored json.dumps() output in jsonb: a JSON string holding the questions
INSERT INTO mcq_tests VALUES (gen_random_uuid(), '{P1}', 'Cell',
  to_jsonb('[{{"question": "What is \\\\frac{{1}}{{2}}?"}}]'::text), now());
INSERT INTO learning_progress VALUES (gen_random_uuid(), '{U1}', '{P1}', ARRAY['Cell', 'DNA'], now());
-- updated_at / cancel flag missing: the new schema requires them, so they take its defaults
INSERT INTO user_plans (user_id, plan, status, source) VALUES ('{U1}', 'scholar', 'active', 'razorpay');
"""


@pytest.fixture
def source_url():
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL not set")
    name = f"supabase_src_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = base.rsplit("/", 1)[0] + "/" + name
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SOURCE_DDL)
        conn.execute(SOURCE_ROWS)
    yield url
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def target_url():
    """A fresh, empty new-schema database per test (the shared pg_url one keeps rows across tests)."""
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL not set")
    name = f"aws_target_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = base.rsplit("/", 1)[0] + "/" + name
    yield url
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def _q(url, query):
    with psycopg.connect(url) as conn:
        return conn.execute(query).fetchall()


def test_copies_converts_and_requeues(source_url, target_url, capsys):
    from scripts.migrate_from_supabase import run

    assert run(source_url, target_url) == 0

    # sign-in accounts become app_users (never signed in → sign-up time counts as last seen)
    assert {r[0] for r in _q(target_url, "SELECT email FROM app_users")} == {"a@example.com", "b@example.com"}

    # JSON strings stored in jsonb are unwrapped to the text the app json.loads()
    (questions,) = _q(target_url, "SELECT questions FROM mcq_tests")[0]
    assert json.loads(questions) == [{"question": "What is \\frac{1}{2}?"}]

    # text[] → jsonb array
    assert _q(target_url, "SELECT completed_topics FROM learning_progress")[0][0] == ["Cell", "DNA"]

    # nulls in now-required columns take the default instead of losing the plan
    plan, cancel = _q(target_url, "SELECT plan, cancel_at_period_end FROM user_plans")[0]
    assert (plan, cancel) == ("scholar", False)

    # rows whose project no longer exists are skipped and reported
    assert [r[0] for r in _q(target_url, "SELECT id::text FROM documents")] == [D1]
    out = capsys.readouterr().out
    assert "parent row missing" in out

    # old messages land in one "Earlier chat" per book
    assert _q(target_url, "SELECT count(*), count(thread_id) FROM chat_messages")[0] == (2, 2)
    assert _q(target_url, "SELECT title FROM chat_threads")[0][0] == "Earlier chat"

    # completed books get a re-index job (passages are rebuilt from the stored text)
    jobs = _q(target_url, "SELECT kind, payload FROM jobs")
    assert [(k, p["document"]["id"]) for k, p in jobs] == [("reindex_document", D1)]

    # vectors and Supabase-only tables aren't copied
    assert _q(target_url, "SELECT count(*) FROM chunks")[0][0] == 0


def test_running_twice_adds_nothing(source_url, target_url):
    from scripts.migrate_from_supabase import run

    assert run(source_url, target_url) == 0
    before = _q(target_url, "SELECT (SELECT count(*) FROM projects), (SELECT count(*) FROM chat_messages), "
                        "(SELECT count(*) FROM chat_threads), (SELECT count(*) FROM jobs)")
    assert run(source_url, target_url) == 0
    after = _q(target_url, "SELECT (SELECT count(*) FROM projects), (SELECT count(*) FROM chat_messages), "
                       "(SELECT count(*) FROM chat_threads), (SELECT count(*) FROM jobs)")
    assert before == after


def test_dry_run_writes_no_rows(source_url, target_url):
    from scripts.migrate_from_supabase import run

    assert run(source_url, target_url, dry_run=True) == 0
    assert _q(target_url, "SELECT count(*) FROM projects")[0][0] == 0
