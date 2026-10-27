import functools
"""
LLM Service — Azure OpenAI

Uses langchain_openai.AzureChatOpenAI, driven by:
    AZURE_OPENAI_API_KEY       (from .env)
    AZURE_OPENAI_ENDPOINT      (from .env)
    AZURE_OPENAI_DEPLOYMENT    (from .env, e.g. "gpt4o")
    AZURE_OPENAI_API_VERSION   (from .env, e.g. "2024-12-01-preview")

Falls back to an OpenAI-compatible client (LLM_BASE_URL / LLM_API_KEY /
LLM_MODEL, e.g. Inception Mercury) if Azure vars are not set, or always when
LLM_PROVIDER=openai.
"""

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from config.settings import settings
from typing import List, Dict
from utils.logger import logger


def _use_azure() -> bool:
    """Decide the chat provider from LLM_PROVIDER (auto | azure | openai)."""
    provider = (settings.LLM_PROVIDER or "auto").strip().lower()
    azure_ready = bool(
        settings.AZURE_OPENAI_ENDPOINT
        and (settings.AZURE_OPENAI_API_KEY or settings.MODEL_API_KEY)
    )
    if provider == "openai":
        return False
    if provider == "azure":
        return True
    return azure_ready


class _TokenRecorder:
    """LangChain callback that records each call's token usage for the current user."""

    def __new__(cls):
        from langchain_core.callbacks import AsyncCallbackHandler

        class Recorder(AsyncCallbackHandler):
            async def on_llm_end(self, response, **kwargs):
                try:
                    from services.usage_service import usage

                    usage_in = usage_out = 0
                    model = ""
                    for gens in response.generations or []:
                        for g in gens:
                            meta = getattr(getattr(g, "message", None), "usage_metadata", None) or {}
                            usage_in += meta.get("input_tokens", 0) or 0
                            usage_out += meta.get("output_tokens", 0) or 0
                            rm = getattr(getattr(g, "message", None), "response_metadata", None) or {}
                            model = model or rm.get("model_name", "")
                    if not (usage_in or usage_out):
                        tu = (response.llm_output or {}).get("token_usage") or {}
                        usage_in = tu.get("prompt_tokens", 0) or 0
                        usage_out = tu.get("completion_tokens", 0) or 0
                        model = model or (response.llm_output or {}).get("model_name", "")
                    await usage.record_tokens(model, usage_in, usage_out)
                except Exception as e:
                    logger.debug(f"Token recording failed: {e}")

        return Recorder()


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


@functools.lru_cache(maxsize=None)
def _reasoning_free(base_cls):
    """A chat model class whose answers (normal and streamed) never contain reasoning blocks."""
    from langchain_core.messages import AIMessageChunk
    from langchain_core.outputs import ChatGenerationChunk

    class ReasoningFree(base_cls):
        def _create_chat_result(self, response, generation_info=None):
            result = super()._create_chat_result(response, generation_info)
            for g in result.generations:
                if isinstance(g.message.content, str):
                    cleaned = strip_reasoning(g.message.content)
                    g.message.content = cleaned
                    g.text = cleaned
            return result

        def _filter_chunk(self, chunk, f):
            c = chunk.message.content
            if isinstance(c, str) and c:
                cleaned = f.feed(c)
                chunk.message.content = cleaned
                chunk.text = cleaned
            return chunk

        def _stream(self, *args, **kwargs):
            f = _ReasoningFilter()
            for chunk in super()._stream(*args, **kwargs):
                yield self._filter_chunk(chunk, f)
            rest = f.flush()
            if rest:
                yield ChatGenerationChunk(message=AIMessageChunk(content=rest))

        async def _astream(self, *args, **kwargs):
            f = _ReasoningFilter()
            async for chunk in super()._astream(*args, **kwargs):
                yield self._filter_chunk(chunk, f)
            rest = f.flush()
            if rest:
                yield ChatGenerationChunk(message=AIMessageChunk(content=rest))

    ReasoningFree.__name__ = base_cls.__name__
    return ReasoningFree


_tier_cache: Dict[str, Dict[str, str]] = {}


