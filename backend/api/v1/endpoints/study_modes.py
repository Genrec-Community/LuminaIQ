"""
Exam Tonight (crash mode) and Visual Lab endpoints. Mounted under /learning.

- POST /cram/plan   - time-boxed study plan (services.cram_planner)
- POST /cram/card   - fast "cram card" for one topic (TL;DR, formulas, quick check)
- POST /visualize   - self-contained interactive HTML simulation for a topic

Cards and simulations are cached per project + topic in the topic_cards table
(migrations/005_topic_cards.sql). Everything still works without that table,
just without the cache.
"""

import asyncio
import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from db.client import async_db, get_supabase_client
from services.book_library import book_library
from services.usage_service import metered, usage
from services.cram_planner import coverage_from_text, plan_session
from services.knowledge_graph_service import knowledge_graph
from services.learning_service import performance_tracker
from services.llm_service import llm_service
from services.rag_service import RAGService
from utils.logger import logger

router = APIRouter()


# ============== Shared helpers ==============


async def _require_project(project_id: str, user: dict) -> None:
    from services.project_service import project_service

    project = await project_service.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.get("user_id") != user["id"]:
        raise HTTPException(403, "Not authorized to access this project")


async def _cache_get(project_id: str, topic: str, kind: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_client()
        res = await async_db(lambda: client.table("topic_cards")
            .select("content")
            .eq("project_id", project_id).eq("topic", topic).eq("kind", kind)
            .limit(1).execute())
        return res.data[0]["content"] if res.data else None
    except Exception as e:  # table not migrated yet, or DB hiccup: no cache
        logger.debug(f"topic_cards read skipped: {e}")
        return None


async def _cache_put(project_id: str, topic: str, kind: str, content: Dict[str, Any]) -> None:
    try:
        client = get_supabase_client()
        await async_db(lambda: client.table("topic_cards").upsert(
            {"project_id": project_id, "topic": topic, "kind": kind, "content": content},
            on_conflict="project_id,topic,kind",
        ).execute())
    except Exception as e:
        logger.debug(f"topic_cards write skipped: {e}")


async def _topic_context(project_id: str, topic: str, document_ids: List[str], limit: int = 8) -> str:
    """Book passages about a topic: vector search, falling back to the stored text."""
    from services.embedding_service import embedding_service
    from services.graph_analytics_service import graph_analytics
    from services.qdrant_service import qdrant_service

    parts: List[str] = []
    try:
        vector = await embedding_service.generate_embedding(topic)
        hits = await qdrant_service.search(
            collection_name=f"project_{project_id}",
            query_vector=vector,
            limit=limit,
            filter_conditions={"document_ids": document_ids} if document_ids else None,
        )
        parts = [h["text"] for h in hits if h.get("text")]
    except Exception as e:
        logger.warning(f"Vector search failed for '{topic}', using stored text: {e}")

    if not parts:
        try:
            from services.document_service import document_service
            await document_service.ensure_project_indexed(project_id)
        except Exception as e:
            logger.error(f"Index check failed for project {project_id}: {e}")
        parts, _ = await graph_analytics.keyword_context_from_stored_text(
            project_id, topic, max_passages=limit, document_ids=document_ids or None,
        )
    return "\n\n".join(parts)


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    clean = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    start, end = clean.find("{"), clean.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(clean[start:end + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _llm_error(e: Exception) -> HTTPException:
    logger.error(f"LLM call failed: {e}")
    return HTTPException(502, RAGService._friendly_error(e))


# ============== Exam Tonight: plan ==============


class CramPlanRequest(BaseModel):
    project_id: str
    minutes: int = Field(..., ge=10, le=24 * 60)
    selected_documents: List[str] = []


async def _book_coverage(project_id: str, documents: List[Dict[str, Any]], topics: List[str]) -> Dict[str, float]:
    """Share of the book each topic covers; cached until the document set changes."""
    from services.document_service import document_service

    signature = hashlib.sha1(
        ("|".join(sorted(d["id"] for d in documents)) + "#" + "|".join(sorted(topics))).encode()
    ).hexdigest()
    key = f"__coverage__{signature[:16]}"
    cached = await _cache_get(project_id, key, "coverage")
    if cached:
        return cached

    texts = []
    for d in documents:
        text = await document_service.load_stored_text({**d, "project_id": project_id})
        if text:
            texts.append(text)
    if not texts:
        return {}
    coverage = await asyncio.to_thread(coverage_from_text, topics, texts)
    await _cache_put(project_id, key, "coverage", coverage)
    return coverage


async def _mastery(user_id: str, project_id: str) -> Dict[str, float]:
    """
    0..1 per topic: the learning engine's estimate of what the student knows
    now (evidence-weighted, faded by forgetting). Falls back to quiz accuracy
    and completed topics if the learner model is unavailable.
    """
    from services.user_data_service import user_data

    mastery: Dict[str, float] = {}
    try:
        for p in await performance_tracker.get_performance(user_id, project_id):
            correct, wrong = p.get("correct_count", 0), p.get("wrong_count", 0)
            total = correct + wrong
            if total:
                mastery[p["topic"]] = (correct / total) * min(1.0, total / 5)
    except Exception as e:
        logger.warning(f"Could not load performance for cram plan: {e}")
    for t in await user_data.get_learning_progress(user_id, project_id):
        mastery[t] = max(mastery.get(t, 0.0), 0.85)
    # The learner model wins wherever it has evidence
    try:
        from services.learning_engine import get_learning_engine, effective_mastery
        for t, state in (await get_learning_engine().load_states(user_id, project_id)).items():
            mastery[t] = round(effective_mastery(state), 3)
    except Exception as e:
        logger.warning(f"Learner model unavailable for cram plan: {e}")
    return mastery


@router.post("/cram/plan")
async def cram_plan(request: CramPlanRequest, current_user: dict = Depends(get_current_user)):
    await _require_project(request.project_id, current_user)

    documents = await knowledge_graph.load_project_documents(request.project_id)
    if request.selected_documents:
        wanted = set(request.selected_documents)
        documents = [d for d in documents if d["id"] in wanted]
    if not documents:
        return {"plan": None, "message": "Upload a document (and wait for it to finish processing) to build a plan."}

    path = await knowledge_graph.generate_learning_path(request.project_id, documents=documents)
    if not path:
        return {"plan": None, "message": "Topics for your documents are still being extracted. Try again in a minute."}

    topics = [p["topic"] for p in path]
    coverage = await _book_coverage(request.project_id, documents, topics)
    mastery = await _mastery(current_user["id"], request.project_id)
    plan = plan_session(path, request.minutes, coverage, mastery)
    return {"plan": plan}


# ============== Exam Tonight: cram card ==============


class CramCardRequest(BaseModel):
    project_id: str
    topic: str = Field(..., min_length=1, max_length=300)
    selected_documents: List[str] = []
    refresh: bool = False


def _clean_card(data: Dict[str, Any], topic: str) -> Dict[str, Any]:
    def strs(v, n):
        return [str(x) for x in (v or []) if str(x).strip()][:n] if isinstance(v, list) else []

    formulas = []
    for f in (data.get("formulas") or [])[:6]:
        if isinstance(f, dict) and f.get("expr"):
            formulas.append({"expr": str(f["expr"]), "meaning": str(f.get("meaning", ""))})
    checks = []
    for q in (data.get("quick_check") or [])[:3]:
        if not isinstance(q, dict):
            continue
        options = strs(q.get("options"), 4)
        try:
            idx = int(q.get("answer_index", 0))
        except (TypeError, ValueError):
            idx = 0
        if q.get("q") and len(options) >= 2 and 0 <= idx < len(options):
            checks.append({"q": str(q["q"]), "options": options, "answer_index": idx, "why": str(q.get("why", ""))})
    return {
        "topic": topic,
        "tldr": str(data.get("tldr", "")).strip(),
        "key_points": strs(data.get("key_points"), 6),
        "formulas": formulas,
        "example": str(data.get("example", "")).strip(),
        "memory_hook": str(data.get("memory_hook", "")).strip(),
        "exam_tip": str(data.get("exam_tip", "")).strip(),
        "mistakes": strs(data.get("mistakes"), 3),
        "quick_check": checks,
    }


@router.post("/cram/card")
async def cram_card(request: CramCardRequest, current_user: dict = Depends(get_current_user)):
    await _require_project(request.project_id, current_user)
    topic = request.topic.strip()

    books = await book_library.books_for_topic(request.project_id, topic, request.selected_documents)
    if not request.refresh:
        cached = await _cache_get(request.project_id, topic, "cram")
        if cached:
            return {"card": cached, "cached": True}
        # Someone else already studied this topic from the same book
        shared = await book_library.get_asset(books, topic, "cram")
        if shared:
            card = {**shared, "topic": topic}
            await _cache_put(request.project_id, topic, "cram", card)
            return {"card": card, "cached": True}

    metered(current_user, "cram")
    await usage.check(current_user["id"], "cram")
    context = await _topic_context(request.project_id, topic, request.selected_documents)
    prompt = f"""You are a brilliant exam coach. A student has very little time before their exam.
Teach the topic below so they understand it AND can score marks on it, using the book passages.

TOPIC: {topic}

BOOK PASSAGES:
{context[:7000] or "(no passages found - use standard textbook knowledge and keep it accurate)"}

Return ONLY valid JSON (no markdown) with this exact shape:
{{
  "tldr": "2-3 sentence plain-language explanation of the core idea",
  "key_points": ["4-6 short points that carry the marks"],
  "formulas": [{{"expr": "F = m·a", "meaning": "what each symbol means / when to use it"}}],
  "example": "one short worked example or concrete illustration, laid out for skimming: one item per line separated by \\n, each line 'Label: detail' (e.g. 'Performance: Car — good mileage; Fridge — even cooling')",
  "memory_hook": "a vivid mnemonic or analogy that makes it stick",
  "exam_tip": "how this is usually asked and how to answer it for full marks",
  "mistakes": ["1-3 common mistakes to avoid"],
  "quick_check": [
    {{"q": "question", "options": ["A", "B", "C", "D"], "answer_index": 0, "why": "one-line explanation"}}
  ]
}}
Rules: formulas may be [] if the topic has none; write formulas in plain text/Unicode (x², √, π, Σ, ·),
not LaTeX; give exactly 2 quick_check questions; keep the whole card readable in about 3 minutes.
Write for fast reading: short lines, no paragraph longer than 2 sentences, start key points with the
key term followed by ' — ', and use **bold** for at most one or two key terms per field."""

    # Topper cram cards come from the Deep model
    deep = (await usage.plan(current_user["id"])) == "topper"
    try:
        raw = await llm_service.chat_completion(
            [{"role": "user", "content": prompt}], temperature=0.3, max_tokens=2500, deep=deep
        )
    except Exception as e:
        raise _llm_error(e)

    data = _parse_json_object(raw)
    if not data:
        raise HTTPException(502, "The AI returned an unreadable card. Please try again.")
    card = _clean_card(data, topic)
    if not card["tldr"] and not card["key_points"]:
        raise HTTPException(502, "The AI returned an empty card. Please try again.")
    await _cache_put(request.project_id, topic, "cram", card)
    await book_library.put_asset(books, topic, "cram", card)
    await usage.charge(current_user["id"], "cram")
    return {"card": card, "cached": False}


# ============== Visual Lab ==============


class VisualRepair(BaseModel):
    html: str = Field(..., max_length=200_000)
    error: str = Field(..., max_length=2000)


class VisualizeRequest(BaseModel):
    project_id: str
    topic: str = Field(..., min_length=1, max_length=300)
    selected_documents: List[str] = []
    refresh: bool = False
    repair: Optional[VisualRepair] = None


MAX_VISUAL_BYTES = 120_000

VISUAL_PROMPT = """You are a brilliant teacher and creative front-end developer. Build ONE self-contained,
working, interactive HTML page that lets a student SEE and PLAY with the topic below.

TOPIC: {topic}

BOOK PASSAGES (the source of truth for content, examples and terminology):
{context}

STEP 1 - decide what kind of topic this is (from the topic AND the passages), then build the
interactive that genuinely fits it. NEVER force equations, graphs or derivations onto a topic that
has none. Inventing formulas or "quotients" for ideas, behaviour, history or literature is WRONG.

- Physics / chemistry / engineering / quantitative: a live simulation (<canvas> + requestAnimationFrame
  or SVG) driven by the REAL equations, sliders for the parameters with units, live readouts,
  Formulas (every symbol explained), a short step-by-step Derivation, Why it happens, Try this.
- Maths / statistics / algorithms / CS: a manipulable visual (draggable points, step-through
  stepper, live plot) with the real rules, worked steps and what changes when you change inputs.
- Biology / medicine / earth science: an animated, labelled process or structure diagram the student
  can step through, hover/tap for parts, toggle states (e.g. healthy vs diseased).
- History / politics / economics stories: an interactive timeline or cause-and-effect map; tap events
  for who/what/why, and see consequences unfold.
- Self-help, strategy, psychology, philosophy, ethics, business, law, literature (e.g. "The 48 Laws of
  Power"): NO equations and NO graphs of made-up quantities. Build something like:
    * a scenario simulator: a realistic situation, 2-4 choices, each revealing what happens and
      which principle it shows (branching story, with a "replay" button);
    * a "spot the principle" mini game with real examples (from the book where possible);
    * do / don't cards that flip, a before-vs-after comparison, a concept map of related ideas;
    * real historical or everyday examples the book uses, and the exceptions/when it backfires.
- Languages / grammar: interactive sentence builders, fill-the-gap with instant feedback.
Mix formats if it helps, but every element must be faithful to the topic and the passages.

STEP 2 - the page contains:
1. A title and one line saying what the student will explore.
2. The main interactive (the centrepiece, chosen above), with clear controls and instant feedback.
3. "The idea": the core explanation in plain words, grounded in the passages.
4. A section that fits the subject: Formulas + Derivation (quantitative topics only), OR Key steps,
   OR Real examples, OR When it backfires / common mistakes.
5. "Try this": 3 short guided things to do with the interactive.

Hard rules:
- Single file. Inline <style> and <script> only. NO external scripts, fonts, images, CDNs or
  network requests (they are blocked). Draw everything yourself (CSS, SVG, canvas, emoji are fine).
- Any maths in HTML/Unicode (x², x<sub>0</sub>, √, π, θ, Δ), no LaTeX.
- Must run without errors in a sandboxed iframe (no localStorage, alert, prompt, forms, popups).
- Responsive: fits 360px-1200px wide and works with touch; canvases handle devicePixelRatio.
- Clean, modern look: dark background #0f172a, cards, rounded corners, accent #f59e0b, readable 15px text.
- Keep it under 25 KB. Factually correct and true to the book; don't invent facts or numbers.

Return ONLY the HTML document, starting with <!DOCTYPE html>. No markdown fences, no commentary."""

# Bumped when the prompt changes so earlier builds (e.g. equations for a non-science book)
# are rebuilt instead of served from the cache
VISUAL_KIND = "visual_v2"

REPAIR_PROMPT = """This interactive HTML lesson about "{topic}" throws an error in the browser:

ERROR: {error}

Fix the bug(s) and return the COMPLETE corrected HTML document (single file, inline CSS/JS, no external
resources, no LaTeX). Return ONLY the HTML, starting with <!DOCTYPE html>.

HTML:
{html}"""


def _sanitize_html(raw: str) -> Optional[str]:
    """Extract the HTML document and strip anything that loads external code."""
    if not raw:
        return None
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw.strip())
    start = text.lower().find("<!doctype")
    if start == -1:
        start = text.lower().find("<html")
    if start == -1:
        return None
    end = text.lower().rfind("</html>")
    html = text[start:end + len("</html>")] if end > start else text[start:]
    # External scripts/stylesheets/frames would be blocked by the CSP anyway; drop them so
    # the page doesn't wait on them.
    html = re.sub(r"<script[^>]*\bsrc\s*=[^>]*>\s*</script>", "", html, flags=re.I)
    html = re.sub(r"<link[^>]*\bhref\s*=\s*[\"']?https?:[^>]*>", "", html, flags=re.I)
    html = re.sub(r"<(iframe|object|embed)\b[^>]*>.*?</\1>", "", html, flags=re.I | re.S)
    if len(html.encode("utf-8")) > MAX_VISUAL_BYTES or "<script" not in html.lower():
        return None
    return html


@router.post("/visualize")
async def visualize(request: VisualizeRequest, current_user: dict = Depends(get_current_user)):
    await _require_project(request.project_id, current_user)
    topic = request.topic.strip()

    books = await book_library.books_for_topic(request.project_id, topic, request.selected_documents)
    if request.repair:
        prompt = REPAIR_PROMPT.format(topic=topic, error=request.repair.error, html=request.repair.html[:60000])
    else:
        if not request.refresh:
            cached = await _cache_get(request.project_id, topic, VISUAL_KIND)
            if cached and cached.get("html"):
                return {"html": cached["html"], "topic": topic, "cached": True}
            # Same topic already built from the same book by another student
            shared = await book_library.get_asset(books, topic, VISUAL_KIND)
            if shared and shared.get("html"):
                await _cache_put(request.project_id, topic, VISUAL_KIND, {"html": shared["html"]})
                return {"html": shared["html"], "topic": topic, "cached": True}
        # New build (repairs are free); cached and shared ones cost nothing
        metered(current_user, "visual")
        await usage.check(current_user["id"], "visual")
        context = await _topic_context(request.project_id, topic, request.selected_documents, limit=6)
        prompt = VISUAL_PROMPT.format(
            topic=topic,
            context=context[:5000] or "(no passages found - use standard textbook knowledge)",
        )

    try:
        # Simulations need real coding ability: always the Deep model (and they're
        # shared across students with the same book, so each is paid for once)
        raw = await llm_service.chat_completion(
            [{"role": "user", "content": prompt}], temperature=0.4, max_tokens=12000, deep=True
        )
    except Exception as e:
        raise _llm_error(e)

    html = _sanitize_html(raw)
    if not html:
        raise HTTPException(502, "The AI couldn't build a working simulation this time. Please try again.")
    await _cache_put(request.project_id, topic, VISUAL_KIND, {"html": html})
    # Shared copy is stored as an .html file; repairs replace a broken one for everyone
    await book_library.put_asset(books, topic, VISUAL_KIND, {"html": html})
    if not request.repair:
        await usage.charge(current_user["id"], "visual")
    return {"html": html, "topic": topic, "cached": False}
