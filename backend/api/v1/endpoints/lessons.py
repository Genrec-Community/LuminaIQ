"""
Structured lessons — the teaching unit the learning engine sends a student to.

Each lesson follows the sequence that makes knowledge stick:
  1. Diagnose   – two targeted questions; strong answers skip the explanation
  2. Model      – the core idea, why it exists, how it connects to what they know
  3. Worked     – a worked example, then a guided one with the support faded
  4. Retrieve   – explain it from memory (graded against key points)
  5. Apply      – unfamiliar scenarios, plus a contrast with an easily
                  confused topic (from the knowledge graph's CONTRASTS_WITH)
  6. Schedule   – the learner model sets the next review

Every answer is evidence for the learner model (services.learning_engine).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
from api.v1.endpoints.study_modes import (
    _cache_get, _cache_put, _llm_error, _parse_json_object, _require_project, _topic_context,
)
from services.learning_engine import edge_kind, get_learning_engine
from services.llm_service import llm_service
from services.usage_service import metered
from utils.logger import logger

router = APIRouter()

LESSON_KIND = "lesson_v1"


class LessonRequest(BaseModel):
    project_id: str
    topic: str = Field(..., min_length=1, max_length=300)
    selected_documents: List[str] = []
    refresh: bool = False


class GradeRequest(BaseModel):
    project_id: str
    topic: str = Field(..., min_length=1, max_length=300)
    prompt: str = Field(..., max_length=1000)
    answer: str = Field(..., min_length=1, max_length=4000)
    key_points: List[str] = Field(default_factory=list, max_length=8)


def _mcq(q: Any, difficulty: str) -> Optional[Dict[str, Any]]:
    if not isinstance(q, dict) or not q.get("q"):
        return None
    options = [str(o) for o in (q.get("options") or []) if str(o).strip()][:4]
    try:
        idx = int(q.get("answer_index", 0))
    except (TypeError, ValueError):
        return None
    if len(options) < 2 or not 0 <= idx < len(options):
        return None
    return {"q": str(q["q"]), "options": options, "answer_index": idx, "why": str(q.get("why", "")),
            "difficulty": str(q.get("difficulty") or difficulty)}


def _clean_lesson(data: Dict[str, Any], topic: str, contrast_with: Optional[str]) -> Dict[str, Any]:
    def text(v) -> str:
        return str(v or "").strip()

    model = data.get("model") or {}
    worked = data.get("worked_example") or {}
    guided = data.get("guided") or {}
    recall = data.get("recall") or {}
    contrast = data.get("contrast") or {}
    diagnose = [q for q in (_mcq(x, d) for x, d in zip((data.get("diagnose") or [])[:2], ("medium", "hard"))) if q]
    apply = [q for q in (_mcq(x, "hard") for x in (data.get("apply") or [])[:2]) if q]
    contrast_q = _mcq(contrast, "hard") if contrast_with else None
    return {
        "topic": topic,
        "diagnose": diagnose,
        "model": {
            "core": text(model.get("core")),
            "why": text(model.get("why")),
            "connects": text(model.get("connects")),
            "example": text(model.get("example")),
        },
        "worked_example": {
            "problem": text(worked.get("problem")),
            "steps": [text(s) for s in (worked.get("steps") or []) if text(s)][:6],
            "takeaway": text(worked.get("takeaway")),
        },
        "guided": {"problem": text(guided.get("problem")), "hint": text(guided.get("hint")),
                   "solution": text(guided.get("solution"))},
        "recall": {"prompt": text(recall.get("prompt")) or f"Explain {topic} in your own words.",
                   "key_points": [text(k) for k in (recall.get("key_points") or []) if text(k)][:5]},
        "apply": apply,
        "contrast": ({**contrast_q, "with": contrast_with} if contrast_q else None),
    }


async def _neighbours(project_id: str, topic: str) -> Dict[str, List[str]]:
    """Prerequisites, explicit contrasts and other connected topics from the graph."""
    out: Dict[str, List[str]] = {"requires": [], "contrasts": [], "connected": []}
    try:
        for e in await get_learning_engine().load_edges(project_id):
            kind = edge_kind(e)
            u, v = e.get("from_topic"), e.get("to_topic")
            if topic not in (u, v):
                continue
            other = v if u == topic else u
            if kind == "CONTRASTS_WITH":
                out["contrasts"].append(other)
            elif kind == "REQUIRES" and v == topic:
                out["requires"].append(other)
            else:
                out["connected"].append(other)
    except Exception as e:
        logger.debug(f"Lesson graph lookup skipped: {e}")
    return out


@router.post("/lesson")
async def lesson(request: LessonRequest, current_user: dict = Depends(get_current_user)):
    await _require_project(request.project_id, current_user)
    topic = request.topic.strip()
    if not request.refresh:
        cached = await _cache_get(request.project_id, topic, LESSON_KIND)
        if cached:
            return {"lesson": cached, "cached": True}

    metered(current_user, "tools")
    graph = await _neighbours(request.project_id, topic)
    contrast_pool = graph["contrasts"] or graph["connected"]
    context = await _topic_context(request.project_id, topic, request.selected_documents)

    contrast_line = (
        f"EASILY CONFUSED CANDIDATES: {', '.join(contrast_pool[:8])}\n"
        "Pick the ONE most easily confused with the topic for the contrast question, or use null if none truly is."
        if contrast_pool else "No contrast topic: set \"contrast\" to null."
    )
    prompt = f"""You are a master teacher. Build a short lesson that makes the topic below genuinely
