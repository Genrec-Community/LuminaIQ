from typing import List, Dict, Any, Optional
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service
from services.llm_service import llm_service
from supabase import create_client, Client
from config.settings import settings
from utils.logger import logger

# LangChain Imports
from langchain_qdrant import QdrantVectorStore
from langchain_together import ChatTogether
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig


class RAGService:
    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY
        )

        # Initialize LLM
        self.llm = ChatTogether(
            model=settings.LLM_MODEL,
            together_api_key=settings.TOGETHER_API_KEY,
            temperature=0.7,
        )

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
        system_prompt = """You are an expert educational assistant. 
Your goal is to provide accurate, well-structured, and comprehensive answers based strictly on the provided context.

Guidelines:
1. **Format:** Use **Markdown** for all responses. Use headers, bullet points, and bold text to improve readability.
2. **Citations:** Always cite your sources implicitly or explicitly if relevant (e.g., "According to [Source 1]...").
3. **Accuracy:** If the answer is not in the context, state clearly: "I couldn't find the answer in the provided documents."
4. **Tone:** Professional, encouraging, and educational.

Context:
{context}"""

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
        """Generate answer using RAG pipeline (LangChain)"""
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

            # Invoke
            response = await chain.ainvoke(
                {"input": question, "chat_history": history_messages}
            )

            # Process sources from 'context' in response
            sources = []
            if "context" in response:
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
                            "chunk_text": doc.page_content[:100] + "...",
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
        """Generate answer using RAG pipeline with streaming (LangChain)"""
        try:
            collection_name = f"project_{project_id}"
            chain = self._get_retrieval_chain(collection_name, selected_documents)

            history_messages = []
            for msg in chat_history:
                if msg["role"] == "user":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    history_messages.append(AIMessage(content=msg["content"]))

            # Stream
            # We need to capture context/sources which usually come in the final output or as events
            # 'astream_events' or 'astream_log' is useful, but 'astream' usually just yields the answer chunks.
            # create_retrieval_chain returns a dict with 'answer' and 'context'.
            # Standard astream yields the output dict chunks. For 'answer' key it yields chunks of the string.

            sources_sent = False
            sources_data = []

            async for chunk in chain.astream(
                {"input": question, "chat_history": history_messages}
            ):
                # Check for answer chunks
                if "answer" in chunk:
                    yield chunk["answer"]

                # Capture context when available (usually at start or end)
                if "context" in chunk and not sources_sent:
                    for doc in chunk["context"]:
                        doc_name = doc.metadata.get("document_name", "Unknown")
                        doc_id = doc.metadata.get("document_id", "")
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

                        sources_data.append(
                            {
                                "doc_id": doc_id,
                                "doc_name": doc_name,
                                "chunk_text": doc.page_content[:100] + "...",
                            }
                        )

            # Send sources at the end
            import json

            yield f"\n\n__SOURCES__:{json.dumps(sources_data)}"

        except Exception as e:
            logger.error(f"Error in RAG stream: {str(e)}")
            yield f"Error: {str(e)}"

    async def generate_summary(
        self, project_id: str, selected_documents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        # Reuse existing logic or adapt to LangChain.
        # Existing logic does manual retrieval of N chunks.
        # We can keep using qdrant_service.get_initial_chunks for this specific task
        # as it's not a standard semantic search.
        # Just update the LLM call to use LangChain chat model.
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
                            "sources": [],  # Sources not stored in simple cache, acceptable for summary
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
"""
            messages = [HumanMessage(content=prompt)]
            response = await self.llm.ainvoke(messages)
            summary_text = response.content

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
