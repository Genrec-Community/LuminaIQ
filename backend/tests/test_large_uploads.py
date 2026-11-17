"""Books bigger than one storage object (50 MB) are uploaded, staged and stored in parts."""

import asyncio
import os
import shutil
import pytest

from config.settings import settings
from utils import split_storage

from tests.test_upload_jobs import USER, FakeStorage, setup  # noqa: F401  (fixture)

MB = 1024 * 1024


class StrictStorage(FakeStorage):
    """Refuses objects over the per-object limit, like Supabase does."""

    def __init__(self, limit):
        super().__init__()
        self.limit = limit

    def from_(self, bucket):
        bucket_obj = super().from_(bucket)
        upload = bucket_obj.upload

        def checked(file, path, file_options=None):
            if len(file) > self.limit:
                raise RuntimeError("Payload too large")
            upload(file, path, file_options)

        bucket_obj.upload = checked
        return bucket_obj


class Client:
    def __init__(self, storage):
        self.storage = storage


@pytest.fixture
def small_parts(monkeypatch):
    """Shrink the limits so tests move kilobytes, not 150 MB."""
    monkeypatch.setattr(split_storage, "SINGLE_MAX", 1000)
    monkeypatch.setattr(settings, "STORAGE_PART_BYTES", 400)


def _file(tmp_path, size):
    data = os.urandom(size)
    p = tmp_path / "book.pdf"
    p.write_bytes(data)
    return str(p), data


# ---------------------------------------------------------------- split_storage

def test_refs_round_trip():
    assert split_storage.make_ref("documents", "p/d.pdf", 1) == "documents/p/d.pdf"
    assert split_storage.make_ref("documents", "p/d.pdf", 4) == "documents/p/d.pdf#parts=4"
    assert split_storage.parse_ref("documents/p/d.pdf") == ("documents", "p/d.pdf", 1)
    assert split_storage.parse_ref("documents/p/d.pdf#parts=4") == ("documents", "p/d.pdf", 4)
    assert split_storage.parse_ref("") is None and split_storage.parse_ref(None) is None


def test_real_limits_150mb_book_needs_four_parts_under_50mb():
    assert split_storage.parts_needed(50 * MB) == 1          # what used to work stays one object
    assert split_storage.parts_needed(150 * MB) == 4
    assert split_storage.part_bytes() < 50 * MB
    assert settings.MAX_FILE_SIZE >= 150 * MB


def test_small_file_is_one_object_at_the_same_path(tmp_path, small_parts):
    path, data = _file(tmp_path, 900)
    storage = StrictStorage(1000)
    assert split_storage.upload_file(Client(storage), "documents", "p/d.pdf", path) == 1
    assert storage.files == {"documents/p/d.pdf": data}


def test_big_file_is_split_and_joined_back(tmp_path, small_parts):
    path, data = _file(tmp_path, 2500)
    storage = StrictStorage(1000)
    client = Client(storage)
    parts = split_storage.upload_file(client, "documents", "p/d.pdf", path, "application/pdf")
    assert parts == 7
    assert sorted(storage.files) == sorted(f"documents/p/d.pdf.part{i}" for i in range(7))
    out = str(tmp_path / "joined.pdf")
    assert split_storage.download_to(client, "documents", "p/d.pdf", parts, out) == 2500
    with open(out, "rb") as f:
        assert f.read() == data
    split_storage.remove(client, "documents", "p/d.pdf", parts)
    assert storage.files == {}


# ---------------------------------------------------------------- staging for the worker

def test_big_upload_is_staged_in_parts_and_worker_joins_them(setup, small_parts, monkeypatch):
    client, pg, storage, project = setup
    data = os.urandom(2100)
    res = client.post("/api/v1/documents/upload", data={"project_id": project["id"]},
                      files={"file": ("big.txt", data, "text/plain")})
    assert res.status_code == 200, res.text
    job = pg.fetch("SELECT payload, pinned_host FROM jobs")[0]
    payload = job["payload"]
    assert job["pinned_host"] is None
    assert payload["staged"].endswith("#parts=6")
    assert all(len(v) <= 1000 for v in storage.files.values())

    seen = {}

    async def fake_process(**kw):
        with open(kw["file_path"], "rb") as f:
            seen["data"] = f.read()
        os.unlink(kw["file_path"])

    from services import jobs
    from services.document_service import document_service
    monkeypatch.setattr(document_service, "process_document", fake_process)
    asyncio.run(jobs.handle_process_document({"id": "j", "payload": payload}))
    assert seen["data"] == data
    assert not any(k.startswith("documents/_staging/") for k in storage.files)


