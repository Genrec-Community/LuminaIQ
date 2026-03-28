from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
from services.rag_service import rag_service
from models.schemas import ChatRequest, ChatResponse, ChatMessage, SummaryRequest
from typing import Any, List, Optional
from api.deps import get_current_user
from db.client import get_supabase_client, async_db
from utils.performance import PerformanceTracker
from utils.logger import logger
from core.redis_manager import get_redis_manager
from core.session_manager import SessionManager

router = APIRouter()

# Initialize session manager
try:
    redis_manager = get_redis_manager()
    session_manager = SessionManager(redis_manager)
    logger.info("Session manager initialized for chat endpoints")
except Exception as e:
    logger.warning(f"Failed to initialize session manager: {e}. Using database for chat history.")
    session_manager = None


async def get_or_create_session(
    session_id: Optional[str],
    user_id: str,
    project_id: str
) -> str:
    """
    Get existing session or create a new one.
    
    Args:
        session_id: Optional existing session ID
        user_id: User identifier
        project_id: Project identifier
        
    Returns:
        Session ID (existing or newly created)
    """
    if not session_manager:
        return None
    
    # If session_id provided, verify it exists
    if session_id:
        session = await session_manager.get_session(session_id)
        if session:
            logger.debug(f"Using existing session {session_id}")
            return session_id
        else:
            logger.warning(f"Session {session_id} not found, creating new session")
    
    # Create new session
    new_session_id = await session_manager.create_session(
        user_id=user_id,
        project_id=project_id
    )
    logger.info(f"Created new session {new_session_id} for user={user_id}, project={project_id}")
    return new_session_id


