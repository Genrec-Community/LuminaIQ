from fastapi import APIRouter, HTTPException, Depends
from utils.rate_limit import rate_limit
from utils.tools import assert_tool, require_tool
from fastapi.responses import StreamingResponse
from services.rag_service import rag_service
from services.user_data_service import user_data
from models.schemas import ChatRequest, ChatResponse, ChatMessage, SummaryRequest
from typing import Any, List, Optional

from pydantic import BaseModel, Field
from api.deps import get_current_user
from db.client import get_supabase_client, async_db
from utils.logger import logger
import asyncio
import json
from services.usage_service import usage, metered
from config.settings import settings as app_settings
from services import photo_questions
from services import answer_cache, chat_threads, context_builder, learner_model, levels, memory, safety, shared_content
from services.telemetry import meter
from services.prompts.levels import build_level_block, resolve_hints

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
        
        level = "" if settings.get("studyLevel") else settings.get("selfLevel", "")
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

        age_group = "" if settings.get("studyLevel") else settings.get("ageGroup", "")
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
    project_id: str, thread_id: Optional[str] = None, current_user: dict = Depends(get_current_user)
):
    """Messages of one of the book's chats (default: the most recent chat)."""
    if thread_id:
        thread = await chat_threads.resolve(project_id, current_user["id"], thread_id)
    else:
        latest = await chat_threads.list_threads(project_id, current_user["id"])
        if not latest:
            return []
        thread = latest[0]
    rows = await chat_threads.messages(thread["id"])
    urls = await asyncio.gather(*[photo_questions.signed_url(m.get("image_path")) for m in rows])
    return [ChatMessage(role=m["role"], content=m["content"], image_url=url,
                        sources=m.get("sources") if isinstance(m.get("sources"), list) else None,
                        created_at=str(m["created_at"]) if m.get("created_at") else None)
            for m, url in zip(rows, urls)]


class ThreadCreate(BaseModel):
    project_id: str
    title: Optional[str] = None


class ThreadRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


@router.get("/threads/{project_id}")
async def list_threads(project_id: str, current_user: dict = Depends(get_current_user)):
    """The book's chats, most recent first (like ChatGPT's sidebar)."""
    return {"threads": await chat_threads.list_threads(project_id, current_user["id"])}


@router.post("/threads")
async def new_thread(body: ThreadCreate, current_user: dict = Depends(get_current_user)):
    """Start a new, empty chat for this book."""
    return await chat_threads.create(body.project_id, current_user["id"], body.title)


@router.patch("/threads/{thread_id}")
async def rename_thread(thread_id: str, body: ThreadRename, current_user: dict = Depends(get_current_user)):
    return await chat_threads.rename(thread_id, current_user["id"], body.title)


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, current_user: dict = Depends(get_current_user)):
    await chat_threads.delete(thread_id, current_user["id"])
    return {"deleted": True}


# Without a chat summary yet, only the most recent turns go to the model: answers stay
# grounded in the book, and requests don't grow slower and costlier as a chat gets longer.
CHAT_HISTORY_LIMIT = 12


async def _load_memory(request: ChatRequest, user_id: str, thread_id: str):
    """
    (chat summary, recent turns, learner snapshot, memory facts, across-books setting).
    Long chats come back as a summary plus the recent turns (services/memory.py).
    """
    client = get_supabase_client()
    try:
        prefs = await memory.settings_for(user_id)
        (summary, history), snap, facts = await asyncio.gather(
            memory.chat_context(thread_id),
            learner_model.snapshot(user_id, request.project_id, prefs["across_books"]),
            memory.for_prompt(user_id, request.project_id, request.message, prefs["across_books"]),
        )
        return summary, history, snap, facts
    except Exception as e:
        logger.debug(f"Memory unavailable, using recent turns only: {e}")
    res = await async_db(
        lambda: client.table("chat_messages")
        .select("role, content")
        .eq("thread_id", thread_id)
        .order("created_at", desc=True)
        .limit(CHAT_HISTORY_LIMIT)
        .execute()
    )
    return "", [{"role": m["role"], "content": m["content"]} for m in reversed(res.data or [])], None, []