understood and remembered, grounded in the material.

TOPIC: {topic}
BUILDS ON: {', '.join(graph['requires'][:5]) or 'nothing in particular'}
{contrast_line}

MATERIAL:
{context[:7000] or "(no passages found - use accurate standard knowledge)"}

Adapt to the subject: for maths/science/technical topics the worked example solves a problem step by step;
for humanities, business, law, self-help etc. it analyses a concrete case or scenario step by step.
Never invent formulas a non-quantitative subject doesn't have.

Return ONLY valid JSON (no markdown):
{{
  "diagnose": [
    {{"q": "question checking real understanding", "options": ["A","B","C","D"], "answer_index": 0, "why": "one line", "difficulty": "medium"}},
    {{"q": "harder question that only someone who understands could answer", "options": ["A","B","C","D"], "answer_index": 0, "why": "one line", "difficulty": "hard"}}
  ],
  "model": {{
    "core": "the core idea in 2-3 plain sentences",
    "why": "why this idea exists / what problem it solves, 1-2 sentences",
    "connects": "how it builds on what the learner already knows, 1-2 sentences",
    "example": "one accessible, concrete everyday example"
  }},
  "worked_example": {{"problem": "a realistic problem or case", "steps": ["step 1", "step 2", "step 3"], "takeaway": "the general lesson"}},
  "guided": {{"problem": "a similar problem for the learner to try", "hint": "a nudge, not the answer", "solution": "the full answer"}},
  "recall": {{"prompt": "ask them to explain the idea from memory in their own words", "key_points": ["3-5 points a good explanation covers"]}},
  "apply": [
    {{"q": "an UNFAMILIAR scenario where they must use the idea", "options": ["A","B","C","D"], "answer_index": 0, "why": "one line"}},
    {{"q": "another unfamiliar scenario, different from the first", "options": ["A","B","C","D"], "answer_index": 0, "why": "one line"}}
  ],
  "contrast": {{"with": "the chosen topic", "q": "a scenario: is this {topic} or <the other topic>? why?", "options": ["…"], "answer_index": 0, "why": "the distinguishing feature"}}
}}
Rules: plain text (Unicode for any maths, no LaTeX); vary which option is correct; keep every field short
and skimmable; the whole lesson should take about 8 minutes."""

    try:
        raw = await llm_service.chat_completion(
            [{"role": "user", "content": prompt}], temperature=0.35, max_tokens=3500
        )
    except Exception as e:
        raise _llm_error(e)
    data = _parse_json_object(raw)
    if not data:
        raise HTTPException(502, "The AI returned an unreadable lesson. Please try again.")

    chosen = (data.get("contrast") or {}).get("with") if isinstance(data.get("contrast"), dict) else None
    match = next((t for t in contrast_pool if chosen and t.lower() == str(chosen).lower()), None)
    result = _clean_lesson(data, topic, match)
    if not result["model"]["core"] or not result["apply"]:
        raise HTTPException(502, "The AI returned an incomplete lesson. Please try again.")
    await _cache_put(request.project_id, topic, LESSON_KIND, result)
    return {"lesson": result, "cached": False}


@router.post("/lesson/grade")
async def grade_recall(request: GradeRequest, current_user: dict = Depends(get_current_user)):
    """Grade an explanation written from memory and record it as recall evidence."""
    await _require_project(request.project_id, current_user)
    metered(current_user, "tools")
    points = "\n".join(f"- {p}" for p in request.key_points) or "- (judge against accurate knowledge of the topic)"
    prompt = f"""Grade a student's explanation written from memory. Be fair and encouraging, but strict
about correctness: reward understanding in their own words, not exact wording.

TOPIC: {request.topic}
QUESTION: {request.prompt}
KEY POINTS A GOOD ANSWER COVERS:
{points}

STUDENT'S ANSWER:
{request.answer[:3000]}

Return ONLY JSON: {{"score": 0.0-1.0, "covered": ["key points they got"], "missing": ["key points missed or wrong"],
"misconception": "a wrong belief in the answer, or empty", "feedback": "2 short sentences: what was good, what to fix"}}"""
    try:
        raw = await llm_service.chat_completion([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=800, light=True)
    except Exception as e:
        raise _llm_error(e)
    data = _parse_json_object(raw) or {}
    try:
        score = max(0.0, min(1.0, float(data.get("score", 0))))
    except (TypeError, ValueError):
        score = 0.0

    def strs(v):
        return [str(x) for x in (v or []) if str(x).strip()][:6] if isinstance(v, list) else []

    update: Dict[str, Any] = {}
    try:
        recorded = await get_learning_engine().record(current_user["id"], request.project_id, [{
            "topic": request.topic, "correct": score >= 0.6, "kind": "recall",
            "difficulty": "hard" if score >= 0.85 else "medium", "source": "lesson",
        }])
        update = recorded.get("updated", {}).get(request.topic, {})
    except Exception as e:
        logger.warning(f"Recall evidence not recorded: {e}")
    return {
        "score": round(score, 2),
        "covered": strs(data.get("covered")),
        "missing": strs(data.get("missing")),
        "misconception": str(data.get("misconception") or "").strip(),
        "feedback": str(data.get("feedback") or "").strip(),
        "mastery": update,
    }
