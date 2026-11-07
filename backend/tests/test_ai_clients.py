"""OpenAI-compatible chat, embeddings and rerank clients, against a fake HTTP server."""

import asyncio
import json

import httpx
import openai
import pytest

from config.settings import settings
from services import embedding_service as emb_mod
from services import llm_service as llm_mod
from services import reranker


def run(c):
    return asyncio.run(c)


def fake_openai(handler):
    return openai.AsyncOpenAI(api_key="k", base_url="http://fake/v1", max_retries=0,
                              http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def completion(text, finish="stop", usage=(10, 5)):
    return {"id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1], "total_tokens": sum(usage)}}


@pytest.fixture
def models(monkeypatch):
    monkeypatch.setattr(settings, "SMALL_LLM_MODEL", "small-1")
    monkeypatch.setattr(settings, "BIG_LLM_MODEL", "big-1")
    monkeypatch.setattr(settings, "BIG_LLM_BASE_URL", "")
    monkeypatch.setattr(settings, "LLM_DEEP_MODEL", "")


# ---------------------------------------------------------------- routing

def test_free_users_always_get_small(models):
    assert llm_mod.resolve_model("deep", plan="free").model == "small-1"
    assert llm_mod.resolve_model("lab", plan="").model == "small-1"


def test_paid_users_get_big_for_big_tasks_only(models):
    assert llm_mod.resolve_model("deep", plan="topper").model == "big-1"
    assert llm_mod.resolve_model("vision", plan="scholar").model == "big-1"
    assert llm_mod.resolve_model("chat", plan="topper").model == "small-1"
    assert llm_mod.resolve_model("generate", plan="institution").model == "small-1"


def test_big_falls_back_to_small_when_unset(models, monkeypatch):
    monkeypatch.setattr(settings, "BIG_LLM_MODEL", "")
    assert llm_mod.resolve_model("deep", plan="topper").model == "small-1"


def test_old_deep_settings_still_give_the_big_model(models, monkeypatch):
    monkeypatch.setattr(settings, "BIG_LLM_MODEL", "")
    monkeypatch.setattr(settings, "LLM_DEEP_MODEL", "deep-legacy")
    monkeypatch.setattr(settings, "LLM_DEEP_BASE_URL", "http://deep/v1")
    cfg = llm_mod.resolve_model("deep", plan="topper")
    assert (cfg.model, cfg.base_url) == ("deep-legacy", "http://deep/v1")
    assert llm_mod.resolve_model("deep", plan="free").model == "small-1"


def test_old_llm_settings_still_work(monkeypatch):
    monkeypatch.setattr(settings, "SMALL_LLM_MODEL", "")
    monkeypatch.setattr(settings, "SMALL_LLM_BASE_URL", "")
    monkeypatch.setattr(settings, "LLM_MODEL", "legacy-model")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://legacy/v1")
    cfg = llm_mod.small_config()
    assert cfg.model == "legacy-model" and cfg.base_url == "https://legacy/v1"


# ---------------------------------------------------------------- chat

def test_chat_completion_strips_reasoning_and_records_usage(models, monkeypatch):
    seen, recorded = {}, []

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json=completion("<think>secret</think>Photosynthesis makes food from light."))

    monkeypatch.setattr(llm_mod, "client_for", lambda cfg: fake_openai(handler))

    async def rec(model, i, o):
        recorded.append((model, i, o))

    from services.usage_service import usage
    monkeypatch.setattr(usage, "record_tokens", rec)
    out = run(llm_mod.llm_service.chat_completion([{"role": "user", "content": "hi"}], temperature=0.2, max_tokens=100))
    assert out == "Photosynthesis makes food from light."
    assert seen["model"] == "small-1" and seen["temperature"] == 0.2 and seen["max_tokens"] == 100
    assert recorded == [("small-1", 10, 5)]


def test_temperature_rejected_is_retried_without_it(models, monkeypatch):
    calls = []

    def handler(req):
        body = json.loads(req.content)
        calls.append(body)
        if "temperature" in body:
            return httpx.Response(400, json={"error": {"message": "Unsupported value: 'temperature'", "type": "invalid_request_error"}})
        return httpx.Response(200, json=completion("ok, answered without temperature"))

    monkeypatch.setattr(llm_mod, "client_for", lambda cfg: fake_openai(handler))
    out = run(llm_mod.llm_service.chat_completion([{"role": "user", "content": "q"}]))
    assert out == "ok, answered without temperature" and len(calls) == 2


def test_cut_off_reply_is_retried_with_more_room(models, monkeypatch):
    budgets = []

    def handler(req):
        body = json.loads(req.content)
        budgets.append(body["max_tokens"])
        if len(budgets) == 1:
            return httpx.Response(200, json=completion("", finish="length"))
        return httpx.Response(200, json=completion("A full answer after more room."))

    monkeypatch.setattr(llm_mod, "client_for", lambda cfg: fake_openai(handler))
    out = run(llm_mod.llm_service.chat_completion([{"role": "user", "content": "q"}], max_tokens=500))
    assert out == "A full answer after more room." and budgets == [500, 1500]


def test_stream_yields_text_without_reasoning(models, monkeypatch):
    def handler(req):
        events = []
        for piece in ["<thi", "nk>hidden</think>Hel", "lo ", "world"]:
            events.append({"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "m",
                           "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]})
        body = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    monkeypatch.setattr(llm_mod, "client_for", lambda cfg: fake_openai(handler))

    async def collect():
        return "".join([c async for c in llm_mod.llm_service.chat_completion_stream([{"role": "user", "content": "q"}])])

    assert run(collect()) == "Hello world"


# ---------------------------------------------------------------- embeddings

def test_embeddings_batch_in_order_and_check_dimension(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 3)
    monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 2)
    batches = []

    def handler(req):
        body = json.loads(req.content)
        batches.append(body["input"])
        data = [{"object": "embedding", "index": i, "embedding": [float(len(t)), 0.0, 1.0]}
                for i, t in reversed(list(enumerate(body["input"])))]   # out of order on purpose
        return httpx.Response(200, json={"object": "list", "data": data, "model": "e",
                                         "usage": {"prompt_tokens": 1, "total_tokens": 1}})

    svc = emb_mod.EmbeddingService()
    svc._client = fake_openai(handler)
    vecs = run(svc.generate_embeddings(["a", "bb", "ccc", ""]))
    assert [v[0] for v in vecs] == [1.0, 2.0, 3.0, 1.0]   # empty text sent as " "
    assert batches == [["a", "bb"], ["ccc", " "]]

    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 1536)
    with pytest.raises(ValueError, match="EMBEDDING_DIMENSION"):
        run(svc.generate_embeddings(["x"]))


# ---------------------------------------------------------------- rerank

_RealAsyncClient = httpx.AsyncClient


class FakeHTTP:
    def __init__(self, handler):
        self.handler = handler

    async def __aenter__(self):
        return _RealAsyncClient(transport=httpx.MockTransport(self.handler))

    async def __aexit__(self, *a):
        return False


def test_rerank_off_without_key(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_API_KEY", "")
    assert run(reranker.rerank("q", ["a", "b"], 2)) is None


def test_rerank_orders_by_score(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_API_KEY", "k")

    def handler(req):
        body = json.loads(req.content)
        assert body["query"] == "q" and body["top_n"] == 2
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 0.1},
                                                     {"index": 2, "relevance_score": 0.9},
                                                     {"index": 1, "relevance_score": 0.5}]})

    monkeypatch.setattr(reranker.httpx, "AsyncClient", lambda **kw: FakeHTTP(handler))
    assert run(reranker.rerank("q", ["a", "b", "c"], 2)) == [2, 1]


def test_rerank_failure_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_API_KEY", "k")
    monkeypatch.setattr(reranker.httpx, "AsyncClient",
                        lambda **kw: FakeHTTP(lambda req: httpx.Response(500, json={"error": "down"})))
    assert run(reranker.rerank("q", ["a", "b"], 2)) is None
