"""LlamaIndex RAG over the repository's existing Qdrant payload schema."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from llama_index.core import PromptTemplate
from llama_index.core.response_synthesizers import (
    ResponseMode,
    get_response_synthesizer,
)
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from config.settings import settings
from db.client import async_db, get_supabase_client
from services.embedding_service import embedding_service
from services.llm_service import llm_service
from services.qdrant_service import qdrant_service
from utils.logger import logger

_sleep = asyncio.sleep


DEFAULT_RAG_PROMPT = """You are Lumina IQ, an educational intelligence system.
Answer from the supplied document excerpts. Explain connections clearly and use
Markdown where it improves readability. Every excerpt starts with [Source n];
cite its facts inline as [n](n), so [Source 1] maps to [1](1). Do not invent
facts outside the context. If the context is relevant but incomplete, explain
the limitation. If it is entirely irrelevant, say: "I couldn't find the answer
in the provided documents."
"""


async def retry_with_backoff(func, max_retries=3, base_delay=1.0, max_delay=8.0):
    last_error = None
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as error:
            last_error = error
            message = str(error).lower()
            retryable = any(
                marker in message
                for marker in (
                    "429",
                    "503",
                    "529",
                    "rate limit",
                    "too many requests",
                    "overloaded",
                    "timeout",
                    "connection",
                    "unavailable",
                )
            )
            if not retryable or attempt == max_retries - 1:
                raise
            await _sleep(min(base_delay * (2**attempt), max_delay))
    raise last_error


class ExistingQdrantRetriever(BaseRetriever):
    """Expose existing LuminaIQ Qdrant points as LlamaIndex nodes."""

    def __init__(
        self,
        collection_name: str,
        selected_documents: Optional[List[str]] = None,
        top_k: int = 5,
        embedding_provider=embedding_service,
        vector_store=qdrant_service,
    ):
        super().__init__()
        self.collection_name = collection_name
        self.selected_documents = selected_documents or []
        self.top_k = top_k
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        raise RuntimeError("ExistingQdrantRetriever must be used asynchronously")

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        query_vector = await self.embedding_provider.generate_embedding(
            query_bundle.query_str
        )
        filters = (
            {"document_ids": self.selected_documents}
            if self.selected_documents
            else None
        )
        results = await self.vector_store.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=self.top_k,
            filter_conditions=filters,
        )

        nodes = []
        populated_results = [result for result in results if result.get("text", "")]
        for source_number, result in enumerate(populated_results, start=1):
            text = result["text"]
            node = TextNode(
                id_=str(result.get("id", "")),
                text=f"[Source {source_number}] {text}",
                metadata={
                    "source_number": source_number,
                    "document_id": result.get("document_id", ""),
                    "document_name": result.get("document_name") or "Unknown",
                    "chunk_id": result.get("chunk_id"),
                    "page": result.get("page"),
                },
                excluded_embed_metadata_keys=[
                    "document_id",
                    "document_name",
                    "chunk_id",
                    "page",
                    "source_number",
                ],
            )
            nodes.append(NodeWithScore(node=node, score=result.get("score")))
        return nodes


def _escape_prompt_value(value: str) -> str:
    return value.replace("{", "{{").replace("}", "}}")


def _format_history(history: List[Dict[str, str]]) -> str:
    recent = history[-settings.RAG_HISTORY_MESSAGES :]
    lines = []
    for message in recent:
        role = "Student" if message.get("role") == "user" else "Tutor"
        lines.append(f"{role}: {message.get('content', '')}")
    return "\n".join(lines) or "No previous conversation."


def _build_prompt(
    system_prompt: Optional[str],
    user_context: Optional[str],
    chat_history: List[Dict[str, str]],
) -> PromptTemplate:
    profile = user_context or "No student profile has been configured."
    instructions = system_prompt or DEFAULT_RAG_PROMPT
    history = _format_history(chat_history)
    template = f"""=== STUDENT PROFILE ===
{_escape_prompt_value(profile)}

=== INSTRUCTIONS ===
{_escape_prompt_value(instructions)}

=== RECENT CONVERSATION ===
{_escape_prompt_value(history)}

=== DOCUMENT EXCERPTS ===
{{context_str}}

