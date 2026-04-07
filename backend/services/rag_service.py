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
    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY
        )

        # Initialize LLM via centralized llm_service
        self.llm = llm_service._get_client(temperature=0.1)

    def _get_retrieval_chain(
        self, collection_name: str, selected_documents: Optional[List[str]] = None
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
        system_prompt = """You are Lumina IQ, an elite educational intelligence system designed to transform raw study material into clear, structured understanding.

Your objective is NOT just accuracy — it is clarity, usefulness, and insight.

You are given context extracted from user documents. Each excerpt represents a numbered source:
- First excerpt → Source 1 → cite as 
- Second excerpt → Source 2 → cite as 
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
- Use citation format: , 
- Place citations inline next to facts.
- If a statement clearly comes from context → cite it.
- If citation is slightly uncertain → still answer, but prioritize clarity over rigid citation.

DO NOT:
- Use plain numbers
- Use [1] or [[1]]
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

---

Context:
{context}
"""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )

        # 3. Chains
        question_answer_chain = create_stuff_documents_chain(self.llm, prompt)
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)

        return rag_chain

    async def get_answer(
        self,
        project_id: str,
        question: str,
        selected_documents: Optional[List[str]] = None,
        chat_history: List[Dict[str, str]] = [],
    ) -> Dict[str, Any]:
        """Generate answer using RAG pipeline (LangChain) with retry logic"""
        try:
            collection_name = f"project_{project_id}"
            chain = self._get_retrieval_chain(collection_name, selected_documents)

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

            # Process sources from 'context' in response
            sources = []
            if "context" in response:
                # DIAGNOSTIC: Log retrieved chunks
                logger.debug(f"Retrieved {len(response['context'])} semantic chunks from context payload")
                
                for i, doc in enumerate(response["context"]):
                    # Resolve filename from doc.metadata if available
                    doc_name = doc.metadata.get("document_name", "Unknown")
                    doc_id = doc.metadata.get("document_id", "")

                    # If name missing in metadata, try DB lookup (cached ideally)
                    if doc_name == "Unknown" and doc_id:
                        try:
                            res = (
                                self.client.table("documents")
                                .select("filename")
                                .eq("id", doc_id)
                                .execute()
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
            raise

    async def get_answer_stream(
        self,
        project_id: str,
        question: str,
        selected_documents: Optional[List[str]] = None,
        chat_history: List[Dict[str, str]] = [],
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
                    self.client.table("documents")
                    .select("id, filename")
                    .in_("id", selected_documents)
                    .execute()
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
            try:
                chain = self._get_retrieval_chain(collection_name, selected_documents)
                sources_data = []
                has_yielded = False

                async for chunk in chain.astream(
                    {"input": question, "chat_history": history_messages}
                ):
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
                                        self.client.table("documents")
                                        .select("filename")
                                        .eq("id", doc_id)
                                        .execute()
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
                yield f"Error: {str(e)}"
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
                        self.client.table("project_summaries")
                        .select("summary")
                        .eq("project_id", project_id)
                        .execute()
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
                .select("id, filename")
                .eq("project_id", project_id)
                .eq("upload_status", "completed")
            )
            if selected_documents:
                query = query.in_("id", selected_documents)
            response = query.execute()
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
                return await self.llm.ainvoke(messages)

            response = await retry_with_backoff(
                invoke_llm, max_retries=3, base_delay=1.5
            )
            # Remove any stray HTML break tags the LLM might have still generated
            summary_text = response.content.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")

            # 3. Store in DB only for full project summaries
            if not selected_documents:
                try:
                    self.client.table("project_summaries").upsert(
                        {"project_id": project_id, "summary": summary_text},
                        on_conflict="project_id",
                    ).execute()
                except Exception as store_err:
                    logger.error(f"Failed to store summary: {store_err}")

            return {"answer": summary_text, "sources": sources}

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise


rag_service = RAGService()
