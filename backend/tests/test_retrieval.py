"""Retrieval pipeline: rewrite, hybrid fusion, rerank, neighbour merge, grounding, Deep decomposition."""

import asyncio

import pytest

from services import retrieval as r
from services.vector_store import Hit


def run(c):
    return asyncio.run(c)


def hit(i, text, doc="d1", page=None, score=0.5):
    return Hit(chunk_id=i, document_id=doc, chunk_index=i, page=page, heading="", content=text, score=score)


@pytest.fixture
def fakes(monkeypatch):
    state = {"dense": {}, "keyword": {}, "llm": [], "rewrite": "standalone question", "rerank": None,
             "embed_fail": False, "count": 5, "neighbours": []}

    async def embed(text):
        if state["embed_fail"]:
            raise RuntimeError("embeddings down")
        return [0.1]

    async def dense(project_id, vector, k=30, document_ids=None):
        return state["dense"].get(state.get("current_query"), state["dense"].get("*", []))

    async def keyword(project_id, query, k=30, document_ids=None):
        state["current_query"] = query
        return state["keyword"].get(query, state["keyword"].get("*", []))

    async def llm(messages, **kw):
        state["llm"].append(messages[-1]["content"])
        return state["rewrite"]

    async def rerank(query, docs, top_n):
        return state["rerank"]

    async def neighbours(document_id, idx):
        return [h for h in state["neighbours"] if h.chunk_index in set(idx)]

    async def project_chunk_count(project_id):
        return state["count"]

    monkeypatch.setattr(r.embedding_service, "generate_embedding", embed)
    monkeypatch.setattr(r.vector_store, "search_dense", dense)
    monkeypatch.setattr(r.vector_store, "search_keyword", keyword)
    monkeypatch.setattr(r.vector_store, "neighbours", neighbours)
    monkeypatch.setattr(r, "_project_has_chunks", project_chunk_count)
    monkeypatch.setattr(r.llm_service, "chat_completion", llm)
    monkeypatch.setattr(r.reranker, "rerank", rerank)
    return state


def test_first_question_is_not_rewritten(fakes):
    fakes["keyword"]["*"] = [hit(1, "Leaves make food.")]
    res = run(r.retrieve("p", "What is photosynthesis?", history=[]))
    assert fakes["llm"] == [] and res.query == "What is photosynthesis?"


def test_followup_is_rewritten(fakes):
    fakes["rewrite"] = "How does chlorophyll absorb light in photosynthesis?"
    fakes["keyword"]["How does chlorophyll absorb light in photosynthesis?"] = [hit(1, "Chlorophyll absorbs red light.")]
    history = [{"role": "user", "content": "What is photosynthesis?"},
               {"role": "assistant", "content": "Plants make food using light and chlorophyll."}]
    res = run(r.retrieve("p", "explain that part about light again", history=history))
    assert res.query == "How does chlorophyll absorb light in photosynthesis?"
    assert "explain that part about light again" in fakes["llm"][0] and "chlorophyll" in fakes["llm"][0]
    assert res.passages[0].text == "Chlorophyll absorbs red light."


