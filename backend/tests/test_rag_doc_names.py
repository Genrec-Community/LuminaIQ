"""Chat sources: filenames for retrieved chunks are looked up in one query."""

import asyncio
from types import SimpleNamespace

from services.rag_service import RAGService


class CountingTable:
    calls = 0

    def __init__(self, rows):
        self.rows = rows

    def select(self, *_):
        return self

    def in_(self, col, ids):
        CountingTable.calls += 1
        self.ids = ids
        return self

    def execute(self):
        return SimpleNamespace(data=[r for r in self.rows if r["id"] in self.ids])


def test_doc_names_one_query_for_many_chunks():
    svc = RAGService.__new__(RAGService)
    rows = [{"id": "d1", "filename": "Bio.pdf"}, {"id": "d2", "filename": "Chem.pdf"}]
    svc.client = SimpleNamespace(table=lambda name: CountingTable(rows))
    docs = [SimpleNamespace(metadata={"document_id": d}) for d in ("d1", "d2", "d1", "d2", "d1")]
    docs.append(SimpleNamespace(metadata={"document_id": "d3", "document_name": "Known.pdf"}))
    names = {}
    asyncio.run(svc._fill_doc_names(docs, names))
    assert names == {"d1": "Bio.pdf", "d2": "Chem.pdf"}
    assert CountingTable.calls == 1
    asyncio.run(svc._fill_doc_names(docs, names))   # all known now: no query
    assert CountingTable.calls == 1
