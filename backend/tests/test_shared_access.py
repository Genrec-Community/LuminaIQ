"""
Shared access that must keep working behind the ownership guard:
class-book copies, Book Store imports and institution staff views.
"""

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import access
from api.deps import get_current_user
from db.client import SupabaseClient
from services import institution_service as isvc
from tests.fake_supabase import FakeClient


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def fake(monkeypatch):
    from services.usage_service import usage

    db = FakeClient()
    monkeypatch.setattr(SupabaseClient, "_instance", db)
    monkeypatch.setattr(usage, "client", db)
    usage._plans.clear()
    access.clear_cache()

    async def create_project(user_id, name):
        row = {"id": str(uuid.uuid4()), "user_id": user_id, "name": name}
        db.tables.setdefault("projects", []).append(row)
        return row
    from services.project_service import project_service
    monkeypatch.setattr(project_service, "create_project", create_project)
    return db


@pytest.fixture
def svc(fake, monkeypatch):
    from services.qdrant_service import qdrant_service

    async def no_vectors(*a, **k):
        return None
    monkeypatch.setattr(qdrant_service, "copy_document_vectors", no_vectors)
    service = isvc.InstitutionService.__new__(isvc.InstitutionService)
    service.client = fake
    service._inst_cache, service._access_cache = {}, {}
    service._id_lock = asyncio.Lock()
    monkeypatch.setattr(isvc, "institutions", service)
    return service


def _as(user_id):
    from main import app

    app.dependency_overrides[get_current_user] = lambda: {"id": user_id, "email": "x@x.com", "managed": False}
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    from main import app
    app.dependency_overrides.clear()


@pytest.fixture
def school(svc, fake):
    """A teacher publishes a book from their own project; a student joins the class and gets a copy."""
    teacher = {"id": str(uuid.uuid4()), "email": "teacher@school.in"}
    student = {"id": str(uuid.uuid4()), "email": "student@x.com"}
    inst = run(svc.create(teacher, "Green Valley School", "", "", "", "Principal"))
    run(svc.approve({"id": "platform"}, inst["id"]))
    cls = run(svc.create_class(teacher, "10 A"))

    tp, td = str(uuid.uuid4()), str(uuid.uuid4())
    fake.tables.setdefault("projects", []).append({"id": tp, "user_id": teacher["id"], "name": "Teacher"})
    fake.tables.setdefault("documents", []).append({
        "id": td, "project_id": tp, "user_id": teacher["id"], "filename": "physics.pdf",
        "upload_status": "completed", "topics": ["Motion"], "file_url": "teacher/physics.pdf"})
    run(svc.publish_book(teacher, cls["id"], td))
    joined = run(svc.join(student, cls["invite_code"], "Stu"))
    copy = fake.tables["class_book_copies"][0]
    return {"teacher": teacher, "student": student, "class": cls, "teacher_project": tp,
            "teacher_doc": td, "student_project": joined["project_id"], "copy_doc": copy["document_id"]}


def test_student_reaches_class_book_copy(school):
    run(access.assert_documents_in_project([school["copy_doc"]], school["student"]["id"],
                                           school["student_project"]))
    res = _as(school["student"]["id"]).get(f"/api/v1/chat/history/{school['student_project']}")
    assert res.status_code == 200


def test_student_cannot_reach_teachers_source_book(school):
    with pytest.raises(HTTPException) as e:
        run(access.assert_documents_in_project([school["teacher_doc"]], school["student"]["id"], None))
    assert e.value.status_code == 404
    res = _as(school["student"]["id"]).get(f"/api/v1/chat/history/{school['teacher_project']}")
    assert res.status_code == 404


def test_staff_class_dashboard_still_sees_students(school, svc):
    dash = run(svc.class_dashboard(school["teacher"], school["class"]["id"]))
    assert [r["user_id"] for r in dash["students"]] == [school["student"]["id"]]


def test_institutions_router_is_not_behind_project_guard():
    from main import app
    from fastapi.routing import APIRoute

    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/institutions"):
            assert not any(getattr(d.dependency, "__name__", "") == "enforce_resource_access"
                           for d in route.dependencies), route.path


def test_book_store_import_into_own_project(fake, monkeypatch):
    from services.book_service import book_service

    owner, importer = str(uuid.uuid4()), str(uuid.uuid4())
    op, od, ip = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    book = str(uuid.uuid4())
    fake.tables["projects"] = [{"id": op, "user_id": owner, "name": "O"},
                               {"id": ip, "user_id": importer, "name": "I"}]
    fake.tables["documents"] = [{"id": od, "project_id": op, "user_id": owner, "filename": "b.txt"}]
    fake.tables["books"] = [{"id": book, "user_id": owner, "document_id": od, "title": "Book",
                             "is_public": True, "text_path": "o/b.txt", "import_count": 0}]

    async def no_clone(*a, **k):
        return None
    monkeypatch.setattr(book_service, "_background_clone", no_clone)

    client = _as(importer)
    res = client.post(f"/api/v1/books/{book}/import", json={"project_id": ip})
    assert res.status_code == 200, res.text
    new_doc = res.json()["document"]["id"]
    assert fake.tables["book_imports"][0]["document_id"] == new_doc
    # The imported copy is the importer's own document
    run(access.assert_documents_in_project([new_doc], importer, ip))
    # ...but importing into someone else's project is refused
    assert client.post(f"/api/v1/books/{book}/import", json={"project_id": op}).status_code == 404