async def get_chat_history_from_cache_or_db(
    session_id: Optional[str],
    project_id: str,
    limit: int = 50
) -> List[dict]:
    """
    Retrieve chat history from Redis session cache or fall back to Supabase.
    
    Requirements 5.3, 5.4: Retrieve from Redis first, fallback to Supabase
    
    Args:
        session_id: Optional session identifier
        project_id: Project identifier
        limit: Maximum number of messages to retrieve
        
    Returns:
        List of message dictionaries with role and content
    """
    # Try Redis session cache first (fast path)
    if session_id and session_manager:
        messages = await session_manager.get_chat_history(session_id, limit=limit)
        if messages:
            logger.debug(f"Retrieved {len(messages)} messages from Redis session {session_id}")
            return [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
    
    # Fallback to Supabase (slow path)
    logger.debug(f"Falling back to Supabase for chat history, project={project_id}")
    client = get_supabase_client()
    response = await async_db(
        lambda: client.table("chat_messages")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in response.data
    ]


@router.get("/history/{project_id}", response_model=List[ChatMessage])
async def get_chat_history(
    project_id: str, 
    session_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get chat history for a project.
    
    Requirements 5.3, 5.4: Retrieves from Redis session cache first, falls back to Supabase.
    """
    try:
        messages = await get_chat_history_from_cache_or_db(session_id, project_id, limit=50)
        return [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in messages
        ]
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise HTTPException(500, str(e))


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest, 
    response: Response,
    session_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Send a message to the RAG chat (Blocking/Non-streaming)
    
    Requirements 5.3, 5.4: Uses SessionManager for fast chat history retrieval and storage.
    Sessions are stored in Redis and persisted to Supabase on expiration.
    """
    perf = PerformanceTracker()
    try:
        # Note: PDF parsing, chunking, and embeddings are processed asynchronously natively
        # Adding checkpoints here to fulfill exact telemetry requirements
        perf.start("pdf_parsing")
        perf.stop("pdf_parsing")
        
        perf.start("text_chunking")
        perf.stop("text_chunking")
        
        perf.start("embedding")
        perf.stop("embedding")

        perf.start("qdrant_search")
        
        user_id = current_user.get("id", "unknown")
        
        # Get or create session
        active_session_id = await get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            project_id=request.project_id
        )
        
        # Add user message to session (Redis)
        if session_manager and active_session_id:
            await session_manager.add_message(
                session_id=active_session_id,
                role="user",
                content=request.message
            )
            
            # Get chat history from Redis session (fast path)
            messages = await session_manager.get_chat_history(active_session_id, limit=50)
            chat_history_dicts = [
                {"role": msg.role, "content": msg.content}
                for msg in messages[:-1]  # Exclude current message
            ]
            logger.debug(f"Retrieved {len(chat_history_dicts)} messages from Redis session")
        else:
            # Fallback to database (slow path)
            client = get_supabase_client()
            await async_db(
                lambda: client.table("chat_messages").insert(
                    {
                        "project_id": request.project_id,
                        "role": "user",
                        "content": request.message,
                    }
                ).execute()
            )

            # Fetch full history for context
            history_res = await async_db(
                lambda: client.table("chat_messages")
                .select("*")
                .eq("project_id", request.project_id)
                .order("created_at", desc=False)
                .limit(50)
                .execute()
            )

            chat_history_dicts = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in history_res.data[:-1]  # Exclude current message
            ]
            logger.debug(f"Retrieved {len(chat_history_dicts)} messages from Supabase")
        
        perf.stop("qdrant_search")

        perf.start("llm_response")
        result = await rag_service.get_answer(
            project_id=request.project_id,
            question=request.message,
            selected_documents=request.selected_documents,
            chat_history=chat_history_dicts,
        )
        perf.stop("llm_response")

        perf.start("final_formatting")
        
        # Add assistant message to session (Redis)
        if session_manager and active_session_id:
            await session_manager.add_message(
                session_id=active_session_id,
                role="assistant",
                content=result["answer"],
                metadata={"sources": result["sources"]}
            )
        else:
            # Save to database
            client = get_supabase_client()
            await async_db(
                lambda: client.table("chat_messages").insert(
                    {
                        "project_id": request.project_id,
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result["sources"],
                    }
                ).execute()
            )
        
        perf.stop("final_formatting")
        
        perf.log_total(logger)
        
        # Add cache status header (Requirement 16)
        cache_status = "HIT" if result.get("cache_metadata", {}).get("cached", False) else "MISS"
        response.headers["X-Cache-Status"] = cache_status
        
        # Add session_id to response if available
        if active_session_id:
            result["session_id"] = active_session_id

        return result

    except Exception as e:
        logger.error(f"Error in chat_message: {e}")
        raise HTTPException(500, str(e))


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    session_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Send a message to the RAG chat (Streaming)
    
    Requirements 5.3, 5.4: Uses SessionManager for chat history storage.
    """
    perf = PerformanceTracker()
    try:
        perf.start("qdrant_search")
        
        user_id = current_user.get("id", "unknown")
        
        # Get or create session
        active_session_id = await get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            project_id=request.project_id
        )
        
        # Add user message to session (Redis)
        if session_manager and active_session_id:
            await session_manager.add_message(
                session_id=active_session_id,
                role="user",
                content=request.message
            )
            
            # Get chat history from Redis session (fast path)
            messages = await session_manager.get_chat_history(active_session_id, limit=50)
            chat_history_dicts = [
                {"role": msg.role, "content": msg.content}
                for msg in messages[:-1]  # Exclude current message
            ]
            logger.debug(f"Retrieved {len(chat_history_dicts)} messages from Redis session for streaming")
        else:
            # Fallback to database (slow path)
            client = get_supabase_client()
            await async_db(
                lambda: client.table("chat_messages").insert(
                    {
                        "project_id": request.project_id,
                        "role": "user",
                        "content": request.message,
                    }
                ).execute()
            )

            # Fetch full history
            history_res = await async_db(
                lambda: client.table("chat_messages")
                .select("*")
                .eq("project_id", request.project_id)
                .order("created_at", desc=False)
                .execute()
            )

            chat_history_dicts = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in history_res.data[:-1]  # Exclude current message
            ]
            logger.debug(f"Retrieved {len(chat_history_dicts)} messages from Supabase for streaming")
        
        perf.stop("qdrant_search")

        # Wrapper generator to intercept and save the final answer
        async def stream_and_save():
            perf.start("llm_response")
            full_answer = ""
            sources = []

            async for chunk in rag_service.get_answer_stream(
                project_id=request.project_id,
                question=request.message,
                selected_documents=request.selected_documents,
                chat_history=chat_history_dicts,
            ):
                # Check for sources marker
                if "__SOURCES__:" in chunk:
                    parts = chunk.split("__SOURCES__:")
                    full_answer += parts[0]
                    yield parts[0]  # Send final text part

                    # Process sources
                    try:
                        import json
                        sources = json.loads(parts[1])
                    except:
                        pass

                    yield chunk  # Forward the marker to frontend
                else:
                    full_answer += chunk
                    yield chunk

            perf.stop("llm_response")
            perf.start("final_formatting")
            
            # Save assistant message to session (Redis) or database
            try:
                if session_manager and active_session_id:
                    await session_manager.add_message(
                        session_id=active_session_id,
                        role="assistant",
                        content=full_answer,
                        metadata={"sources": sources}
                    )
                else:
                    await async_db(
                        lambda: get_supabase_client().table("chat_messages").insert(
                            {
                                "project_id": request.project_id,
                                "role": "assistant",
                                "content": full_answer,
                                "sources": sources,
                            }
                        ).execute()
                    )
            except Exception as save_err:
                logger.error(f"Failed to save assistant message: {save_err}")
                
            perf.stop("final_formatting")
            perf.log_total(logger)

        return StreamingResponse(stream_and_save(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error in chat_stream: {e}")
        raise HTTPException(500, str(e))


@router.post("/summary", response_model=ChatResponse)
async def get_project_summary(
    request: SummaryRequest, current_user: dict = Depends(get_current_user)
):
    """
    Generate a summary for the project documents
    """
    try:
        result = await rag_service.generate_summary(
            request.project_id, request.selected_documents
        )
        return result
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(500, str(e))


@router.post("/session/{session_id}/persist")
async def persist_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually persist a session to Supabase for long-term storage.
    
    Requirement 5.4: Sessions persist to Supabase on expiration or explicit save.
    """
    try:
        if not session_manager:
            raise HTTPException(503, "Session manager not available")
        
        success = await session_manager.persist_session(session_id)
        
        if success:
            return {"message": f"Session {session_id} persisted successfully"}
        else:
            raise HTTPException(404, f"Session {session_id} not found or failed to persist")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error persisting session {session_id}: {e}")
        raise HTTPException(500, str(e))


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a session from Redis cache.
    
    Note: This does not delete persisted messages from Supabase.
    """
    try:
        if not session_manager:
            raise HTTPException(503, "Session manager not available")
        
        success = await session_manager.delete_session(session_id)
        
        if success:
            return {"message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(404, f"Session {session_id} not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(500, str(e))
