import os
import sys

# Settings are read at import time; give them harmless values (no network is used).
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("INSTITUTION_REQUIRE_APPROVAL", "true")
os.environ.setdefault("INSTITUTION_TRIAL_DAYS", "14")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---- real-Postgres fixtures (tests using them skip when TEST_DATABASE_URL isn't set)
import uuid as _uuid

import pytest


@pytest.fixture(scope="session")
def pg_url():
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg

    name = f"lumina_test_{_uuid.uuid4().hex[:8]}"
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = base.rsplit("/", 1)[0] + "/" + name
    from db.migrate import migrate

    migrate(url)
    yield url
    with psycopg.connect(base, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def pg_client(pg_url):
    from db.pg import PgClient

    client = PgClient(pg_url, max_size=8)
    yield client
    client.close()
