"""pgvector store: write, dense and keyword search, filters, reuse, copy, delete."""

import asyncio
import uuid

import pytest

from config.settings import settings
from db.client import SupabaseClient
from services import vector_store as vs
from services.chunking import Chunk


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return self.pg.table(name)


def run(c):
    return asyncio.run(c)


def vec(*hot):
    """A unit-ish vector with weight on the given dimensions."""
    v = [0.0] * settings.EMBEDDING_DIMENSION
    for i in hot:
        v[i] = 1.0
    return v


def chunk(i, text, page=None, heading=""):
    return Chunk(index=i, page=page, heading=heading, content=text, embed_text=text, content_hash=f"h-{text}")


@pytest.fixture
def book(pg_client, monkeypatch):
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(pg_client))
    user = str(uuid.uuid4())
    proj = pg_client.table("projects").insert({"user_id": user, "name": "Bio"}).execute().data[0]
    d1 = pg_client.table("documents").insert({"project_id": proj["id"], "filename": "a.pdf"}).execute().data[0]
    d2 = pg_client.table("documents").insert({"project_id": proj["id"], "filename": "b.pdf"}).execute().data[0]
    run(vs.replace_document_chunks(proj["id"], d1["id"], [
        chunk(0, "Photosynthesis happens in the chloroplast of leaves.", page=4, heading="Ch 1 › Plants"),
        chunk(1, "Respiration releases energy from glucose in mitochondria.", page=5),
        chunk(2, "The heart pumps blood through arteries and veins.", page=9),
    ], [vec(0), vec(1), vec(2)]))
    run(vs.replace_document_chunks(proj["id"], d2["id"], [
        chunk(0, "Chlorophyll absorbs red and blue light for photosynthesis.", page=1),
    ], [vec(0, 3)]))
    return proj["id"], d1["id"], d2["id"]


def test_dense_search_orders_by_similarity_and_keeps_pages(book):
    pid, d1, d2 = book
    hits = run(vs.search_dense(pid, vec(0), k=3))
    assert hits[0].content.startswith("Photosynthesis happens") and hits[0].page == 4
    assert hits[0].heading == "Ch 1 › Plants" and hits[0].score > 0.99
    assert hits[1].document_id == d2


def test_document_filter(book):
    pid, d1, d2 = book
    hits = run(vs.search_dense(pid, vec(0), k=5, document_ids=[d2]))
    assert {h.document_id for h in hits} == {d2}


def test_keyword_search_uses_stems_and_any_word(book):
    pid, d1, d2 = book
    hits = run(vs.search_keyword(pid, "how do leaves photosynthesise in chloroplasts?", k=5))
    assert hits and "chloroplast" in hits[0].content
    assert run(vs.search_keyword(pid, "   ", k=5)) == []
    assert run(vs.search_keyword(pid, "volcano tectonic", k=5)) == []


def test_other_books_never_leak(book, pg_client):
    pid, d1, d2 = book
    other = pg_client.table("projects").insert({"user_id": str(uuid.uuid4()), "name": "X"}).execute().data[0]
    assert run(vs.search_dense(other["id"], vec(0), k=5)) == []
    assert run(vs.search_keyword(other["id"], "photosynthesis", k=5)) == []


def test_existing_vectors_reused_by_hash(book):
    found = run(vs.existing_vectors(["h-The heart pumps blood through arteries and veins.", "h-missing"]))
    assert list(found) == ["h-The heart pumps blood through arteries and veins."]
    assert found["h-The heart pumps blood through arteries and veins."].startswith("[")


def test_copy_document_reuses_vectors(book, pg_client):
    pid, d1, d2 = book
    other = pg_client.table("projects").insert({"user_id": str(uuid.uuid4()), "name": "Copy"}).execute().data[0]
    doc = pg_client.table("documents").insert({"project_id": other["id"], "filename": "a.pdf"}).execute().data[0]
    assert run(vs.copy_document(d1, other["id"], doc["id"])) == 3
    hits = run(vs.search_dense(other["id"], vec(1), k=1))
    assert hits[0].content.startswith("Respiration") and hits[0].document_id == doc["id"] and hits[0].page == 5
    assert run(vs.count(doc["id"])) == 3


def test_replace_delete_neighbours_first_chunks(book):
    pid, d1, d2 = book
    assert [h.chunk_index for h in run(vs.neighbours(d1, [2, 0]))] == [0, 2]
    assert run(vs.first_chunks(d1, 2))[0].startswith("Photosynthesis")
    run(vs.replace_document_chunks(pid, d1, [chunk(0, "Only one passage now.")], [vec(5)]))
    assert run(vs.count(d1)) == 1
    run(vs.delete_document(d1))
    assert run(vs.count(d1)) == 0