# ---------------------------------------------------------------- browser upload in parts

def test_upload_url_hands_out_one_permit_per_part(setup, monkeypatch):
    client, pg, storage, project = setup
    from api.v1.endpoints import documents

    async def fake_sign(path):
        return f"token-for-{path}"

    monkeypatch.setattr(documents, "create_signed_upload", fake_sign)
    monkeypatch.setattr("utils.indra_ocr_client.warm_up", lambda: None)

    res = client.post("/api/v1/documents/upload-url",
                      json={"project_id": project["id"], "filename": "physics.pdf", "size": 150 * MB})
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["parts"]) == 4
    assert [p["path"] for p in body["parts"]] == [f"{body['path']}.part{i}" for i in range(4)]
    assert all(p["token"] == f"token-for-{p['path']}" for p in body["parts"])
    assert body["part_bytes"] * 4 >= 150 * MB

    small = client.post("/api/v1/documents/upload-url",
                        json={"project_id": project["id"], "filename": "notes.pdf", "size": 10 * MB}).json()
    assert small["parts"] == [{"path": small["path"], "token": small["token"]}]   # unchanged for old apps

    too_big = client.post("/api/v1/documents/upload-url",
                          json={"project_id": project["id"], "filename": "huge.pdf", "size": 151 * MB})
    assert too_big.status_code == 413


class FakeHttp:
    """Stands in for httpx.AsyncClient against Supabase Storage."""

    objects = {}
    deleted = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url, headers=None):
        key = url.split("/storage/v1/object/uploads/", 1)[1]
        data = self.objects.get(key)

        class Resp:
            status_code = 200 if data is not None else 404

            async def aiter_bytes(self, n):
                for i in range(0, len(data), n):
                    yield data[i:i + n]

        class Ctx:
            async def __aenter__(self_inner):
                return Resp()

            async def __aexit__(self_inner, *a):
                return False

        return Ctx()

    async def request(self, method, url, headers=None, json=None):
        FakeHttp.deleted.extend(json["prefixes"])


def test_upload_from_storage_joins_parts_in_order(setup, monkeypatch):
    client, pg, storage, project = setup
    import httpx

    path = f"{USER}/{project['id']}/3000-big.pdf"
    chunks = [os.urandom(1000), os.urandom(1000), os.urandom(1000)]
    FakeHttp.objects = {f"{path}.part{i}": c for i, c in enumerate(chunks)}
    FakeHttp.deleted = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeHttp)
    queued = {}

    async def fake_queue(**kw):
        with open(kw["temp_path"], "rb") as f:
            queued["data"] = f.read()
        os.unlink(kw["temp_path"])

    monkeypatch.setattr("services.jobs.queue_document_processing", fake_queue)
    res = client.post("/api/v1/documents/upload-from-storage",
                      json={"project_id": project["id"], "storage_path": path, "filename": "big.pdf", "parts": 3})
    assert res.status_code == 200, res.text
    assert queued["data"] == b"".join(chunks)
    assert FakeHttp.deleted == [f"{path}.part{i}" for i in range(3)]

    missing = client.post("/api/v1/documents/upload-from-storage",
                          json={"project_id": project["id"], "storage_path": path, "filename": "other.pdf", "parts": 4})
    assert missing.status_code == 404
    bad = client.post("/api/v1/documents/upload-from-storage",
                      json={"project_id": project["id"], "storage_path": path, "filename": "x.pdf", "parts": 0})
    assert bad.status_code == 400


# ---------------------------------------------------------------- the stored original

def _scanned_pdf(path, pages=2):
    """A PDF of full-page 300 dpi grey images plus a text line, like a scanned book."""
    fitz = pytest.importorskip("fitz")
    w, h = 2480, 3508
    image = fitz.Pixmap(fitz.csGRAY, w, h, os.urandom(w * h), False).tobytes("png")
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=image)
        page.insert_text((72, 72), "Photosynthesis makes glucose from light.", fontsize=12)
    doc.save(path)