def tier_models() -> Dict[str, str]:
    """LLM_TIER_MODELS ("free=a,scholar=b,...") as {plan: model}."""
    raw = settings.LLM_TIER_MODELS or ""
    if raw not in _tier_cache:
        pairs = {}
        for part in raw.split(","):
            plan, _, model = part.partition("=")
            if plan.strip() and model.strip():
                pairs[plan.strip().lower()] = model.strip()
        _tier_cache[raw] = pairs
    return _tier_cache[raw]


def _request_plan() -> str:
    try:
        from services.usage_service import current_plan
        return current_plan.get() or ""
    except Exception:
        return ""


def resolve_model(light: bool = False, deep: bool = False, plan: str = None) -> str:
    """
    The model (Azure: deployment) for a call. Deep answers use the Deep model;
    otherwise the signed-in user's plan picks its model from LLM_TIER_MODELS;
    otherwise bulk work uses LLM_LIGHT_MODEL and the rest LLM_MODEL.
    """
    azure = _use_azure()
    default = (settings.AZURE_OPENAI_DEPLOYMENT if azure else settings.LLM_MODEL) or "gpt-4.1-mini"
    if deep and settings.LLM_DEEP_MODEL and not azure:
        return settings.LLM_DEEP_MODEL
    tier = tier_models().get((plan if plan is not None else _request_plan()) or "")
    if tier:
        return tier
    if light and settings.LLM_LIGHT_MODEL and not azure:
        return settings.LLM_LIGHT_MODEL
    return default


def _build_client(
    temperature: float = 0.7,
    max_tokens: int = 4000,
    light: bool = False,
    deep: bool = False,
    model: str = None,
):
    """
    Returns either:
    - AzureChatOpenAI (preferred)
    - ChatOpenAI fallback for legacy providers
    """
    model = model or resolve_model(light=light, deep=deep)

    # Resolve API Key: support unified MODEL_API_KEY or explicit keys
    azure_api_key = settings.AZURE_OPENAI_API_KEY or settings.MODEL_API_KEY

    # Azure OpenAI
    if _use_azure():
        from langchain_openai import AzureChatOpenAI

        logger.debug(f"[LLMService] Using Azure OpenAI | deployment={model}")

        kwargs = {
            "azure_endpoint": settings.AZURE_OPENAI_ENDPOINT,
            "api_key": azure_api_key,
            "azure_deployment": model,
            "api_version": settings.AZURE_OPENAI_API_VERSION,
            "max_tokens": max_tokens,
            "callbacks": [_TokenRecorder()],
            "stream_usage": True,
        }

        # Reasoning models (gpt-5 family except -chat, o1/o3/o4) only accept the default temperature
        name = model.lower()
        if "o1" in name or name.startswith(("o3", "o4")) or ("gpt-5" in name and "chat" not in name):
            kwargs["temperature"] = 1.0
        else:
            kwargs["temperature"] = temperature

        return _reasoning_free(AzureChatOpenAI)(**kwargs)

    # Fallback OpenAI-compatible providers
    from langchain_openai import ChatOpenAI

    fallback_api_key = (
        settings.LLM_API_KEY
        or settings.MODEL_API_KEY
        or settings.AZURE_OPENAI_API_KEY
    )
    base_url = settings.LLM_BASE_URL or None
    if deep and settings.LLM_DEEP_MODEL and model == settings.LLM_DEEP_MODEL:
        base_url = settings.LLM_DEEP_BASE_URL or base_url
        fallback_api_key = settings.LLM_DEEP_API_KEY or fallback_api_key

    logger.debug(
        f"[LLMService] Using OpenAI-compatible provider | model={model} "
        f"| base={base_url or 'api.openai.com'}"
    )
    kwargs = {
        "model": model,
        "openai_api_key": fallback_api_key,
        "openai_api_base": base_url,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "callbacks": [_TokenRecorder()],
        "stream_usage": True,  # token counts on streamed answers too
    }
    if settings.LLM_REASONING_EFFORT:
        # Sent as a raw body field so it works with any OpenAI-compatible provider
        kwargs["extra_body"] = {"reasoning_effort": settings.LLM_REASONING_EFFORT}
    return _reasoning_free(ChatOpenAI)(**kwargs)

