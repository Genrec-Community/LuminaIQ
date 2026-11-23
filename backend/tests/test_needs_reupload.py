"""Ready books with no passages are flagged for re-upload (real Postgres)."""
import asyncio
import uuid
from types import SimpleNamespace

from db.client import SupabaseClient


def test_ready_book_without_passages_is_flagged(pg_client, monkeypatch):
    monkeypatch.setattr(SupabaseClient, "_instance", SimpleNamespace(pg=pg_client))
    from api.v1.endpoints.documents import _ready_without_passages

    pid = pg_client.table("projects").insert({"user_id": str(uuid.uuid4()), "name": "B"}).execute().data[0]["id"]
    docs = pg_client.table("documents").insert([
        {"project_id": pid, "filename": "lost.pdf", "upload_status": "completed"},
        {"project_id": pid, "filename": "ok.pdf", "upload_status": "completed"},
        {"project_id": pid, "filename": "busy.pdf", "upload_status": "processing"},
    ]).execute().data
    lost, ok, busy = (d["id"] for d in docs)
    pg_client.fetch("INSERT INTO chunks (project_id, document_id, chunk_index, content, content_hash)"
                    " VALUES (%s, %s, 0, 'text', 'h')", (pid, ok))
    assert asyncio.run(_ready_without_passages(pid, docs)) == {lost}
