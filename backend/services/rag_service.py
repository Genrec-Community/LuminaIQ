"""
Answering a student's question from their book (no LangChain).

    question + recent chat -> retrieval (rewrite, hybrid search, rerank, merge)
    -> one prompt: fixed instructions, the student's profile and level rules,
       numbered excerpts with pages, the chat, the question
    -> the small model (or the big one for Deep answers on paid plans)

The fixed instructions come first so OpenAI-compatible providers can cache that
prefix. Sources keep the page each excerpt came from, so a citation can open the
book there. The stream protocol is unchanged: answer text, then
"\\n\\n__SOURCES__:<json>".
"""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional

from config.settings import settings
from db.client import async_db, get_supabase_client
from services import retrieval, vector_store
from services.llm_service import llm_service
from utils.logger import logger

HISTORY_TURNS = 12

BASE_PROMPT = """You are Lumina IQ, a study companion that turns a student's own books into clear understanding.

You are given numbered excerpts from the student's documents. Cite them inline right after the fact
they support, written exactly like [1](1) or [2](2) for excerpt 1 or 2. Never invent a citation, never
cite an excerpt for something it doesn't say, and don't add a list of sources at the end.

How to answer:
- Use clear Markdown: short paragraphs, headings or bullet points when they help, bold for key terms.
- Explain the reasoning, not just the facts: make it obvious how the excerpts answer the question.
- If the excerpts answer only part of the question, answer that part and say what is missing.
- Write maths in LaTeX: $...$ inline and $$...$$ on its own line.
- If the student asks about themselves (their name, goal or exam), answer only from the STUDENT
  PROFILE, never from the book. If no profile is set, suggest filling it in under Settings > Profile.
- If a YOUR PERSONA section is present, use that name and personality; accuracy and citations come first.
- When the excerpts don't cover the question, follow the OUTSIDE THE BOOK rule below (without one,
  say "I couldn't find this in your book.")."""