def _convert_messages(messages: List[Dict[str, str]]):
    """Convert dict messages to LangChain message objects."""
    converted = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            converted.append(HumanMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
        elif role == "system":
            converted.append(SystemMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted


class LLMService:
    # Minimum tokens we require in the actual response.
    # If the model returns fewer chars than this, we suspect token starvation.
    EMPTY_RESPONSE_MIN_CHARS = 20
    # Multiplier applied when retrying after an empty/short response
    RETRY_TOKEN_MULTIPLIER = 3

    def __init__(self):
        if _use_azure():
            logger.info(
                f"[LLMService] Initialized with Azure OpenAI | "
                f"deployment={settings.AZURE_OPENAI_DEPLOYMENT}"
            )
        else:
            logger.info(
                f"[LLMService] Initialized with OpenAI-compatible provider | "
                f"model={settings.LLM_MODEL} | base={settings.LLM_BASE_URL or 'api.openai.com'}"
                + (f" | reasoning_effort={settings.LLM_REASONING_EFFORT}" if settings.LLM_REASONING_EFFORT else "")
            )

    def _get_client(self, temperature: float = 0.7, max_tokens: int = 4000,
                    light: bool = False, deep: bool = False, model: str = None):
        return _build_client(temperature=temperature, max_tokens=max_tokens, light=light, deep=deep, model=model)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        light: bool = False,
        deep: bool = False,
    ) -> str:
        """Generate chat completion (non-streaming).

        light=True uses LLM_LIGHT_MODEL when configured (bulk structured tasks);
        deep=True uses LLM_DEEP_MODEL (Deep answers, Visual Lab).
        
        Automatically retries with a larger token budget if the model returns
        an empty or near-empty response — this handles reasoning models that
        consume their entire token allowance on internal chain-of-thought.
        """
        # Cap absolute minimum — never go below 2000 or things will always be empty
        max_tokens = max(max_tokens, 2000)
        try:
            client = self._get_client(temperature=temperature, max_tokens=max_tokens, light=light, deep=deep)
            lc_messages = _convert_messages(messages)
            logger.info(
                f"[LLMService] Sending {len(lc_messages)} messages "
                f"(temp={temperature}, max_tokens={max_tokens})"
            )
            response = await client.ainvoke(lc_messages)
            answer = response.content if getattr(response, "content", None) else ""

            # Detect token starvation: finish_reason='length' + empty content
            metadata = getattr(response, "response_metadata", None) or {}
            finish_reason = metadata.get("finish_reason", "")
            # Non-OpenAI providers often send null for these nested fields
            reasoning_tokens = (
                ((metadata.get("token_usage") or {})
                 .get("completion_tokens_details") or {})
                .get("reasoning_tokens") or 0
            )

            if not answer or len(answer) < self.EMPTY_RESPONSE_MIN_CHARS:
                logger.warning(
                    f"[LLMService] Empty/short response — finish_reason={finish_reason!r}, "
                    f"reasoning_tokens={reasoning_tokens}. "
                    f"Metadata: {metadata}"
                )
                # If finish_reason is 'length', the model ran out of token budget.
                # Retry once with a much larger cap to give the model breathing room.
                if finish_reason == "length" or reasoning_tokens > max_tokens * 0.5:
                    # Cap retry max_tokens to prevent "Request too large" 413 error (e.g. Groq 8000 TPM)
                    retry_tokens = min(max_tokens * self.RETRY_TOKEN_MULTIPLIER, 6000)
                    logger.warning(
                        f"[LLMService] Retrying with {retry_tokens} tokens "
                        f"(token starvation detected — reasoning used {reasoning_tokens} tokens)"
                    )
                    retry_client = self._get_client(temperature=temperature, max_tokens=retry_tokens, light=light, deep=deep)
                    retry_response = await retry_client.ainvoke(lc_messages)
                    answer = retry_response.content if getattr(retry_response, "content", None) else ""
                    logger.info(f"[LLMService] Retry completion: {len(answer)} chars")

            if not answer:
                logger.error(f"[LLMService] Still empty after retry. Metadata: {metadata}")
            else:
                logger.info(f"[LLMService] Completion: {len(answer)} chars")
            return answer
        except Exception as e:
            logger.error(f"[LLMService] chat_completion error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ):
        """Generate streaming chat completion."""
        max_tokens = max(max_tokens, 2000)
        try:
            client = self._get_client(temperature=temperature, max_tokens=max_tokens)
            lc_messages = _convert_messages(messages)
            async for chunk in client.astream(lc_messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error(f"[LLMService] streaming error: {e}")
            raise


llm_service = LLMService()
