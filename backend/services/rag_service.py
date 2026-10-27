from db.client import async_db
from typing import List, Dict, Any, Optional
import asyncio
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service
from services.llm_service import llm_service
from supabase import create_client, Client
from config.settings import settings
from utils.logger import logger

# LangChain Imports
from langchain_qdrant import QdrantVectorStore
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig


# Retry decorator for handling 503 and transient errors
async def retry_with_backoff(func, max_retries=3, base_delay=1.0, max_delay=10.0):
    """Retry async function with exponential backoff"""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()
            # Check if it's a retryable error (503, rate limit, service unavailable)
            if any(
                x in error_str
                for x in [
                    "503",
                    "service unavailable",
                    "rate limit",
                    "overloaded",
                    "529",
                    "too many requests",
                ]
            ):
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        f"Retryable error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
            # Non-retryable error, raise immediately
            raise
    raise last_exception


class RAGService:
    # Strong refs to background tasks so they aren't garbage-collected mid-run
    _background_tasks: set = set()

    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY
        )

        # Chat clients per model: the model depends on the user's plan
        # (LLM_TIER_MODELS) and on Deep mode, see llm_service.resolve_model
        self._clients = {}

    def _llm(self, deep: bool = False):
        """The chat model for this request's plan, or the Deep model for Deep answers."""
        from services.llm_service import resolve_model
        model = resolve_model(deep=deep)
        key = (model, deep)
        if key not in self._clients:
            self._clients[key] = llm_service._get_client(temperature=0.1, deep=deep, model=model)
        return self._clients[key]

    def _get_retrieval_chain(
        self, collection_name: str, selected_documents: Optional[List[str]] = None, system_prompt: Optional[str] = None, user_context: Optional[str] = None,
        deep: bool = False,
    ):
        """Create a RAG chain for a specific collection"""

        # 1. Vector Store & Retriever
        vector_store = qdrant_service.get_vector_store(collection_name)

        # Define search arguments (filters)
        search_kwargs = {"k": 5}
        if selected_documents:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Use 'should' for OR logic - match ANY of the selected documents
            should_conditions = [
                FieldCondition(key="document_id", match=MatchValue(value=doc_id))
                for doc_id in selected_documents
            ]
            qdrant_filter = Filter(should=should_conditions)
            search_kwargs["filter"] = qdrant_filter

        retriever = vector_store.as_retriever(search_kwargs=search_kwargs)

        # 2. Prompt
        # Build identity preamble from user profile
        if user_context:
            identity_block = f"""=== STUDENT PROFILE (HIGHEST PRIORITY) ===
{user_context}

CRITICAL RULE:
- If the student asks ANY question about themselves — "who am I", "what is my name", "what am I studying for", "tell me about myself" — answer ONLY using the STUDENT PROFILE above.
- Do NOT use document content to describe the student. The student is the READER, not the subject.
- If the student asks "who am I" and the profile has their name, greet them by name and describe what you know from their profile.
- If a YOUR PERSONA section is present above, adopt that name and personality for every reply (the rules below still apply).

===================================================

"""
        else:
            identity_block = """=== STUDENT PROFILE ===
No profile information has been set yet.

CRITICAL RULE:
- If the student asks about themselves ("who am I", "what is my name", etc.), tell them:
  "I don't have your personal details yet. Please go to **Settings > Profile** and fill in your name and learning goal — then I'll be able to answer personal questions about you!"
- Do NOT try to infer who the student is from the document content.

===================================================

"""

        base_system_prompt = identity_block + (system_prompt or """You are Lumina IQ, an elite educational intelligence system designed to transform raw study material into clear, structured understanding.

Your objective is NOT just accuracy — it is clarity, usefulness, and insight.

    You are given context extracted from user documents. Each excerpt represents a numbered source:
- First excerpt → Source 1 → cite as [1](1)
- Second excerpt → Source 2 → cite as [2](2)
...and so on.

---

CORE DIRECTIVES:

1. RESPONSE QUALITY
- Deliver answers that are structured, clear, and genuinely helpful.
- Use Markdown formatting:
  - Headings
  - Bullet points
  - Bold for key ideas
- Avoid flat text. Make it readable and intelligent.

---

2. CITATIONS (IMPORTANT BUT NOT PARALYZING)
- Use citation format: [1](1), [2](2)
- Place citations inline next to facts.
- If a statement clearly comes from context → cite it.
- If citation is slightly uncertain → still answer, but prioritize clarity over rigid citation.

DO NOT:
- Use plain numbers
- Use <source 1> or [[1]]
- Add a sources list at the bottom

---

3. INTELLIGENT ANSWERING LOGIC

You must operate in 3 levels:

LEVEL 1 — STRONG MATCH  
If the context clearly contains the answer:
→ Provide a complete, well-explained answer with citations.

LEVEL 2 — PARTIAL MATCH  
If the context is relevant but incomplete:
→ Provide the best possible answer using available information  
→ Clearly mention limitations  
→ Still be helpful and explanatory

LEVEL 3 — NO MATCH  
Only if the context is completely irrelevant:
→ Respond:
"I couldn't find the answer in the provided documents."

⚠️ DO NOT default to Level 3 unless absolutely necessary.

---

4. REASONING (MANDATORY)
- Do not just state facts.
- Explain how the information connects to the question.
- Make the logic obvious to the user.

---

5. ANTI-HALLUCINATION (SMART, NOT PARALYZING)
- Do NOT invent facts outside the context.
- BUT you ARE allowed to:
  - Interpret
  - Summarize
  - Connect ideas logically

---

6. TONE
- Confident
- Clear
- Intelligent
- Slightly authoritative, but not robotic

---

FINAL RULE:

Your job is not to prove correctness.

Your job is to make the user understand.
""")


        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", base_system_prompt + "\n\nUse the following context to answer the user's question:\n{context}"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )

        # 3. Chains
        question_answer_chain = create_stuff_documents_chain(self._llm(deep), prompt)
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)

        return rag_chain

    @staticmethod
    def _friendly_error(e: Exception) -> str:
        """Plain-language message for chat errors (raw details go to the logs)."""
        text = str(e)
        lower = text.lower()
        if "not found: collection" in lower or "doesn't exist" in lower:
            return "Your documents' search index is being rebuilt. Please try again in a few minutes."
        if "402" in text or "credit limit" in lower or "insufficient_quota" in lower:
            return "The AI service has run out of credit, so I can't answer right now. Please let the site admin know."
        if "401" in text or "invalid api key" in lower or "invalid_api_key" in lower:
            return "The AI service rejected its API key, so I can't answer right now. Please let the site admin know."
        if "connection error" in lower or "apiconnectionerror" in lower or "timed out" in lower:
            return "I couldn't reach the AI service. Please try again in a moment."
        return "Something went wrong while answering. Please try again."

    def _trigger_reindex(self, project_id: str):
        """Rebuild missing vectors for this project's documents in the background."""
        from services.document_service import document_service

        async def _run():
            try:
                await document_service.ensure_project_indexed(project_id)
            except Exception as e:
                logger.error(f"Index check failed for project {project_id}: {e}")

        task = asyncio.create_task(_run())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _answer_from_stored_text(
        self,
        project_id: str,
        question: str,
        selected_documents: Optional[List[str]],
        chat_history: List[Dict[str, str]],
        user_context: Optional[str],
        deep: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Answer without the vector index (missing, rebuilding, or the embedding
        provider is down) using passages found in the documents' stored text.
        Returns None when no text is available.
        """
        from services.graph_analytics_service import graph_analytics

        passages, sources = await graph_analytics.keyword_context_from_stored_text(
            project_id,
            question,
            max_passages=6,
            document_ids=selected_documents or None,
            per_passage_sources=True,
            overview_if_empty=True,
        )
        if not passages:
            return None

        context = "\n\n".join(f"[Source {i + 1}]\n{p}" for i, p in enumerate(passages))
        system = (
            (f"=== STUDENT PROFILE ===\n{user_context}\n\n" if user_context else "")
            + "You are a helpful study companion. Answer the student's question using the "
            "excerpts from their documents below. Cite facts inline as [1](1), [2](2) matching "
            "the source numbers. Use clear Markdown. If the excerpts don't cover the question, "
            "say so briefly and give the best answer you can from them.\n\n"
            f"EXCERPTS:\n{context[:9000]}"
        )
        messages = [{"role": "system", "content": system}]
        for m in chat_history[-6:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": question})

        answer = await llm_service.chat_completion(messages, temperature=0.3, max_tokens=1500, deep=deep)
        return {"answer": answer, "sources": sources}

    async def get_answer(
        self,
        project_id: str,
        question: str,
        selected_documents: Optional[List[str]] = None,
        chat_history: List[Dict[str, str]] = [],
        system_prompt: Optional[str] = None,
        user_context: Optional[str] = None,
        deep: bool = False,
    ) -> Dict[str, Any]:
        """Generate answer using RAG pipeline (LangChain) with retry logic"""
        try:
            collection_name = f"project_{project_id}"
            chain = self._get_retrieval_chain(collection_name, selected_documents, system_prompt, user_context, deep=deep)

            # Convert history to LangChain format
            history_messages = []
            for msg in chat_history:
                if msg["role"] == "user":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    history_messages.append(AIMessage(content=msg["content"]))

            # Invoke with retry logic
            async def invoke_chain():
                return await chain.ainvoke(
                    {"input": question, "chat_history": history_messages}
                )

            response = await retry_with_backoff(
                invoke_chain, max_retries=3, base_delay=1.5
            )

            # Nothing retrieved (index empty / rebuilding): use stored text instead
            if "context" in response and not response["context"]:
                self._trigger_reindex(project_id)
                fallback = await self._answer_from_stored_text(
                    project_id, question, selected_documents, chat_history, user_context,
                    deep=deep,
                )
                if fallback:
                    return fallback

            # Process sources from 'context' in response
            sources = []
            if "context" in response:
                logger.debug(f"Retrieved {len(response['context'])} chunks")

                for i, doc in enumerate(response["context"]):
                    # Resolve filename from doc.metadata if available
                    doc_name = doc.metadata.get("document_name", "Unknown")
                    doc_id = doc.metadata.get("document_id", "")

                    # If name missing in metadata, try DB lookup (cached ideally)
                    if doc_name == "Unknown" and doc_id:
                        try:
                            res = (
                                (await async_db(lambda: self.client.table("documents")
                                .select("filename")
                                .eq("id", doc_id)
                                .execute()))
                            )
                            if res.data:
                                doc_name = res.data[0]["filename"]
                        except:
                            pass

                    sources.append(
                        {
                            "doc_id": doc_id,
                            "doc_name": doc_name,
                            "chunk_text": doc.page_content,
                            "page": doc.metadata.get("page"),
                        }
                    )

            return {"answer": response["answer"], "sources": sources}

        except Exception as e:
            logger.error(f"Error in RAG pipeline: {str(e)}")
            
            if "Not found: Collection" in str(e) or "doesn't exist" in str(e):
                self._trigger_reindex(project_id)
            # Search/embeddings/index failed: answer from the stored text instead
            try:
                fallback = await self._answer_from_stored_text(
                    project_id, question, selected_documents, chat_history, user_context,
                    deep=deep,
                )
                if fallback:
                    return fallback
            except Exception as fb_err:
                logger.error(f"Stored-text fallback failed: {fb_err}")

            raise Exception(self._friendly_error(e))

    async def get_answer_stream(
        self,
        project_id: str,
        question: str,
        selected_documents: Optional[List[str]] = None,
        chat_history: List[Dict[str, str]] = [],
        system_prompt: Optional[str] = None,
        user_context: Optional[str] = None,
        deep: bool = False,
    ):
        """Generate answer using RAG pipeline with streaming (LangChain) - Optimized with retry"""
        max_retries = 3
        base_delay = 2.0

        collection_name = f"project_{project_id}"

        # Preload document names in batch to avoid multiple DB calls during streaming
        doc_name_cache = {}
        if selected_documents:
            try:
                res = (
                    (await async_db(lambda: self.client.table("documents")
                    .select("id, filename")
                    .in_("id", selected_documents)
                    .execute()))
                )
                for doc in res.data:
                    doc_name_cache[doc["id"]] = doc["filename"]
            except Exception as cache_err:
                logger.warning(f"Failed to preload doc names: {cache_err}")

        history_messages = []
        for msg in chat_history:
            if msg["role"] == "user":
                history_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                history_messages.append(AIMessage(content=msg["content"]))

        for attempt in range(max_retries):
            has_yielded = False
            try:
                chain = self._get_retrieval_chain(collection_name, selected_documents, system_prompt, user_context, deep=deep)
                sources_data = []

                empty_context = False
                async for chunk in chain.astream(
                    {"input": question, "chat_history": history_messages}
                ):
                    # Retrieval comes before generation: if it found nothing
                    # (index empty or still rebuilding), stop before the LLM call
                    # and answer from the documents' stored text instead.
                    if "context" in chunk and not chunk["context"] and not has_yielded:
                        empty_context = True
                        break

                    # Check for answer chunks
                    if "answer" in chunk:
                        has_yielded = True
                        yield chunk["answer"]

                    # Capture context when available (usually at start or end)
                    if "context" in chunk:
                        for doc in chunk["context"]:
                            doc_name = doc.metadata.get("document_name", "Unknown")
                            doc_id = doc.metadata.get("document_id", "")

                            # Use cached name first, then metadata, then "Unknown"
                            if doc_id and doc_id in doc_name_cache:
                                doc_name = doc_name_cache[doc_id]
                            elif doc_name == "Unknown" and doc_id:
                                try:
                                    res = (
                                        (await async_db(lambda: self.client.table("documents")
                                        .select("filename")
                                        .eq("id", doc_id)
                                        .execute()))
                                    )
                                    if res.data:
                                        doc_name = res.data[0]["filename"]
                                        doc_name_cache[doc_id] = doc_name
                                except:
                                    pass

                            sources_data.append(
                                {
                                    "doc_id": doc_id,
                                    "doc_name": doc_name,
                                    "chunk_text": doc.page_content,
                                    "page": doc.metadata.get("page"),
                                }
                            )

                if empty_context:
                    self._trigger_reindex(project_id)
                    fallback = await self._answer_from_stored_text(
                        project_id, question, selected_documents, chat_history, user_context,
                        deep=deep,
                    )
                    import json

                    if fallback:
                        yield fallback["answer"]
                        yield f"\n\n__SOURCES__:{json.dumps(fallback['sources'])}"
                    else:
                        yield "I couldn't find any readable text in the selected documents yet. Try again once they finish processing."
                        yield "\n\n__SOURCES__:[]"
                    return

                if not sources_data:
                    self._trigger_reindex(project_id)

                # Send sources at the end
                import json

                yield f"\n\n__SOURCES__:{json.dumps(sources_data)}"
                return  # Success, exit retry loop

            except Exception as e:
                error_str = str(e).lower()
                is_retryable = any(
                    x in error_str
                    for x in [
                        "503",
                        "service unavailable",
                        "rate limit",
                        "overloaded",
                        "529",
                        "too many requests",
                    ]
                )

                if is_retryable and attempt < max_retries - 1:
                    delay = min(base_delay * (2**attempt), 15.0)
                    logger.warning(
                        f"Retryable streaming error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    continue

                # On final failure, try non-streaming fallback
                if attempt == max_retries - 1:
                    logger.warning(
                        f"Streaming failed after {max_retries} attempts, trying non-streaming fallback..."
                    )
                    try:
                        # Use non-streaming as fallback
                        result = await self.get_answer(
                            project_id=project_id,
                            question=question,
                            selected_documents=selected_documents,
                            chat_history=chat_history,
                            system_prompt=system_prompt,
                            user_context=user_context,
                        )
                        yield result["answer"]
                        import json

                        yield f"\n\n__SOURCES__:{json.dumps(result.get('sources', []))}"
                        return
                    except Exception as fallback_err:
                        logger.error(f"Fallback also failed: {fallback_err}")
                        yield f"Error: Service temporarily unavailable. Please try again in a moment."
                        return

                logger.error(f"Error in RAG stream: {str(e)}")

                if "Not found: Collection" in str(e) or "doesn't exist" in str(e):
                    self._trigger_reindex(project_id)
                # Failed before any answer text (search, embeddings or index):
                # answer from the documents' stored text instead.
                if not has_yielded:
                    try:
                        fallback = await self._answer_from_stored_text(
                            project_id, question, selected_documents, chat_history, user_context,
                            deep=deep,
                        )
                        if fallback:
                            import json

                            yield fallback["answer"]
                            yield f"\n\n__SOURCES__:{json.dumps(fallback['sources'])}"
                            return
                    except Exception as fb_err:
                        logger.error(f"Stored-text fallback failed: {fb_err}")

                yield f"Error: {self._friendly_error(e)}"
                return

    async def generate_summary(
        self, project_id: str, selected_documents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate summary with retry logic for reliability"""
        try:
            # 1. Check if summary already exists in DB (skip cache for selected docs)
            if not selected_documents:
                try:
                    cached_res = (
                        (await async_db(lambda: self.client.table("project_summaries")
                        .select("summary")
                        .eq("project_id", project_id)
                        .execute()))
                    )
                    if cached_res.data:
                        logger.info(
                            f"Returning cached summary for project {project_id}"
                        )
                        return {
                            "answer": cached_res.data[0]["summary"],
                            "sources": [],
                        }
                except Exception as cache_err:
                    logger.warning(f"Failed to fetch cached summary: {cache_err}")

            # 2. Generate if not found
            query = (
                self.client.table("documents")
                .select("id, project_id, filename, text_storage_path")
                .eq("project_id", project_id)
                .eq("upload_status", "completed")
            )
            if selected_documents:
                query = query.in_("id", selected_documents)
            response = (await async_db(lambda: query.execute()))
            documents = response.data
            if not documents:
                return {"answer": "No documents available.", "sources": []}

            all_intro_text = ""
            sources = []
            collection_name = f"project_{project_id}"

            for doc in documents:
                chunks = await qdrant_service.get_initial_chunks(
                    collection_name, doc["id"], 3
                )
                if not chunks:
                    # Not indexed (yet): use the opening of the stored text
                    from services.document_service import document_service
                    text = await document_service.load_stored_text(doc)
                    if text:
                        chunks = [text[i:i + 1500] for i in range(0, min(len(text), 4500), 1500)]
                if chunks:
                    doc_text = "\n".join(chunks)
                    all_intro_text += (
                        f"--- Document: {doc['filename']} ---\n{doc_text}\n\n"
                    )
                    sources.append(
                        {
                            "doc_id": doc["id"],
                            "doc_name": doc["filename"],
                            "chunk_text": chunks[0][:100] + "...",
                        }
                    )

            if not all_intro_text:
                return {"answer": "Unable to read content.", "sources": []}

            prompt = f"""You are an expert research assistant.
Here are the introductions/beginnings of the documents in this project:

{all_intro_text[:10000]}

Please provide a concise and engaging collaborative summary of what these documents are about.
Highlight the main topics and key themes.
IMPORTANT: Format the output using standard Markdown. Do NOT use any HTML tags like <br>. Use standard newline characters (\\n) for spacing and line breaks.
"""
            messages = [HumanMessage(content=prompt)]

            # Use retry logic for LLM call
            async def invoke_llm():
                return await self._llm().ainvoke(messages)

            response = await retry_with_backoff(
                invoke_llm, max_retries=3, base_delay=1.5
            )
            # Remove any stray HTML break tags the LLM might have still generated
            summary_text = response.content.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")

            # 3. Store in DB only for full project summaries
            if not selected_documents:
                try:
                    (await async_db(lambda: self.client.table("project_summaries").upsert(
                        {"project_id": project_id, "summary": summary_text},
                        on_conflict="project_id",
                    ).execute()))
                except Exception as store_err:
                    logger.error(f"Failed to store summary: {store_err}")

            return {"answer": summary_text, "sources": sources}

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise


rag_service = RAGService()
