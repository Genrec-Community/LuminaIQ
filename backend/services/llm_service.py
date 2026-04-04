"""
LLM Service — Azure OpenAI

Uses langchain_openai.AzureChatOpenAI, driven by:
    AZURE_OPENAI_API_KEY       (from .env)
    AZURE_OPENAI_ENDPOINT      (from .env)
    AZURE_OPENAI_DEPLOYMENT    (from .env, e.g. "gpt4o")
    AZURE_OPENAI_API_VERSION   (from .env, e.g. "2024-12-01-preview")

Falls back to legacy OpenAI-compatible client if Azure vars are not set.
"""

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from config.settings import settings
from typing import List, Dict
from utils.logger import logger


def _build_client(temperature: float = 0.7, max_tokens: int = 4000):
    """
    Returns either an AzureChatOpenAI or ChatOpenAI client
    depending on which credentials are populated in settings.
    """
    if settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY:
        # Use ChatOpenAI compatible client because the provided endpoint/key 
        # behaves like a standard OpenAI proxy (GitHub Models / Azure Global)
        from langchain_openai import ChatOpenAI
        logger.debug(
            f"Using Azure/GitHub Proxy ChatOpenAI provider (deployment={settings.AZURE_OPENAI_DEPLOYMENT})"
        )
        return ChatOpenAI(
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            openai_api_base=settings.AZURE_OPENAI_ENDPOINT,
            openai_api_key=settings.AZURE_OPENAI_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # Fallback: legacy OpenAI-compatible (Groq etc.)
    from langchain_openai import ChatOpenAI
    logger.warning("Azure credentials missing, falling back to basic ChatOpenAI client")
    return ChatOpenAI(
        model=settings.LLM_MODEL or "gpt-3.5-turbo",
        openai_api_key=settings.LLM_API_KEY,
        openai_api_base=settings.LLM_BASE_URL or None,
        temperature=temperature,
        max_tokens=max_tokens,
    )


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
        using_azure = bool(settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY)
        if using_azure:
            logger.info(
                f"Initialized Azure OpenAI service (deployment={settings.AZURE_OPENAI_DEPLOYMENT})"
            )
        else:
            logger.warning("Azure OpenAI not configured, utilizing fallback LLM.")

    def _get_client(self, temperature: float = 0.7, max_tokens: int = 4000):
        return _build_client(temperature=temperature, max_tokens=max_tokens)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """Generate chat completion (non-streaming).
        
        Automatically retries with a larger token budget if the model returns
        an empty or near-empty response — this handles reasoning models that
        consume their entire token allowance on internal chain-of-thought.
        """
        # Cap absolute minimum — never go below 2000 or things will always be empty
        max_tokens = max(max_tokens, 2000)
        try:
            client = self._get_client(temperature=temperature, max_tokens=max_tokens)
            lc_messages = _convert_messages(messages)
            logger.info(
                f"Sending {len(lc_messages)} messages "
                f"(temp={temperature}, max_tokens={max_tokens})"
            )
            response = await client.ainvoke(lc_messages)
            answer = response.content if getattr(response, "content", None) else ""

            # Detect token starvation: finish_reason='length' + empty content
            metadata = getattr(response, "response_metadata", {})
            finish_reason = metadata.get("finish_reason", "")
            reasoning_tokens = (
                metadata.get("token_usage", {})
                .get("completion_tokens_details", {})
                .get("reasoning_tokens", 0)
            )

            if not answer or len(answer) < self.EMPTY_RESPONSE_MIN_CHARS:
                logger.warning(
                    f"Empty/short response detected: finish_reason={finish_reason!r}, "
                    f"reasoning_tokens={reasoning_tokens}. "
                    f"Metadata: {metadata}"
                )
                # If finish_reason is 'length', the model ran out of token budget.
                # Retry once with a much larger cap to give the model breathing room.
                if finish_reason == "length" or reasoning_tokens > max_tokens * 0.5:
                    # Cap retry max_tokens to prevent "Request too large" 413 error (e.g. Groq 8000 TPM)
                    retry_tokens = min(max_tokens * self.RETRY_TOKEN_MULTIPLIER, 6000)
                    logger.warning(
                        f"Retrying completion with {retry_tokens} tokens "
                        f"(token starvation detected, reasoning used {reasoning_tokens} tokens)"
                    )
                    retry_client = self._get_client(temperature=temperature, max_tokens=retry_tokens)
                    retry_response = await retry_client.ainvoke(lc_messages)
                    answer = retry_response.content if getattr(retry_response, "content", None) else ""
                    logger.info(f"Retry completion successful: {len(answer)} chars generated")

            if not answer:
                logger.error(f"Response remains empty after retry. Metadata: {metadata}")
            else:
                logger.info(f"Completion generated {len(answer)} chars")
            return answer
        except Exception as e:
            logger.error(f"Chat completion error occurred: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            logger.error(f"Streaming completion error occurred: {e}")
            raise


llm_service = LLMService()
