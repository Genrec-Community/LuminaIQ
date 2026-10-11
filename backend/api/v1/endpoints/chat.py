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


# Keep keys in sync with AI_CHARACTERS in frontend/src/utils/persona.js
AI_CHARACTER_GUIDANCE = {
    "buddy": "a cheerful, encouraging study buddy who explains like a friend, uses light puns and celebrates progress",
    "mentor": "a calm, wise mentor who is patient, uses Socratic questions and connects ideas to the bigger picture",
    "coach": "a high-energy coach who is goal-focused, motivating, and frames learning like training for a big match",
    "sage": "a gentle, soothing guide who keeps the student relaxed, reduces exam stress and explains step by step",
    "scientist": "a curious scientist who loves real-world examples, experiments and explaining how things work",
    "pirate": "a playful pirate captain who turns learning into a treasure hunt with light pirate talk (never at the cost of clarity)",
}

AGE_GROUP_GUIDANCE = {
    "teen": "a teenager (13-17) — use simple words, relatable examples, short paragraphs",
    "young": "a college student (18-24) — be concise and exam-oriented",
    "adult": "a working professional — be efficient, practical and respectful of their time",
    "mature": "a lifelong learner (45+) — be warm, clear and unhurried; avoid slang",
}

HUMOR_GUIDANCE = {
    "none": "Do not use jokes.",
    "some": "Use an occasional light joke or fun analogy where it helps memory.",
    "lots": "Be playful: sprinkle fun analogies, mnemonics and gentle humour throughout.",
}


def build_persona_block(settings: dict) -> str:
    """Describe the user's customised AI companion for the system prompt."""
    name = (settings.get("aiName") or "").strip()
    character = settings.get("aiCharacter") or ""
    if not name and character not in AI_CHARACTER_GUIDANCE:
        return ""
    lines = ["", "=== YOUR PERSONA (chosen by the student) ==="]
    if name:
        lines.append(f"Your name is {name}. Introduce yourself as {name}, not as Lumina IQ.")
    if character in AI_CHARACTER_GUIDANCE:
        lines.append(f"Personality: {AI_CHARACTER_GUIDANCE[character]}.")
    lines.append(HUMOR_GUIDANCE.get(settings.get("aiHumor", "some"), HUMOR_GUIDANCE["some"]))
    if settings.get("aiEmoji", True) is False:
        lines.append("Do not use emojis.")
    lines.append(
        "Stay in character, but accuracy, clarity and citations always come first. "
        "End longer answers with one quick memory hook or a check-yourself question."
    )
    return "\n".join(lines)


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

        nickname = settings.get("nickname", "")
        if nickname:
            context_parts.append(f"Nickname (address the student by this): {nickname}")

        age_group = settings.get("ageGroup", "")
        if age_group in AGE_GROUP_GUIDANCE:
            context_parts.append(f"Audience: {AGE_GROUP_GUIDANCE[age_group]}")

        exam_name = settings.get("examName", "")
        exam_date = settings.get("examDate", "")
        if exam_name or exam_date:
            context_parts.append(
                f"Preparing for: {exam_name or 'an exam'}"
                + (f" on {exam_date}" if exam_date else "")
                + " — prioritise exam-relevant points, likely questions and memory tricks."
            )

        persona = build_persona_block(settings)
        if persona:
            context_parts.append(persona)

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
