"""
Turn a document's text into searchable passages: chunk, embed what's new, store.

Passages whose exact text was embedded before (the same book uploaded by another
student, a re-index) reuse the stored vector, so they cost nothing to index.
"""
import asyncio
from typing import Awaitable, Callable, List, Optional

from config.settings import settings
from services import vector_store
from services.chunking import Chunk, chunk_document
from services.embedding_service import embedding_service
from utils.logger import logger

Progress = Optional[Callable[[int, str], Awaitable[None]]]


async def make_chunks(text: str, title: str) -> List[Chunk]:
    """Chunking is CPU work: run it off the event loop."""
    return await asyncio.to_thread(
        chunk_document, text, title, settings.CHUNK_TOKENS, settings.CHUNK_OVERLAP_TOKENS, settings.EMBEDDING_MODEL)


async def index_chunks(project_id: str, document_id: str, chunks: List[Chunk], on_progress: Progress = None) -> int:
    """Embed the chunks (reusing known vectors) and store them for the document. Returns the passage count."""
    if not chunks:
        return 0
    known = await vector_store.existing_vectors(c.content_hash for c in chunks)
    todo = [c for c in chunks if c.content_hash not in known]
    vectors = dict(known)
    if todo:
        step = max(1, settings.EMBEDDING_BATCH_SIZE) * max(1, settings.MAX_GLOBAL_EMBEDDINGS)
        for start in range(0, len(todo), step):
            part = todo[start:start + step]
            for c, v in zip(part, await embedding_service.generate_embeddings([c.embed_text for c in part])):
                vectors[c.content_hash] = v
            if on_progress:
                done = min(len(todo), start + step)
                await on_progress(int(done * 100 / len(todo)), f"Indexed {done}/{len(todo)} passages")
    logger.info(f"[Indexing] {document_id}: {len(chunks)} passages ({len(chunks) - len(todo)} reused, {len(todo)} embedded)")
    return await vector_store.replace_document_chunks(
        project_id, document_id, chunks, [vectors[c.content_hash] for c in chunks])


async def index_text(project_id: str, document_id: str, title: str, text: str, on_progress: Progress = None) -> int:
    return await index_chunks(project_id, document_id, await make_chunks(text, title), on_progress)
