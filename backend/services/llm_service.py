"""
Chat models over any OpenAI-compatible API (OpenAI, Azure's /openai/v1, Groq,
Together, OpenRouter, vLLM, Ollama, Inception ...), with two configurations:

    SMALL_LLM_*  most work, and every request from free users
    BIG_LLM_*    Deep answers, Visual Lab builds and photo questions for paid plans

resolve_model() is the one place that decides which runs. Token usage is
recorded per user (services/usage_service.py).
"""
import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional

import openai

from config.settings import settings
from utils.logger import logger



# Some open models (gpt-oss on Bedrock, DeepSeek, Qwen) put their hidden reasoning
# inside the answer text as <reasoning>...</reasoning> or <think>...</think>.
_REASONING_TAGS = (("<reasoning>", "</reasoning>"), ("<think>", "</think>"))


def strip_reasoning(text: str) -> str:
    """Remove reasoning blocks from a complete answer (an unclosed block is dropped to the end)."""
    if not text or "<" not in text:
        return text
    f = _ReasoningFilter()
    return (f.feed(text) + f.flush()).strip() if any(o in text for o, _ in _REASONING_TAGS) else text


class _ReasoningFilter:
    """Streaming filter that drops reasoning blocks even when a tag is split across chunks."""

    def __init__(self):
        self.buf = ""
        self.close_tag = None  # set while inside a block
        self.started = False

    @staticmethod
    def _partial_suffix(text: str, tags) -> int:
        """Length of the longest suffix of text that is the start of one of the tags."""
        best = 0
        for tag in tags:
            for n in range(min(len(tag) - 1, len(text)), 0, -1):
                if text.endswith(tag[:n]):
                    best = max(best, n)
                    break
        return best

    def _emit(self, out: list, text: str):
        if not self.started:
            text = text.lstrip()
            if text:
                self.started = True
        if text:
            out.append(text)

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        out = []
        while self.buf:
            if self.close_tag:
                i = self.buf.find(self.close_tag)
                if i >= 0:
                    self.buf = self.buf[i + len(self.close_tag):]
                    self.close_tag = None
                    continue
                keep = self._partial_suffix(self.buf, [self.close_tag])
                self.buf = self.buf[-keep:] if keep else ""
                break
            hits = [(self.buf.find(o), o, c) for o, c in _REASONING_TAGS if o in self.buf]
            if hits:
                i, open_tag, close_tag = min(hits)
                self._emit(out, self.buf[:i])
                self.buf = self.buf[i + len(open_tag):]
                self.close_tag = close_tag
                continue
            keep = self._partial_suffix(self.buf, [o for o, _ in _REASONING_TAGS])
            self._emit(out, self.buf[:-keep] if keep else self.buf)
            self.buf = self.buf[-keep:] if keep else ""
            break
        return "".join(out)

    def flush(self) -> str:
        rest, self.buf = ("" if self.close_tag else self.buf), ""
        out = []
        self._emit(out, rest)
        return "".join(out)


# --------------------------------------------------------------------------- models

@dataclass(frozen=True)
class ModelConfig:
    role: str                # "small" | "big"
    model: str
    base_url: Optional[str]
    api_key: str
    reasoning_effort: str = ""


def small_config() -> ModelConfig:
    # The old LLM_* settings still work, so existing deployments keep running
    return ModelConfig(
        role="small",
        model=settings.SMALL_LLM_MODEL or settings.LLM_MODEL or "gpt-4.1-mini",
        base_url=settings.SMALL_LLM_BASE_URL or settings.LLM_BASE_URL or None,
        api_key=settings.SMALL_LLM_API_KEY or settings.LLM_API_KEY or "",
        reasoning_effort=settings.SMALL_LLM_REASONING_EFFORT or settings.LLM_REASONING_EFFORT,
    )


def big_config() -> Optional[ModelConfig]:
    if not settings.BIG_LLM_MODEL:
        return None
    small = small_config()
    return ModelConfig(
        role="big",
        model=settings.BIG_LLM_MODEL,
        base_url=settings.BIG_LLM_BASE_URL or small.base_url,
        api_key=settings.BIG_LLM_API_KEY or small.api_key,
        reasoning_effort=settings.BIG_LLM_REASONING_EFFORT,
    )


# Tasks that deserve the big model (for paying users)
BIG_TASKS = {"deep", "lab", "vision"}


def _request_plan() -> str:
    try:
        from services.usage_service import current_plan
        return current_plan.get() or ""
    except Exception:
        return ""


def resolve_model(task: str = "chat", plan: Optional[str] = None) -> ModelConfig:
    """
    The model for one call. Free users (and calls with no signed-in user, e.g.
    background jobs) always get the small model; paying users get the big one
    for Deep answers, Visual Lab builds and photo questions, when it's configured.
    """
    plan = (plan if plan is not None else _request_plan()) or "free"
    big = big_config()
    if task in BIG_TASKS and plan != "free" and big:
        return big
    return small_config()


