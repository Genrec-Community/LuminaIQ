"""Uploads are queued as jobs; the file reaches the worker through staging storage (or host pinning)."""

import asyncio
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from api.deps import get_current_user
from db.client import SupabaseClient
from utils import job_queue as q
from utils.worker import HOST

USER = str(uuid.uuid4())


class FakeBucket:
    def __init__(self, store, name, fail=False):
        self.store, self.name, self.fail = store, name, fail

    def upload(self, file, path, file_options=None):
        if self.fail:
            raise RuntimeError("storage down")
        self.store[f"{self.name}/{path}"] = file

    def download(self, path):
        return self.store[f"{self.name}/{path}"]

    def remove(self, paths):
        for p in paths:
            self.store.pop(f"{self.name}/{p}", None)


class FakeStorage:
    def __init__(self, fail=False):
        self.files, self.fail = {}, fail

    def from_(self, bucket):
        return FakeBucket(self.files, bucket, self.fail)


class TestAppClient:
    """Real Postgres for data, fake Supabase storage."""

    def __init__(self, pg, storage):
        self.pg, self.storage = pg, storage

    def table(self, name):
        return self.pg.table(name)

    def rpc(self, name, params=None):
        return self.pg.rpc(name, params)


@pytest.fixture
def setup(pg_client, monkeypatch):
    with pg_client.pool.connection() as conn:
        conn.execute("TRUNCATE jobs, projects CASCADE")
    project = pg_client.table("projects").insert({"user_id": USER, "name": "Bio"}).execute().data[0]
    storage = FakeStorage()
    monkeypatch.setattr(SupabaseClient, "_instance", TestAppClient(pg_client, storage))
    from api import access
    access.clear_cache()
    from main import app

    app.dependency_overrides[get_current_user] = lambda: {"id": USER, "email": "u@x.com", "managed": False}
    yield TestClient(app, raise_server_exceptions=False), pg_client, storage, project
    app.dependency_overrides.clear()


def _upload(client, project_id):
    return client.post("/api/v1/documents/upload", data={"project_id": project_id},
                       files={"file": ("cells.txt", b"Cells are the unit of life.", "text/plain")})


def test_upload_enqueues_process_document_job(setup):
    client, pg, storage, project = setup
    res = _upload(client, project["id"])
    assert res.status_code == 200, res.text
    doc_id = res.json()["id"] if "id" in res.json() else res.json()["document_id"]
    jobs = pg.fetch("SELECT kind, payload, pinned_host, dedupe_key FROM jobs")
    assert len(jobs) == 1 and jobs[0]["kind"] == "process_document"
    payload = jobs[0]["payload"]
    assert payload["document_id"] == doc_id and payload["project_id"] == project["id"]
    assert payload["staged"] == f"documents/_staging/{doc_id}.txt"
    assert storage.files[payload["staged"]] == b"Cells are the unit of life."
    assert jobs[0]["pinned_host"] is None and jobs[0]["dedupe_key"] == f"process_document:{doc_id}"


def test_staging_failure_pins_to_host(setup):
    client, pg, storage, project = setup
    storage.fail = True
    assert _upload(client, project["id"]).status_code == 200
    job = pg.fetch("SELECT payload, pinned_host FROM jobs")[0]
    assert job["pinned_host"] == HOST
    assert os.path.exists(job["payload"]["local_path"])
    os.unlink(job["payload"]["local_path"])


def test_handler_reads_staged_file_and_cleans_up(setup, monkeypatch):
    client, pg, storage, project = setup
    storage.files["documents/_staging/d1.txt"] = b"hello"
    seen = {}

    async def fake_process(**kw):
        with open(kw["file_path"], "rb") as f:
            seen["data"] = f.read()
        seen["doc"] = kw["document_id"]
        os.unlink(kw["file_path"])

    from services import jobs
    from services.document_service import document_service
    monkeypatch.setattr(document_service, "process_document", fake_process)
    job = {"id": "j", "payload": {"document_id": "d1", "project_id": project["id"], "filename": "a.txt",
                                  "user_id": USER, "staged": "documents/_staging/d1.txt"}}
    assert asyncio.run(jobs.handle_process_document(job)) == {"document_id": "d1"}
    assert seen == {"data": b"hello", "doc": "d1"}
    assert "documents/_staging/d1.txt" not in storage.files


def test_jobs_api_shows_only_own_jobs(setup):
    client, pg, storage, project = setup
    mine = q.enqueue(pg, "process_document", {}, user_id=USER)
    theirs = q.enqueue(pg, "process_document", {}, user_id=str(uuid.uuid4()))
    assert client.get(f"/api/v1/jobs/status/{mine['id']}").json()["status"] == "pending"
    assert client.get(f"/api/v1/jobs/status/{theirs['id']}").status_code == 404
    assert [j["job_id"] for j in client.get("/api/v1/jobs/my-jobs").json()] == [mine["id"]]
    assert client.post("/api/v1/jobs/submit", json={"job_type": "generate_mcq"}).status_code == 400
