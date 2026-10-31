"""Cross-user access: user B must never reach user A's projects or documents."""

import asyncio
import re
import uuid

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api import access
from api.deps import get_current_user
from db.client import SupabaseClient
from tests.fake_supabase import FakeClient

USER_A, USER_B = str(uuid.uuid4()), str(uuid.uuid4())
PA, PB = str(uuid.uuid4()), str(uuid.uuid4())   # A's project, B's project
DA, DB = str(uuid.uuid4()), str(uuid.uuid4())   # a document in each


@pytest.fixture
def db(monkeypatch):
    fake = FakeClient()
    fake.tables["projects"] = [
        {"id": PA, "user_id": USER_A, "name": "A"},
        {"id": PB, "user_id": USER_B, "name": "B"},
    ]
    fake.tables["documents"] = [
        {"id": DA, "project_id": PA, "filename": "a.pdf"},
        {"id": DB, "project_id": PB, "filename": "b.pdf"},
    ]
    monkeypatch.setattr(SupabaseClient, "_instance", fake)
    access.clear_cache()
    return fake


@pytest.fixture
def client(db):
    from main import app

    app.dependency_overrides[get_current_user] = lambda: {"id": USER_B, "email": "b@x.com", "managed": False}
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def guarded_routes():
    from main import app

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not any(getattr(d.dependency, "__name__", "") == "enforce_resource_access"
                   for d in route.dependencies):
            continue
        yield route


def test_path_project_of_other_user_404(client):
    assert client.get(f"/api/v1/chat/history/{PA}").status_code == 404


def test_guard_is_attached_to_chat(client):
    paths = {r.path for r in guarded_routes()}
    assert "/api/v1/chat/history/{project_id}" in paths
    assert "/api/v1/auth/login" not in paths


def test_every_path_route_with_project_or_document_id_404(client):
    checked = 0
    for route in guarded_routes():
        if "{project_id}" not in route.path and "{document_id}" not in route.path:
            continue
        path = route.path.replace("{project_id}", PA).replace("{document_id}", DA)
        path = re.sub(r"\{[^}]+\}", "x", path)
        for method in route.methods:
            res = client.request(method, path, params={"project_id": PA}, json={"project_id": PA})
            assert res.status_code == 404, f"{method} {route.path} -> {res.status_code}"
            checked += 1
    assert checked > 30


def test_body_project_of_other_user_404(client):
    res = client.post("/api/v1/chat/stream", json={"project_id": PA, "message": "hi"})
    assert res.status_code == 404


def test_selected_documents_from_other_project_404(client):
    res = client.post("/api/v1/chat/message",
                      json={"project_id": PB, "message": "x", "selected_documents": [DA]})
    assert res.status_code == 404


def test_nested_batch_ids_checked(client):
    body = {"interactions": [{"project_id": PB, "topic": "t"}, {"project_id": PA, "topic": "t"}]}
    res = client.post("/api/v1/knowledge-graph/analytics/record-batch", json=body)
    assert res.status_code == 404


def test_malformed_id_404(client):
    assert client.get("/api/v1/chat/history/not-a-uuid").status_code == 404


def test_query_project_id_checked(client):
    assert client.delete(f"/api/v1/documents/{DA}", params={"project_id": PA}).status_code == 404


def test_document_in_own_project_but_wrong_pairing_404(client):
    # B's own project, but A's document
    assert client.get(f"/api/v1/documents/{PB}/{DA}/text").status_code == 404


def test_owner_passes(db):
    asyncio.run(access.assert_project_owner(PA, USER_A))
    asyncio.run(access.assert_documents_in_project([DA], USER_A, PA))


def test_owner_checks_reject_other_user(db):
    with pytest.raises(HTTPException) as e:
        asyncio.run(access.assert_project_owner(PA, USER_B))
    assert e.value.status_code == 404
    with pytest.raises(HTTPException):
        asyncio.run(access.assert_documents_in_project([DA], USER_B, None))


@pytest.fixture
def owner_client(db):
    from main import app

    app.dependency_overrides[get_current_user] = lambda: {"id": USER_A, "email": "a@x.com", "managed": False}
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_owner_reaches_own_chat_history(owner_client, db):
    db.tables["chat_messages"] = [{"id": "m1", "project_id": PA, "role": "user", "content": "hello"}]
    res = owner_client.get(f"/api/v1/chat/history/{PA}")
    assert res.status_code == 200
    assert res.json()[0]["content"] == "hello"


def test_owner_post_body_still_reaches_handler(owner_client, db, monkeypatch):
    # The guard reads the JSON body; the handler must still receive it intact.
    from services.user_data_service import user_data
    monkeypatch.setattr(user_data, "client", db)
    res = owner_client.post("/api/v1/user-data/bookmarks",
                            json={"project_id": PA, "title": "Ch 1", "document_id": DA})
    assert res.status_code == 200, res.text
    assert any(b.get("title") == "Ch 1" for b in db.tables.get("bookmarks", []))


def test_multipart_upload_to_other_users_project_404(client):
    res = client.post("/api/v1/documents/upload", data={"project_id": PA},
                      files={"file": ("a.txt", b"hello", "text/plain")})
    assert res.status_code == 404