def test_rewrite_failure_uses_the_question(fakes, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("llm down")
    monkeypatch.setattr(r.llm_service, "chat_completion", boom)
    fakes["keyword"]["*"] = [hit(1, "x")]
    res = run(r.retrieve("p", "and then?", history=[{"role": "user", "content": "q"}]))
    assert res.query == "and then?"


def test_hybrid_fusion_prefers_passages_found_both_ways(fakes):
    a, b, c = hit(1, "A only dense", score=0.9), hit(10, "B in both", score=0.8), hit(20, "C only keyword")
    fakes["dense"]["*"] = [a, b]
    fakes["keyword"]["*"] = [c, b]
    res = run(r.retrieve("p", "q", top_n=3))
    assert res.passages[0].text == "B in both"
    assert {p.text for p in res.passages} == {"A only dense", "B in both", "C only keyword"}


def test_rerank_order_is_used_when_available(fakes):
    fakes["dense"]["*"] = [hit(1, "first", score=0.9), hit(5, "second", score=0.8), hit(9, "third", score=0.7)]
    fakes["rerank"] = [2, 0]
    res = run(r.retrieve("p", "q", top_n=2))
    assert [p.text for p in res.passages] == ["third", "first"]


def test_rerank_failure_keeps_fused_order(fakes):
    fakes["dense"]["*"] = [hit(1, "first", score=0.9), hit(5, "second", score=0.8)]
    fakes["rerank"] = None
    res = run(r.retrieve("p", "q", top_n=2))
    assert [p.text for p in res.passages] == ["first", "second"]


def test_adjacent_chunks_merge_into_one_passage(fakes):
    fakes["dense"]["*"] = [hit(4, "Part one of the idea.", page=7, score=0.9),
                           hit(5, "Part two of the idea.", page=8, score=0.85),
                           hit(20, "Unrelated far away.", page=30, score=0.5)]
    res = run(r.retrieve("p", "q", top_n=3))
    merged = res.passages[0]
    assert merged.text == "Part one of the idea.\n\nPart two of the idea." and merged.page == 7
    assert len(res.passages) == 2


def test_overlapping_text_is_not_repeated_when_merging(fakes):
    fakes["dense"]["*"] = [hit(1, "Alpha beta. Gamma delta.", score=0.9), hit(2, "Gamma delta. Epsilon.", score=0.8)]
    res = run(r.retrieve("p", "q", top_n=2))
    assert res.passages[0].text == "Alpha beta. Gamma delta. Epsilon."


def test_grounding(fakes, monkeypatch):
    monkeypatch.setattr(r.settings, "RAG_MIN_SIMILARITY", 0.4)
    fakes["dense"]["*"] = [hit(1, "weak match", score=0.25), hit(9, "unrelated", score=0.05)]
    weak = run(r.retrieve("p", "q"))
    assert weak.grounded is False and [p.text for p in weak.passages] == ["weak match"]   # unrelated dropped
    fakes["dense"]["*"] = [hit(1, "strong match", score=0.7)]
    assert run(r.retrieve("p", "q")).grounded is True
    fakes["dense"]["*"] = []
    fakes["keyword"]["*"] = []
    res = run(r.retrieve("p", "q"))
    assert res.grounded is False and res.passages == []


def test_keyword_search_still_works_when_embeddings_fail(fakes):
    fakes["embed_fail"] = True
    fakes["keyword"]["*"] = [hit(1, "found by words")]
    res = run(r.retrieve("p", "q"))
    assert [p.text for p in res.passages] == ["found by words"] and res.grounded is True


def test_deep_mode_searches_each_sub_question(fakes):
    fakes["rewrite"] = "1. What is mitosis?\n2. What is meiosis?\n3. How do they differ?"
    for q, t in [("What is mitosis?", "Mitosis makes two cells."), ("What is meiosis?", "Meiosis makes four cells.")]:
        fakes["keyword"][q] = [hit(len(t), t, doc=q)]
    res = run(r.retrieve("p", "Compare mitosis and meiosis", deep=True, top_n=6))
    texts = {p.text for p in res.passages}
    assert {"Mitosis makes two cells.", "Meiosis makes four cells."} <= texts
    assert res.sub_queries == ["What is mitosis?", "What is meiosis?", "How do they differ?"]


def test_search_passages_shape_for_study_tools(fakes):
    fakes["dense"]["*"] = [hit(3, "Cells divide.", page=2, score=0.8)]
    out = run(r.search_passages("p", ["cell division"], per_query=5))
    assert out[0]["text"] == "Cells divide." and out[0]["page"] == 2 and out[0]["document_id"] == "d1"
    assert "score" in out[0] and "chunk_id" in out[0]


def test_neighbours_from_different_sections_stay_separate(fakes):
    def h(i, text, heading, page, score):
        return Hit(chunk_id=i, document_id="d1", chunk_index=i, page=page, heading=heading, content=text, score=score)
    fakes["dense"]["*"] = [h(1, "Respiration releases energy.", "Ch 2 Respiration", 3, 0.9),
                           h(0, "Photosynthesis makes food.", "Ch 1 Plants", 1, 0.4),
                           h(2, "The heart pumps blood.", "Ch 3 Circulation", 4, 0.3)]
    res = run(r.retrieve("p", "respiration energy", top_n=3))
    assert res.passages[0].text == "Respiration releases energy." and res.passages[0].page == 3
    assert len(res.passages) == 3


def test_merge_stops_after_a_few_chunks(fakes):
    fakes["dense"]["*"] = [hit(i, f"Part {i}.", score=0.9 - i / 100) for i in range(6)]
    res = run(r.retrieve("p", "q", top_n=6))
    assert max(len(p.chunk_ids) for p in res.passages) <= r.MAX_MERGE