@pytest.mark.skipif(not shutil.which("gs"), reason="Ghostscript not installed")
def test_compress_pdf_shrinks_a_scan_and_keeps_text(tmp_path):
    from services.pdf_compress import compress_pdf
    import fitz

    src = str(tmp_path / "scan.pdf")
    _scanned_pdf(src)
    out = asyncio.run(compress_pdf(src, target_bytes=1))
    assert out and os.path.getsize(out) < os.path.getsize(src) * 0.9
    with fitz.open(out) as doc:
        assert doc.page_count == 2
        assert "Photosynthesis" in doc[0].get_text()
    os.unlink(out)


def test_compress_pdf_without_ghostscript_returns_none(tmp_path, monkeypatch):
    from services import pdf_compress

    monkeypatch.setattr(pdf_compress.shutil, "which", lambda _: None)
    path, _ = _file(tmp_path, 100)
    assert asyncio.run(pdf_compress.compress_pdf(path, 10)) is None


def test_big_original_is_compressed_then_stored_in_parts(setup, small_parts, monkeypatch, tmp_path):
    client, pg, storage, project = setup
    from services import pdf_compress
    from services.document_service import document_service

    doc = pg.table("documents").insert({"project_id": project["id"], "filename": "big.pdf",
                                        "file_type": "application/pdf", "upload_status": "processing"}).execute().data[0]
    src, _ = _file(tmp_path, 5000)
    smaller = str(tmp_path / "smaller.pdf")
    with open(smaller, "wb") as f:
        f.write(os.urandom(1800))   # still over one object: stored in parts
    monkeypatch.setattr(settings, "PDF_COMPRESS_ABOVE_BYTES", 1000)

    async def fake_compress(path, target):
        assert path == src and target == split_storage.SINGLE_MAX
        return smaller

    monkeypatch.setattr(pdf_compress, "compress_pdf", fake_compress)
    from db.client import get_supabase_client
    monkeypatch.setattr(document_service, "client", get_supabase_client())
    ref = asyncio.run(document_service._save_original_to_storage(doc["id"], project["id"], "big.pdf", src))
    assert ref == f"documents/{project['id']}/{doc['id']}.pdf#parts=5"
    assert pg.table("documents").select("file_url").eq("id", doc["id"]).execute().data[0]["file_url"] == ref
    assert sum(len(v) for v in storage.files.values()) == 1800
    assert not os.path.exists(smaller)          # the compressed temp copy is cleaned up
    assert os.path.exists(src)                  # the pipeline still owns the original


def test_reader_gets_signed_links_for_every_part(setup, monkeypatch):
    client, pg, storage, project = setup
    doc = pg.table("documents").insert({
        "project_id": project["id"], "filename": "big.pdf", "file_type": "application/pdf",
        "upload_status": "completed", "file_url": f"documents/{project['id']}/d.pdf#parts=3",
    }).execute().data[0]

    from tests.test_upload_jobs import FakeBucket
    monkeypatch.setattr(FakeBucket, "create_signed_url",
                        lambda self, path, expiry: {"signedURL": f"https://s/{self.name}/{path}"}, raising=False)
    res = client.get(f"/api/v1/documents/{project['id']}/{doc['id']}/url")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "pdf" and "url" not in body   # older apps fall back to the text view
    assert body["parts"] == [f"https://s/documents/{project['id']}/d.pdf.part{i}" for i in range(3)]


def test_retry_rebuilds_a_parted_original(setup, small_parts, monkeypatch):
    client, pg, storage, project = setup
    data = os.urandom(2000)
    for i in range(5):
        storage.files[f"documents/{project['id']}/d.pdf.part{i}"] = data[i * 400:(i + 1) * 400]
    doc = pg.table("documents").insert({
        "project_id": project["id"], "filename": "big.pdf", "file_type": "application/pdf",
        "upload_status": "failed", "file_url": f"documents/{project['id']}/d.pdf#parts=5",
    }).execute().data[0]
    queued = {}

    async def fake_queue(**kw):
        with open(kw["temp_path"], "rb") as f:
            queued["data"] = f.read()
        os.unlink(kw["temp_path"])

    monkeypatch.setattr("services.jobs.queue_document_processing", fake_queue)
    res = client.post(f"/api/v1/documents/{project['id']}/{doc['id']}/retry")
    assert res.status_code == 200, res.text
    assert queued["data"] == data
