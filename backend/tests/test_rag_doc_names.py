"""Chat sources: filenames for all retrieved passages come from one query."""

import asyncio
from types import SimpleNamespace

from services.rag_service import RAGService


def test_doc_names_one_query_for_many_passages():
    calls = []

    class Table:
        def select(self, *_):
            return self

        def in_(self, col, ids):
            calls.append(list(ids))
            self.ids = ids
            return self

        def execute(self):
            rows = [{"id": "d1", "filename": "Bio.pdf"}, {"id": "d2", "filename": "Chem.pdf"}]
            return SimpleNamespace(data=[r for r in rows if r["id"] in self.ids])

    svc = RAGService.__new__(RAGService)
    svc.client = SimpleNamespace(table=lambda name: Table())
    names = asyncio.run(svc._doc_names(["d1", "d2", "d1", "d2", None]))
    assert names == {"d1": "Bio.pdf", "d2": "Chem.pdf"}
    assert calls == [["d1", "d2"]]
