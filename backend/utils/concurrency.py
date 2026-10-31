"""Per-process limits on heavy work, so one worker doesn't run out of memory or hammer the AI provider."""
import asyncio
from typing import Optional

from config.settings import settings

_docs: Optional[asyncio.Semaphore] = None
_llm: Optional[asyncio.Semaphore] = None


def doc_semaphore() -> asyncio.Semaphore:
    """Documents being read and indexed at once in this process."""
    global _docs
    if _docs is None:
        _docs = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_DOCUMENT_UPLOADS))
    return _docs


def llm_semaphore() -> asyncio.Semaphore:
    """Background LLM calls (topics, knowledge graph) at once in this process."""
    global _llm
    if _llm is None:
        _llm = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_LLM))
    return _llm