async def _prepare_chat(request: ChatRequest, user_id: str):
    """
    Load the chat so far, what we know about the student and their profile in parallel,
    and start saving the new user message in the background. Returns
    (history, user_context, save_task, level info); await save_task before saving the reply
    so the two stay in order. request.thread_id is set to the chat the message went to.
    """
    client = get_supabase_client()
    thread = await chat_threads.resolve(request.project_id, user_id, request.thread_id)
    request.thread_id = thread["id"]
    (summary, history, snap, facts), user_context, eff = await asyncio.gather(
        _load_memory(request, user_id, thread["id"]), get_user_context_string(user_id),
        levels.effective_for(user_id)
    )
    # The answer style for their level, school safety rules, hints-first and outside-book
    level_block = build_level_block(eff, resolve_hints(eff, request.hints))
    # The profile has a budget; the level rules (including school safety) are never trimmed
    user_context = context_builder.trim(user_context, app_settings.CONTEXT_BUDGET_PROFILE)
    # Prompt order (stable first, for provider prefix caching): profile, what we know, level rules
    known = context_builder.learner_block(snap, facts, summary, app_settings.CONTEXT_BUDGET_MEMORY)
    user_context = "\n\n".join(p for p in (user_context, known, level_block) if p)
    async def save_question():
        await async_db(lambda: client.table("chat_messages").insert(
            {"project_id": request.project_id, "thread_id": thread["id"], "role": "user", "content": request.message,
             "image_path": getattr(request, "image_path", None)}
        ).execute())
        await chat_threads.touch(thread, request.message)

    save_task = asyncio.create_task(save_question())
    return history, user_context, save_task, eff


def _after_reply(request: ChatRequest, user_id: str, eff) -> None:
    """Refresh the chat summary and memory facts in the background once enough turns piled up."""
    task = asyncio.create_task(memory.maybe_refresh(request.thread_id, user_id, eff.get("level") or "general"))
    _background.add(task)
    task.add_done_callback(_background.discard)


_background: set = set()


async def _answer_cache_plan(request: ChatRequest, history, eff):
    """
    (scope, key) when this message may use the shared answer cache: the first question of
    a chat about shared-library or class books, without hints-first or a custom prompt.
    """
    if history or request.system_prompt or resolve_hints(eff, request.hints):
        return None
    if photo_questions.PHOTO_MARKER in (getattr(request, "message", "") or ""):
        return None   # photo questions are personal: never shared or served from the cache
    scope = await shared_content.scope_for(request.project_id, request.selected_documents)
    if not scope:
        return None
    return scope, answer_cache.scope_key(scope, eff.get("level") or "general", request.deep,
                                         eff.get("outside_book", True))


async def _attach_photo(request: ChatRequest, current_user: dict) -> Optional[str]:
    """
    A photo with the message: read it (vision model), keep it for the thumbnail, and add its
    transcript to request.message so the book is searched for it. Returns a reply to send
    instead (an unsuitable photo for Class 5-10), else None.
    """
    request.image_path = None
    if not request.image:
        return None
    from services.llm_service import vision_config
    uid = current_user["id"]
    await assert_tool(uid, "image")
    plan = await usage.plan(uid)
    if vision_config(plan) is None:
        raise HTTPException(403, {"code": "tool_disabled", "tool": "image",
                                  "message": "Photo questions aren't available on your plan yet."})
    try:
        photo = photo_questions.decode(request.image)
    except photo_questions.PhotoError as e:
        raise HTTPException(400, str(e))
    request.image = None
    await usage.consume(uid, "image")
    eff = await levels.effective_for(uid)
    try:
        transcript, unsafe = await photo_questions.read_photo(photo, eff.get("level") or "general", plan)
    except Exception as e:
        logger.error(f"[Photo] reading failed: {e}")
        raise HTTPException(502, "I couldn't read that photo just now. Please try again.")
    if unsafe:
        request.message = (request.message or "").strip() or "(photo)"
        return photo_questions.UNSAFE_REPLY
    request.image_path = await photo_questions.store(uid, photo)
    request.message = photo_questions.with_photo(request.message, transcript)
    return None


async def _save_reply(request: ChatRequest, save_task, answer: str, sources=None) -> None:
    await save_task
    await async_db(lambda: get_supabase_client().table("chat_messages").insert(
        {"project_id": request.project_id, "thread_id": request.thread_id, "role": "assistant",
         "content": answer, "sources": sources or []}
    ).execute())


@router.post("/message", response_model=ChatResponse, dependencies=[Depends(rate_limit("chat")), Depends(require_tool("chat"))])
async def chat_message(
    request: ChatRequest, current_user: dict = Depends(get_current_user)
):
    """
    Send a message to the RAG chat (Blocking/Non-streaming)
    """
    feature = "deep" if request.deep else "chat"
    if request.deep:
        await assert_tool(current_user["id"], "deep")
    metered(current_user, feature)
    await usage.consume(current_user["id"], feature)
    photo_reply = await _attach_photo(request, current_user)
    try:
        client = get_supabase_client()
        chat_history_dicts, user_context_str, save_task, eff = await _prepare_chat(
            request, current_user["id"]
        )
        safe_reply = photo_reply or await safety.screen(request.message, eff["level"], current_user["id"])
        if safe_reply:
            await _save_reply(request, save_task, safe_reply)
            return {"answer": safe_reply, "sources": [], "thread_id": request.thread_id}

        plan = await _answer_cache_plan(request, chat_history_dicts, eff)
        if plan:
            hit = await answer_cache.lookup(plan[0], plan[1], request.message)
            if hit:
                await _save_reply(request, save_task, hit["answer"], hit["sources"])
                return {"answer": hit["answer"], "sources": hit["sources"], "thread_id": request.thread_id}
            # A cached answer is shared by every student of this book: neutral voice, level style only
            user_context_str = build_level_block(eff, False)

        with meter() as cost:
            result = await rag_service.get_answer(
                project_id=request.project_id,
                question=request.message,
                selected_documents=request.selected_documents,
                chat_history=chat_history_dicts,
                system_prompt=request.system_prompt,
                user_context=user_context_str,
                deep=request.deep,
            )
        if plan:
            await answer_cache.store(plan[0], plan[1], request.message, result["answer"], result["sources"],
                                     cost.cost)

        await save_task
        # Save Assistant Message (non-blocking)
        await async_db(
            lambda: client.table("chat_messages").insert(
                {
                    "project_id": request.project_id,
                    "thread_id": request.thread_id,
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result["sources"],
                }
            ).execute()
        )
        _after_reply(request, current_user["id"], eff)

        return {**result, "thread_id": request.thread_id}

    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/stream", dependencies=[Depends(rate_limit("chat")), Depends(require_tool("chat"))])
