"""Per-feature models (LLM_TASK_MODELS) and the fallback model (FALLBACK_LLM_MODEL)."""
import asyncio

import pytest

from config.settings import settings
from services import llm_service as L


@pytest.fixture(autouse=True)
def _cfg(monkeypatch):
    monkeypatch.setattr(settings, "SMALL_LLM_MODEL", "small-default")
    monkeypatch.setattr(settings, "SMALL_LLM_BASE_URL", "http://x/v1")
    monkeypatch.setattr(settings, "SMALL_LLM_API_KEY", "k")
    monkeypatch.setattr(settings, "BIG_LLM_MODEL", "big-default")
    monkeypatch.setattr(settings, "BIG_LLM_BASE_URL", "http://x/v1")
    monkeypatch.setattr(settings, "BIG_LLM_API_KEY", "k")
    monkeypatch.setattr(settings, "LLM_TASK_MODELS",
                        "chat=chat-m, generate=gen-m, big:deep=deep-m, vision=vis-m")
    monkeypatch.setattr(settings, "FALLBACK_LLM_MODEL", "fb-m")


def test_task_overrides():
    assert L.resolve_model("chat", "free").model == "chat-m"
    assert L.resolve_model("generate", "free").model == "gen-m"
    assert L.resolve_model("memory", "free").model == "small-default"
    # free users never get the big model, even for deep
    assert L.resolve_model("deep", "free").role == "small"
    big = L.resolve_model("deep", "pro")
    assert (big.role, big.model) == ("big", "deep-m")
    assert L.resolve_model("lab", "pro").model == "big-default"


def test_vision_model_named_is_enabled(monkeypatch):
    monkeypatch.setattr(settings, "SMALL_LLM_VISION", False)
    cfg = L.vision_config("free")
    assert cfg and cfg.model == "vis-m"
    monkeypatch.setattr(settings, "LLM_TASK_MODELS", "")
    assert L.vision_config("free") is None


def test_fallback_config():
    fb = L.fallback_for(L.resolve_model("chat", "free"))
    assert fb.model == "fb-m"
    assert L.fallback_for(L.ModelConfig("small", "fb-m", "u", "k", None)) is None


class _Boom(Exception):
    pass


def test_completion_falls_back(monkeypatch):
    used = []

    async def fake(self, cfg, *a, **k):
        used.append(cfg.model)
        if cfg.model == "chat-m":
            raise _Boom("throttled")
        return "ok"

    monkeypatch.setattr(L.LLMService, "_complete", fake)
    svc = L.LLMService.__new__(L.LLMService)
    assert asyncio.run(svc.chat_completion([{"role": "user", "content": "hi"}], task="chat")) == "ok"
    assert used == ["chat-m", "fb-m"]


def test_stream_falls_back_only_before_first_token(monkeypatch):
    async def fails_first(self, cfg, *a, **k):
        if cfg.model == "chat-m":
            raise _Boom("down")
            yield  # pragma: no cover
        yield "from-fb"

    monkeypatch.setattr(L.LLMService, "_stream", fails_first)
    svc = L.LLMService.__new__(L.LLMService)
    async def collect(got):
        async for p in svc.chat_completion_stream([], task="chat"):
            got.append(p)
        return got

    out = asyncio.run(collect([]))
    assert out == ["from-fb"]

    async def fails_midway(self, cfg, *a, **k):
        yield "half"
        raise _Boom("cut")

    monkeypatch.setattr(L.LLMService, "_stream", fails_midway)
    got = []
    with pytest.raises(_Boom):
        asyncio.run(collect(got))
    assert got == ["half"]