def _history_messages(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [{"role": m["role"], "content": m["content"]}
            for m in (history or [])[-HISTORY_TURNS:]
            if m.get("role") in ("user", "assistant") and m.get("content")]


def _excerpts_block(passages: List[retrieval.Passage], grounded: bool) -> str:
    if not passages:
        return "EXCERPTS FROM THE STUDENT'S DOCUMENTS:\n(none found for this question)"
    lines = ["EXCERPTS FROM THE STUDENT'S DOCUMENTS:"]
    if not grounded:
        lines.append("(These are only loosely related to the question: use them only where they truly apply.)")
    for i, p in enumerate(passages, 1):
        where = f", page {p.page}" if p.page else ""
        head = f" — {p.heading}" if p.heading else ""
        lines.append(f"\n[Excerpt {i}{where}{head}]\n{p.text[:4000]}")
    return "\n".join(lines)


def build_messages(question: str, passages: List[retrieval.Passage], grounded: bool,
                   history: List[Dict[str, str]], user_context: Optional[str],
                   system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
    """Fixed instructions first (cacheable), then profile/level rules, excerpts, chat and the question."""
    system = system_prompt or BASE_PROMPT
    parts = [system]
    parts.append(f"=== STUDENT PROFILE ===\n{user_context}" if user_context else "=== STUDENT PROFILE ===\n(not set yet)")
    parts.append(_excerpts_block(passages, grounded))
    return [{"role": "system", "content": "\n\n".join(parts)}, *_history_messages(history),
            {"role": "user", "content": question}]


class RAGService:
    def __init__(self):
        self.client = get_supabase_client()

    @staticmethod
    def _friendly_error(e: Exception) -> str:
        """Plain-language message for chat errors (raw details go to the logs)."""
        text = str(e)
        lower = text.lower()
        if "402" in text or "credit limit" in lower or "insufficient_quota" in lower:
            return "The AI service has run out of credit, so I can't answer right now. Please let the site admin know."
        if "401" in text or "invalid api key" in lower or "invalid_api_key" in lower or "incorrect api key" in lower:
            return "The AI service rejected its API key, so I can't answer right now. Please let the site admin know."
        if "connection" in lower or "timed out" in lower or "timeout" in lower:
            return "I couldn't reach the AI service. Please try again in a moment."
        if "429" in text or "rate limit" in lower:
            return "The AI service is busy right now. Please try again in a moment."
        return "Something went wrong while answering. Please try again."

    async def _doc_names(self, doc_ids: List[str]) -> Dict[str, str]:
        ids = sorted({d for d in doc_ids if d})
        if not ids:
            return {}
        try:
            res = await async_db(lambda: self.client.table("documents").select("id, filename").in_("id", ids).execute())
            return {r["id"]: r["filename"] for r in res.data or []}
        except Exception as e:
            logger.debug(f"Document names unavailable: {e}")
            return {}

    async def _sources(self, passages: List[retrieval.Passage]) -> List[Dict[str, Any]]:
        names = await self._doc_names([p.document_id for p in passages])
        return [{"doc_id": p.document_id or "", "doc_name": names.get(p.document_id, "Unknown"),
                 "chunk_text": p.text, "page": p.page} for p in passages]

    async def _retrieve(self, project_id: str, question: str, history, selected_documents, deep: bool):
        """Passages for the question; while a book has no index yet, keyword search over its stored text."""
        result = await retrieval.retrieve(project_id, question, history=history, document_ids=selected_documents,
                                          top_n=settings.RAG_TOP_PASSAGES, deep=deep)
        if result.passages:
            return result.passages, result.grounded
        if await retrieval._project_has_chunks(project_id):
            return [], False      # indexed, but nothing relevant: outside-book territory
        stored = await retrieval._stored_text_passages(project_id, result.query, settings.RAG_TOP_PASSAGES,
                                                       selected_documents)
        passages = [retrieval.Passage(text=s["text"], document_id=s["document_id"], page=None) for s in stored]
        return passages, bool(passages)

    async def get_answer(self, project_id: str, question: str, selected_documents: Optional[List[str]] = None,
                         chat_history: Optional[List[Dict[str, str]]] = None, system_prompt: Optional[str] = None,
                         user_context: Optional[str] = None, deep: bool = False) -> Dict[str, Any]:
        try:
            passages, grounded = await self._retrieve(project_id, question, chat_history, selected_documents, deep)
            messages = build_messages(question, passages, grounded, chat_history or [], user_context, system_prompt)
            answer = await llm_service.chat_completion(messages, temperature=0.2, max_tokens=4000, deep=deep)
            return {"answer": answer, "sources": await self._sources(passages)}
        except Exception as e:
            logger.error(f"[RAG] answer failed: {e}")
            raise Exception(self._friendly_error(e))

    async def get_answer_stream(self, project_id: str, question: str,
                                selected_documents: Optional[List[str]] = None,
                                chat_history: Optional[List[Dict[str, str]]] = None,
                                system_prompt: Optional[str] = None, user_context: Optional[str] = None,
                                deep: bool = False) -> AsyncIterator[str]:
        try:
            passages, grounded = await self._retrieve(project_id, question, chat_history, selected_documents, deep)
            sources = await self._sources(passages)
            messages = build_messages(question, passages, grounded, chat_history or [], user_context, system_prompt)
        except Exception as e:
            logger.error(f"[RAG] retrieval failed: {e}")
            yield f"Error: {self._friendly_error(e)}"
            return

        started = False
        for attempt in range(2):
            try:
                async for piece in llm_service.chat_completion_stream(messages, temperature=0.2, max_tokens=4000,
                                                                      deep=deep):
                    started = True
                    yield piece
                break
            except Exception as e:
                logger.error(f"[RAG] stream failed (attempt {attempt + 1}): {e}")
                if started or attempt == 1:
                    yield f"\n\nError: {self._friendly_error(e)}" if started else f"Error: {self._friendly_error(e)}"
                    break
                await asyncio.sleep(1.5)
        yield f"\n\n__SOURCES__:{json.dumps(sources)}"

    async def generate_summary(self, project_id: str, selected_documents: Optional[List[str]] = None) -> Dict[str, Any]:
        """A short overview of what the book is about (stored for the whole project)."""
        if not selected_documents:
            try:
                cached = await async_db(lambda: self.client.table("project_summaries").select("summary")
                                        .eq("project_id", project_id).execute())
                if cached.data:
                    return {"answer": cached.data[0]["summary"], "sources": []}
            except Exception as e:
                logger.warning(f"Cached summary unavailable: {e}")

        query = (self.client.table("documents").select("id, project_id, filename, text_storage_path")
                 .eq("project_id", project_id).eq("upload_status", "completed"))
        if selected_documents:
            query = query.in_("id", selected_documents)
        documents = (await async_db(lambda: query.execute())).data or []
        if not documents:
            return {"answer": "No documents available.", "sources": []}

        intro, sources = "", []
        for doc in documents:
            chunks = await vector_store.first_chunks(doc["id"], 3)
            if not chunks:
                from services.document_service import document_service
                text = await document_service.load_stored_text(doc)
                if text:
                    chunks = [text[i:i + 1500] for i in range(0, min(len(text), 4500), 1500)]
            if chunks:
                intro += f"--- Document: {doc['filename']} ---\n" + "\n".join(chunks) + "\n\n"
                sources.append({"doc_id": doc["id"], "doc_name": doc["filename"], "chunk_text": chunks[0][:100] + "..."})
        if not intro:
            return {"answer": "Unable to read content.", "sources": []}

        prompt = ("Here are the openings of the documents in a student's study project:\n\n"
                  f"{intro[:10000]}\n\nWrite a concise, engaging summary of what these documents are about, "
                  "highlighting the main topics and themes. Use Markdown, no HTML.")
        summary = await llm_service.chat_completion([{"role": "user", "content": prompt}], temperature=0.3,
                                                    max_tokens=2000, task="generate")
        summary = summary.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        if not selected_documents:
            try:
                await async_db(lambda: self.client.table("project_summaries").upsert(
                    {"project_id": project_id, "summary": summary}, on_conflict="project_id").execute())
            except Exception as e:
                logger.error(f"Failed to store summary: {e}")
        return {"answer": summary, "sources": sources}


rag_service = RAGService()