Question: {{query_str}}
Answer:"""
    return PromptTemplate(template)


def _sources(nodes: List[NodeWithScore]) -> List[Dict[str, Any]]:
    sources = []
    for node in nodes:
        content = node.get_content()
        prefix = f"[Source {node.metadata.get('source_number')}] "
        if content.startswith(prefix):
            content = content[len(prefix) :]
        sources.append(
            {
                "doc_id": node.metadata.get("document_id", ""),
                "doc_name": node.metadata.get("document_name", "Unknown"),
                "chunk_text": content,
                "page": node.metadata.get("page"),
                "score": node.score,
            }
        )
    return sources


def _friendly_error(error: Exception) -> str:
    message = str(error)
    lowered = message.lower()
    if "not found: collection" in lowered or "doesn't exist" in lowered:
        return "Document chunks are still processing or failed to upload. Please try again shortly."
    if "connection" in lowered or "timeout" in lowered:
        return "Failed to connect to the AI service. Please try again shortly."
    return message


class RAGService:
    def __init__(self, client=None, llm=None):
        self.client = client or get_supabase_client()
        self.llm = llm or llm_service._get_client(temperature=0.1)

    async def _retrieve(
        self,
        project_id: str,
        question: str,
        selected_documents: Optional[List[str]],
    ) -> List[NodeWithScore]:
        retriever = ExistingQdrantRetriever(
            collection_name=f"project_{project_id}",
            selected_documents=selected_documents,
            top_k=settings.RAG_TOP_K,
        )
        return await retriever.aretrieve(question)

    def _synthesizer(
        self,
        system_prompt: Optional[str],
        user_context: Optional[str],
        chat_history: List[Dict[str, str]],
        streaming: bool,
    ):
        return get_response_synthesizer(
            llm=self.llm,
            simple_template=_build_prompt(system_prompt, user_context, chat_history),
            response_mode=ResponseMode.SIMPLE_SUMMARIZE,
            use_async=True,
            streaming=streaming,
        )

    async def get_answer(
        self,
        project_id: str,
        question: str,
        selected_documents: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        user_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = chat_history or []
        try:
            nodes = await retry_with_backoff(
                lambda: self._retrieve(project_id, question, selected_documents),
                max_retries=2,
                base_delay=0.5,
            )
            if not nodes:
                return {
                    "answer": "I couldn't find the answer in the provided documents.",
                    "sources": [],
                }

            synthesizer = self._synthesizer(
                system_prompt, user_context, history, streaming=False
            )
            response = await retry_with_backoff(
                lambda: synthesizer.asynthesize(question, nodes),
                max_retries=2,
                base_delay=1.0,
            )
            return {"answer": str(response), "sources": _sources(nodes)}
        except Exception as error:
            logger.error(f"LlamaIndex RAG error: {error}")
            raise Exception(_friendly_error(error)) from error

    async def get_answer_stream(
        self,
        project_id: str,
        question: str,
        selected_documents: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        user_context: Optional[str] = None,
    ):
        history = chat_history or []
        nodes = []
        yielded = False
        try:
            nodes = await retry_with_backoff(
                lambda: self._retrieve(project_id, question, selected_documents),
                max_retries=2,
                base_delay=0.5,
            )
            if not nodes:
                yield "I couldn't find the answer in the provided documents."
                yield "\n\n__SOURCES__:[]"
                return

            synthesizer = self._synthesizer(
                system_prompt, user_context, history, streaming=True
            )
            response = await synthesizer.asynthesize(question, nodes)
            async for token in response.async_response_gen():
                if token:
                    yielded = True
                    yield token
            yield f"\n\n__SOURCES__:{json.dumps(_sources(nodes))}"
        except Exception as error:
            logger.error(f"LlamaIndex streaming RAG error: {error}")
            if not yielded:
                try:
                    fallback = await self.get_answer(
                        project_id=project_id,
                        question=question,
                        selected_documents=selected_documents,
                        chat_history=history,
                        system_prompt=system_prompt,
                        user_context=user_context,
                    )
                    yield fallback["answer"]
                    yield f"\n\n__SOURCES__:{json.dumps(fallback['sources'])}"
                    return
                except Exception as fallback_error:
                    logger.error(f"LlamaIndex RAG fallback failed: {fallback_error}")
            yield f"Error: {_friendly_error(error)}"
            yield f"\n\n__SOURCES__:{json.dumps(_sources(nodes))}"

    async def generate_summary(
        self, project_id: str, selected_documents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not selected_documents:
            try:
                cached = await async_db(
                    lambda: self.client.table("project_summaries")
                    .select("summary")
                    .eq("project_id", project_id)
                    .execute()
                )
                if cached.data:
                    return {"answer": cached.data[0]["summary"], "sources": []}
            except Exception as error:
                logger.warning(f"Summary cache read failed: {error}")

        def fetch_documents():
            query = (
                self.client.table("documents")
                .select("id, filename")
                .eq("project_id", project_id)
                .eq("upload_status", "completed")
            )
            if selected_documents:
                query = query.in_("id", selected_documents)
            return query.execute()

        documents = (await async_db(fetch_documents)).data
        if not documents:
            return {"answer": "No documents available.", "sources": []}

        collection_name = f"project_{project_id}"
        chunk_groups = await asyncio.gather(
            *(
                qdrant_service.get_initial_chunks(collection_name, document["id"], 3)
                for document in documents
            )
        )
        sections = []
        sources = []
        for document, chunks in zip(documents, chunk_groups):
            if not chunks:
                continue
            sections.append(
                f"--- Document: {document['filename']} ---\n" + "\n".join(chunks)
            )
            sources.append(
                {
                    "doc_id": document["id"],
                    "doc_name": document["filename"],
                    "chunk_text": chunks[0][:100] + "...",
                }
            )

        if not sections:
            return {"answer": "Unable to read content.", "sources": []}

        summary = await llm_service.chat_completion(
            [
                {
                    "role": "system",
                    "content": "Summarize study documents clearly using Markdown.",
                },
                {
                    "role": "user",
                    "content": "\n\n".join(sections)[:10000]
                    + "\n\nHighlight the main topics and key themes.",
                },
            ],
            temperature=0.1,
        )
        summary = (
            summary.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        )

        if not selected_documents:
            try:
                await async_db(
                    lambda: self.client.table("project_summaries")
                    .upsert(
                        {"project_id": project_id, "summary": summary},
                        on_conflict="project_id",
                    )
                    .execute()
                )
            except Exception as error:
                logger.warning(f"Summary cache write failed: {error}")
        return {"answer": summary, "sources": sources}


rag_service = RAGService()
