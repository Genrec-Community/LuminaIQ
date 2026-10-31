"""
The Postgres query layer must behave like the supabase-py calls the services
already make. These run against a real Postgres (TEST_DATABASE_URL, e.g. the
docker compose one) in a fresh, throwaway database with the full schema.
"""

import os
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

BASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture(scope="module")
def db_url():
    name = f"lumina_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(BASE_URL, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = BASE_URL.rsplit("/", 1)[0] + "/" + name
    from db.migrate import migrate

    migrate(url)
    yield url
    with psycopg.connect(BASE_URL, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def pg(db_url):
    from db.pg import PgClient

    client = PgClient(db_url, max_size=4)
    yield client
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("TRUNCATE projects, documents, books, book_imports, usage_counters, "
                     "unlimited_access, app_users, institution_members, institutions CASCADE")
    client.close()


def new_project(pg, user=None, name="P"):
    return pg.table("projects").insert({"user_id": user or str(uuid.uuid4()), "name": name}).execute().data[0]


# ---------------------------------------------------------------- migrations

def test_migrations_are_recorded_and_idempotent(db_url):
    from db.migrate import migrate

    assert migrate(db_url) == []          # second run applies nothing
    with psycopg.connect(db_url) as conn:
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert "0001_init" in versions


# ---------------------------------------------------------------- insert / select

def test_insert_returns_rows_with_string_ids_and_iso_timestamps(pg):
    row = new_project(pg, name="Physics")
    assert isinstance(row["id"], str) and uuid.UUID(row["id"])
    assert isinstance(row["user_id"], str)
    assert isinstance(row["created_at"], str) and "T" in row["created_at"]
    assert row["name"] == "Physics"


def test_insert_many_and_select_columns(pg):
    user = str(uuid.uuid4())
    pg.table("projects").insert([{"user_id": user, "name": "A"}, {"user_id": user, "name": "B"}]).execute()
    res = pg.table("projects").select("id, name").eq("user_id", user).order("name").execute()
    assert [r["name"] for r in res.data] == ["A", "B"]
    assert set(res.data[0]) == {"id", "name"}


def test_filters(pg):
    user = str(uuid.uuid4())
    for n in ("a", "b", "c", "d"):
        new_project(pg, user, n)
    t = lambda: pg.table("projects").select("name").eq("user_id", user)
    assert [r["name"] for r in t().neq("name", "a").order("name").execute().data] == ["b", "c", "d"]
    assert [r["name"] for r in t().in_("name", ["a", "c"]).order("name").execute().data] == ["a", "c"]
    assert [r["name"] for r in t().gt("name", "b").order("name").execute().data] == ["c", "d"]
    assert [r["name"] for r in t().gte("name", "b").lt("name", "d").order("name").execute().data] == ["b", "c"]
    assert [r["name"] for r in t().lte("name", "a").execute().data] == ["a"]
    assert [r["name"] for r in t().match({"name": "d"}).execute().data] == ["d"]


def test_in_with_uuid_column_and_empty_list(pg):
    p1, p2 = new_project(pg), new_project(pg)
    res = pg.table("projects").select("id").in_("id", [p1["id"], p2["id"]]).execute()
    assert {r["id"] for r in res.data} == {p1["id"], p2["id"]}
    assert pg.table("projects").select("id").in_("id", []).execute().data == []


def test_order_desc_limit_range_and_count(pg):
    user = str(uuid.uuid4())
    for n in "abcde":
        new_project(pg, user, n)
    q = pg.table("projects").select("name", count="exact").eq("user_id", user).order("name", desc=True)
    res = q.range(1, 2).execute()
    assert [r["name"] for r in res.data] == ["d", "c"]
    assert res.count == 5
    assert len(pg.table("projects").select("*").eq("user_id", user).limit(2).execute().data) == 2
    assert pg.table("projects").select("id").eq("user_id", user).execute().count is None


def test_is_null_and_or(pg):
    user = str(uuid.uuid4())
    pg.table("institution_members")  # table exists
    proj = new_project(pg, user)
    d1 = pg.table("documents").insert({"project_id": proj["id"], "filename": "Alpha.pdf"}).execute().data[0]
    pg.table("documents").insert({"project_id": proj["id"], "filename": "beta.pdf", "file_type": "pdf"}).execute()
    assert [r["id"] for r in pg.table("documents").select("id").is_("file_type", "null").execute().data] == [d1["id"]]
    res = pg.table("documents").select("filename").or_("filename.ilike.%alp%,file_type.eq.pdf").order("filename").execute()
    assert [r["filename"] for r in res.data] == ["Alpha.pdf", "beta.pdf"]
    res = pg.table("documents").select("filename").or_("file_type.is.null,filename.lte.B").execute()
    assert [r["filename"] for r in res.data] == ["Alpha.pdf"]


def test_array_contains_and_jsonb_roundtrip(pg):
    user = str(uuid.uuid4())
    b = pg.table("books").insert({"user_id": user, "title": "T", "tags": ["math", "class-8"]}).execute().data[0]
    assert b["tags"] == ["math", "class-8"]
    assert pg.table("books").select("id").contains("tags", ["math"]).execute().data[0]["id"] == b["id"]
    assert pg.table("books").select("id").contains("tags", ["chemistry"]).execute().data == []
    proj = new_project(pg, user)
    topics = [{"name": "Motion", "pages": [1, 2]}, "Force"]
    d = pg.table("documents").insert({"project_id": proj["id"], "filename": "x", "topics": topics}).execute().data[0]
    assert d["topics"] == topics


def test_single_and_maybe_single(pg):
    p = new_project(pg)
    assert pg.table("projects").select("*").eq("id", p["id"]).single().execute().data["id"] == p["id"]
    with pytest.raises(Exception):
        pg.table("projects").select("*").eq("id", str(uuid.uuid4())).single().execute()
    assert pg.table("projects").select("*").eq("id", str(uuid.uuid4())).maybe_single().execute().data is None


# ---------------------------------------------------------------- update / upsert / delete

def test_update_and_delete_return_rows(pg):
    p = new_project(pg, name="old")
    res = pg.table("projects").update({"name": "new"}).eq("id", p["id"]).execute()
    assert res.data[0]["name"] == "new"
    gone = pg.table("projects").delete().eq("id", p["id"]).execute()
    assert gone.data[0]["id"] == p["id"]
    assert pg.table("projects").select("*").eq("id", p["id"]).execute().data == []


def test_upsert_on_conflict(pg):
    p = new_project(pg)
    pg.table("project_summaries").upsert({"project_id": p["id"], "summary": "v1"}, on_conflict="project_id").execute()
    pg.table("project_summaries").upsert({"project_id": p["id"], "summary": "v2"}, on_conflict="project_id").execute()
    rows = pg.table("project_summaries").select("summary").eq("project_id", p["id"]).execute().data
    assert rows == [{"summary": "v2"}]


def test_upsert_defaults_to_primary_key_and_ignore_duplicates(pg):
    uid = str(uuid.uuid4())
    pg.table("app_users").upsert({"id": uid, "email": "a@x.com"}).execute()
    pg.table("app_users").upsert({"id": uid, "email": "b@x.com"}).execute()
    assert pg.table("app_users").select("email").eq("id", uid).execute().data == [{"email": "b@x.com"}]
    pg.table("app_users").upsert({"id": uid, "email": "c@x.com"}, ignore_duplicates=True).execute()
    assert pg.table("app_users").select("email").eq("id", uid).execute().data == [{"email": "b@x.com"}]


def test_unique_violation_message_matches_supabase(pg):
    pg.table("unlimited_access").insert({"email": "t@x.com"}).execute()
    with pytest.raises(Exception) as e:
        pg.table("unlimited_access").insert({"email": "t@x.com"}).execute()
    assert "duplicate key value violates unique constraint" in str(e.value)


def test_unknown_column_is_an_error(pg):
    with pytest.raises(Exception):
        pg.table("projects").select("*").eq("nope", 1).execute()


# ---------------------------------------------------------------- rpc

def test_rpc_scalar_void_and_counting(pg):
    uid = str(uuid.uuid4())
    assert pg.rpc("is_unlimited", {"p_user": uid}).execute().data is False
    pg.table("app_users").insert({"id": uid, "email": "Tester@X.com"}).execute()
    pg.table("unlimited_access").insert({"email": "tester@x.com"}).execute()
    assert pg.rpc("is_unlimited", {"p_user": uid}).execute().data is True

    args = {"p_user": uid, "p_feature": "chat", "p_period": "2026-10-31", "p_amount": 1, "p_limit": -1}
    assert pg.rpc("consume_usage", args).execute().data == 1
    assert pg.rpc("consume_usage", args).execute().data == 2

    user = str(uuid.uuid4())
    book = pg.table("books").insert({"user_id": user, "title": "B"}).execute().data[0]
    assert pg.rpc("increment_book_import_count", {"book_id_input": book["id"]}).execute().data is None
    assert pg.table("books").select("import_count").eq("id", book["id"]).execute().data[0]["import_count"] == 1


def test_values_are_parameters_not_sql(pg):
    p = new_project(pg, name="safe")
    evil = "x'; DROP TABLE projects; --"
    assert pg.table("projects").select("*").eq("name", evil).execute().data == []
    assert pg.table("projects").select("id").eq("id", p["id"]).execute().data