_clients: Dict[tuple, openai.AsyncOpenAI] = {}


def client_for(cfg: ModelConfig) -> openai.AsyncOpenAI:
    key = (cfg.base_url, cfg.api_key)
    if key not in _clients:
        _clients[key] = openai.AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key or "not-set",
                                           timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=2)
    return _clients[key]


async def _record_usage(model: str, usage) -> None:
    if not usage:
        return
    try:
        from services.usage_service import usage as usage_service
        await usage_service.record_tokens(model, getattr(usage, "prompt_tokens", 0) or 0,
                                          getattr(usage, "completion_tokens", 0) or 0)
    except Exception as e:
        logger.debug(f"[LLM] token usage not recorded: {e}")


async def _create(client: openai.AsyncOpenAI, kwargs: dict):
    """
    chat.completions.create, adapting to provider quirks: reasoning models that
    refuse a temperature, providers that want max_completion_tokens, and ones
    that don't accept stream_options.
    """
    for _ in range(3):
        try:
            return await client.chat.completions.create(**kwargs)
        except openai.BadRequestError as e:
            msg = str(e).lower()
            if "temperature" in msg and "temperature" in kwargs:
                kwargs.pop("temperature")
            elif "max_tokens" in msg and "max_tokens" in kwargs:
                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            elif "stream_options" in msg and "stream_options" in kwargs:
                kwargs.pop("stream_options")
            else:
                raise
    return await client.chat.completions.create(**kwargs)


def _task(light: bool, deep: bool, task: Optional[str]) -> str:
    return task or ("deep" if deep else "generate" if light else "chat")


class LLMService:
    # A reply shorter than this, cut off by the length limit, is retried with more room
    EMPTY_RESPONSE_MIN_CHARS = 20

    def __init__(self):
        cfg = small_config()
        big = big_config()
        logger.info(f"[LLM] small={cfg.model} @ {cfg.base_url or 'api.openai.com'}"
                    + (f" | big={big.model} @ {big.base_url or 'api.openai.com'}" if big else " | big=not set"))

    def _kwargs(self, cfg: ModelConfig, messages, temperature, max_tokens) -> dict:
        kwargs = {"model": cfg.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if cfg.reasoning_effort:
            kwargs["extra_body"] = {"reasoning_effort": cfg.reasoning_effort}
        return kwargs

    async def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7,
                              max_tokens: int = 4000, light: bool = False, deep: bool = False,
                              task: Optional[str] = None) -> str:
        """One reply. deep=True asks for the big model (paid plans); light is kept for old callers."""
        cfg = resolve_model(_task(light, deep, task))
        client = client_for(cfg)
        kwargs = self._kwargs(cfg, messages, temperature, max_tokens)
        resp = await _create(client, kwargs)
        await _record_usage(cfg.model, getattr(resp, "usage", None))
        choice = resp.choices[0] if resp.choices else None
        text = strip_reasoning((choice.message.content if choice else "") or "")
        if len(text) < self.EMPTY_RESPONSE_MIN_CHARS and choice and choice.finish_reason == "length":
            # Reasoning models can spend the whole budget thinking: give them more room once
            budget_key = "max_completion_tokens" if "max_completion_tokens" in kwargs else "max_tokens"
            kwargs[budget_key] = min(max_tokens * 3, 16000)
            logger.warning(f"[LLM] reply cut off at {max_tokens} tokens; retrying with {kwargs[budget_key]}")
            resp = await _create(client, kwargs)
            await _record_usage(cfg.model, getattr(resp, "usage", None))
            text = strip_reasoning((resp.choices[0].message.content if resp.choices else "") or "")
        return text

    async def chat_completion_stream(self, messages: List[Dict[str, str]], temperature: float = 0.7,
                                     max_tokens: int = 4000, deep: bool = False,
                                     task: Optional[str] = None) -> AsyncIterator[str]:
        """The reply as it's generated (reasoning blocks removed)."""
        cfg = resolve_model(_task(False, deep, task))
        client = client_for(cfg)
        kwargs = self._kwargs(cfg, messages, temperature, max_tokens)
        kwargs.update(stream=True, stream_options={"include_usage": True})
        stream = await _create(client, kwargs)
        filt = _ReasoningFilter()
        async for chunk in stream:
            if getattr(chunk, "usage", None):
                await _record_usage(cfg.model, chunk.usage)
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            out = filt.feed(delta) if delta else ""
            if out:
                yield out
        rest = filt.flush()
        if rest:
            yield rest


llm_service = LLMService()
