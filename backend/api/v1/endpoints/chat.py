from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from services.rag_service import rag_service
from services.user_data_service import user_data
from models.schemas import ChatRequest, ChatResponse, ChatMessage, SummaryRequest
from typing import Any, List
from api.deps import get_current_user
from db.client import get_supabase_client, async_db
from utils.logger import logger

router = APIRouter()


async def get_user_context_string(user_id: str) -> str:
    try:
        settings = await user_data.get_settings(user_id)
        if not settings:
            return ""
            
        context_parts = []
        name = settings.get("studentName", "")
        if name: context_parts.append(f"Student Name: {name}")
        
        goal = settings.get("learningGoal", "")
        if goal: context_parts.append(f"Learning Goal: {goal}")
        
        level = settings.get("selfLevel", "")
        if level:
            level_map = {
                "beginner": "Beginner (Just starting out)",
                "intermediate": "Intermediate (Knows the basics)",
                "advanced": "Advanced (Looking to master)"
            }
            context_parts.append(f"Knowledge Level: {level_map.get(level, level)}")
            
        style = settings.get("learningStyle", "")
        if style:
            style_map = {
                "visual": "Visual (Prefers diagrams & summaries)",
                "reading": "Reading (Deep text-based study)",
                "practice": "Practice (Quizzes & exercises)",
                "balanced": "Balanced (Mix of everything)"
            }
            context_parts.append(f"Preferred Learning Style: {style_map.get(style, style)}")
            
        return "\n".join(context_parts)
    except Exception as e:
        logger.error(f"Error fetching user settings for context: {e}")
        return ""


@router.get("/history/{project_id}", response_model=List[ChatMessage])
async def get_chat_history(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get chat history for a project (non-blocking DB)
    """
    try:
        client = get_supabase_client()
        response = await async_db(
            lambda: client.table("chat_messages")
            .select("*")
            .eq("project_id", project_id)
            .order("created_at", desc=False)
            .execute()
        )

        return [
            ChatMessage(role=msg["role"], content=msg["content"])
            for msg in response.data
        ]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest, current_user: dict = Depends(get_current_user)
):
    """
    Send a message to the RAG chat (Blocking/Non-streaming)
    """
    try:
        client = get_supabase_client()
        # Save User Message (non-blocking)
        await async_db(
            lambda: client.table("chat_messages").insert(
                {
                    "project_id": request.project_id,
                    "role": "user",
                    "content": request.message,
                }
            ).execute()
        )

        # Fetch full history for context (non-blocking)
        history_res = await async_db(
            lambda: client.table("chat_messages")
            .select("*")
            .eq("project_id", request.project_id)
            .order("created_at", desc=False)
            .execute()
        )

        chat_history_dicts = [
            {"role": msg["role"], "content": msg["content"]} for msg in history_res.data
        ]

        user_context_str = await get_user_context_string(current_user["id"])

        result = await rag_service.get_answer(
            project_id=request.project_id,
            question=request.message,
            selected_documents=request.selected_documents,
            chat_history=chat_history_dicts[:-1],  # Exclude current msg to avoid duplication if RAG appends it
            system_prompt=request.system_prompt,
            user_context=user_context_str,
        )

        # Save Assistant Message (non-blocking)
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

        return result

    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/stream")
async def chat_stream(
    request: ChatRequest, current_user: dict = Depends(get_current_user)
):
    """
    Send a message to the RAG chat (Streaming)
    """
    try:
        client = get_supabase_client()
        # Save User Message (non-blocking)
        await async_db(
            lambda: client.table("chat_messages").insert(
                {
                    "project_id": request.project_id,
                    "role": "user",
                    "content": request.message,
                }
            ).execute()
        )

        # Fetch full history (non-blocking)
        history_res = await async_db(
            lambda: client.table("chat_messages")
            .select("*")
            .eq("project_id", request.project_id)
            .order("created_at", desc=False)
            .execute()
        )

        chat_history_dicts = [
            {"role": msg["role"], "content": msg["content"]} for msg in history_res.data
        ]

        user_context_str = await get_user_context_string(current_user["id"])

        # Wrapper generator to intercept and save the final answer
        async def stream_and_save():
            full_answer = ""
            sources = []

            async for chunk in rag_service.get_answer_stream(
                project_id=request.project_id,
                question=request.message,
                selected_documents=request.selected_documents,
                chat_history=chat_history_dicts[:-1],
                system_prompt=request.system_prompt,
                user_context=user_context_str,
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

            # Save Assistant Message after stream ends (non-blocking)
            try:
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
                print(f"Failed to save assistant message: {save_err}")

        return StreamingResponse(stream_and_save(), media_type="text/event-stream")
    except Exception as e:
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
        raise HTTPException(500, str(e))