async def chat_stream(
    request: ChatRequest, current_user: dict = Depends(get_current_user)
):
    """
    Send a message to the RAG chat (Streaming)
    """
    feature = "deep" if request.deep else "chat"
    if request.deep:
        await assert_tool(current_user["id"], "deep")
    metered(current_user, feature)
    await usage.consume(current_user["id"], feature)
    photo_reply = await _attach_photo(request, current_user)
    try:
        chat_history_dicts, user_context_str, save_task, eff = await _prepare_chat(
            request, current_user["id"]
        )
        safe_reply = photo_reply or await safety.screen(request.message, eff["level"], current_user["id"])
        if safe_reply:
            async def caring_reply():
                yield safe_reply
                yield "\n\n__SOURCES__:[]"
                try:
                    await _save_reply(request, save_task, safe_reply)
                except Exception as save_err:
                    logger.error(f"Failed to save safety reply: {save_err}")
            return StreamingResponse(caring_reply(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "X-Thread-Id": request.thread_id or ""})

        plan = await _answer_cache_plan(request, chat_history_dicts, eff)
        hit = await answer_cache.lookup(plan[0], plan[1], request.message) if plan else None
        if hit:
            async def cached_reply():
                text = hit["answer"]
                for i in range(0, len(text), 400):
                    yield text[i:i + 400]
                yield f"\n\n__SOURCES__:{json.dumps(hit['sources'])}"
                try:
                    await _save_reply(request, save_task, text, hit["sources"])
                except Exception as save_err:
                    logger.error(f"Failed to save cached reply: {save_err}")
            return StreamingResponse(cached_reply(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "X-Thread-Id": request.thread_id or ""})
        if plan:
            # A cached answer is shared by every student of this book: neutral voice, level style only
            user_context_str = build_level_block(eff, False)

        # Wrapper generator to intercept and save the final answer
        async def stream_and_save():
            full_answer = ""
            sources = []
            with meter() as spent:
                async for chunk in rag_service.get_answer_stream(
                    project_id=request.project_id,
                    question=request.message,
                    selected_documents=request.selected_documents,
                    chat_history=chat_history_dicts,
                    system_prompt=request.system_prompt,
                    user_context=user_context_str,
                    deep=request.deep,
                ):
                    if "__SOURCES__:" in chunk:
                        text, _, raw = chunk.partition("__SOURCES__:")
                        full_answer += text
                        try:
                            sources = json.loads(raw)
                        except Exception:
                            pass
                    else:
                        full_answer += chunk
                    yield chunk   # the frontend reads the sources marker itself

            full_answer = full_answer.rstrip()
            if plan:
                await answer_cache.store(plan[0], plan[1], request.message, full_answer, sources, spent.cost)

            # Save Assistant Message after stream ends (non-blocking)
            try:
                await save_task
                await async_db(
                    lambda: get_supabase_client().table("chat_messages").insert(
                        {
                            "project_id": request.project_id,
                            "thread_id": request.thread_id,
                            "role": "assistant",
                            "content": full_answer,
                            "sources": sources,
                        }
                    ).execute()
                )
                _after_reply(request, current_user["id"], eff)
            except Exception as save_err:
                logger.error(f"Failed to save assistant message: {save_err}")

        return StreamingResponse(
            stream_and_save(),
            media_type="text/event-stream",
            # Deliver tokens as they're generated instead of letting proxies buffer them
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "X-Thread-Id": request.thread_id or ""},
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/summary", response_model=ChatResponse, dependencies=[Depends(rate_limit("generate")), Depends(require_tool("chat"))])
async def get_project_summary(
    request: SummaryRequest, current_user: dict = Depends(get_current_user)
):
    """
    Generate a summary for the project documents
    """
    metered(current_user, "summary")
    await usage.consume(current_user["id"], "tools")
    try:
        result = await rag_service.generate_summary(
            request.project_id, request.selected_documents
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
