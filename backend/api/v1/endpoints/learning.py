"""
Learning API Endpoints - Adaptive Learning System

Endpoints:
Performance:
- POST /performance/record - Record quiz performance
- GET /performance/{project_id} - Get performance for project

Weakness Detection:
- GET /weak-topics/{project_id} - Get weak topics

Spaced Repetition:
- POST /review-cards - Create review cards
- POST /review-cards/from-quiz - Create cards from quiz results
- GET /review-cards/due - Get due cards
- POST /review-cards/{card_id}/review - Record a review
- DELETE /review-cards/{card_id} - Delete a card

Knowledge Graph:
- POST /knowledge-graph/{project_id}/build - Build graph from topics
- GET /knowledge-graph/{project_id} - Get full graph
- GET /knowledge-graph/{project_id}/related/{topic} - Find related topics
- GET /knowledge-graph/{project_id}/learning-path - Generate learning path
- GET /knowledge-graph/{project_id}/prerequisites/{topic} - Get prerequisites
- GET /knowledge-graph/{project_id}/stats - Get graph statistics

Dashboard:
- GET /dashboard/{project_id} - Get learning dashboard
- GET /stats - Get overall learning statistics
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from services.learning_service import (
    learning_service,
    performance_tracker,
    weakness_detector,
    spaced_repetition,
)
from services.knowledge_graph_service import knowledge_graph
from services.llm_service import llm_service
from api.deps import get_current_user
from utils.logger import logger
import json

router = APIRouter()


# ============== Schemas ==============


class RecordPerformanceRequest(BaseModel):
    project_id: str
    topic: str
    correct: int = Field(..., ge=0)
    wrong: int = Field(..., ge=0)


class PerformanceResponse(BaseModel):
    topic: str
    correct_count: int
    wrong_count: int
    accuracy: float
    last_attempt: Optional[str]


class WeakTopicResponse(BaseModel):
    topic: str
    weakness_score: float
    correct_count: int
    wrong_count: int
    last_attempt: Optional[str]
    recommendation: str


class CreateCardRequest(BaseModel):
    project_id: str
    topic: str
    question: str
    answer: str


class CreateCardsFromQuizRequest(BaseModel):
    project_id: str
    topic: str
    questions: List[Dict[str, Any]]
    wrong_only: bool = True


class RecordReviewRequest(BaseModel):
    quality: int = Field(..., ge=0, le=5, description="0=blackout, 5=perfect recall")


class ReviewCardResponse(BaseModel):
    id: str
    topic: str
    question: str
    answer: str
    next_review: str
    interval_days: int
    overdue_days: Optional[int] = 0


class DashboardResponse(BaseModel):
    overall: Dict[str, Any]
    weak_topics: List[Dict[str, Any]]
    due_cards: List[Dict[str, Any]]
    review_stats: Dict[str, Any]
    performance_by_topic: List[Dict[str, Any]]


# ============== Performance Endpoints ==============


@router.post("/performance/record")
async def record_performance(
    request: RecordPerformanceRequest, current_user: dict = Depends(get_current_user)
):
    """
    Record quiz performance for a topic.

    This should be called after a user completes a quiz.
    """
    try:
        user_id = current_user["id"]

        result = await performance_tracker.record_performance(
            user_id=user_id,
            project_id=request.project_id,
            topic=request.topic,
            correct=request.correct,
            wrong=request.wrong,
        )

        return {
            "success": True,
            "message": f"Recorded {request.correct} correct, {request.wrong} wrong for '{request.topic}'",
            "data": result,
        }

    except Exception as e:
        logger.error(f"Error recording performance: {e}")
        raise HTTPException(500, str(e))


@router.get("/performance/{project_id}")
async def get_performance(
    project_id: str,
    topic: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get performance records for a project, optionally filtered by topic."""
    try:
        user_id = current_user["id"]

        records = await performance_tracker.get_performance(
            user_id=user_id, project_id=project_id, topic=topic
        )

        # Add calculated accuracy
        for record in records:
            total = record.get("correct_count", 0) + record.get("wrong_count", 0)
            record["accuracy"] = round(
                (record.get("correct_count", 0) / total * 100) if total > 0 else 0, 1
            )

        return {"performance": records}

    except Exception as e:
        logger.error(f"Error getting performance: {e}")
        raise HTTPException(500, str(e))


# ============== Weakness Detection Endpoints ==============


@router.get("/weak-topics/{project_id}")
async def get_weak_topics(
    project_id: str,
    top_k: int = 5,
    threshold: float = 0.3,
    current_user: dict = Depends(get_current_user),
):
    """
    Get top-K weakest topics for a project.

    Uses Min-Heap algorithm for efficient top-K selection.

    Args:
        top_k: Number of weak topics to return (default 5)
        threshold: Minimum weakness score to include (0.0-1.0, default 0.3)
    """
    try:
        user_id = current_user["id"]

        weak_topics = await weakness_detector.get_weak_topics(
            user_id=user_id, project_id=project_id, top_k=top_k, threshold=threshold
        )

        return {"weak_topics": weak_topics, "count": len(weak_topics)}

    except Exception as e:
        logger.error(f"Error getting weak topics: {e}")
        raise HTTPException(500, str(e))


# ============== Spaced Repetition Endpoints ==============


@router.post("/review-cards")
async def create_review_card(
    request: CreateCardRequest, current_user: dict = Depends(get_current_user)
):
    """Create a single review card for spaced repetition."""
    try:
        user_id = current_user["id"]

        card = await spaced_repetition.create_review_card(
            user_id=user_id,
            project_id=request.project_id,
            topic=request.topic,
            question=request.question,
            answer=request.answer,
        )

        return {"success": True, "card": card}

    except Exception as e:
        logger.error(f"Error creating review card: {e}")
        raise HTTPException(500, str(e))


@router.post("/review-cards/from-quiz")
async def create_cards_from_quiz(
    request: CreateCardsFromQuizRequest, current_user: dict = Depends(get_current_user)
):
    """
    Create review cards from quiz results.

    By default, only creates cards for incorrectly answered questions.
    Set wrong_only=False to create cards for all questions.
    """
    try:
        user_id = current_user["id"]

        cards = await spaced_repetition.create_cards_from_quiz(
            user_id=user_id,
            project_id=request.project_id,
            topic=request.topic,
            questions=request.questions,
            wrong_only=request.wrong_only,
        )

        return {"success": True, "cards_created": len(cards), "cards": cards}

    except Exception as e:
        logger.error(f"Error creating cards from quiz: {e}")
        raise HTTPException(500, str(e))


@router.get("/review-cards/due")
async def get_due_cards(
    project_id: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """
    Get review cards due for study.

    Returns cards ordered by priority (most overdue first).
    Uses Priority Queue (Min-Heap) algorithm internally.
    """
    try:
        user_id = current_user["id"]

        cards = await spaced_repetition.get_due_cards(
            user_id=user_id, project_id=project_id, limit=limit
        )

        return {"due_cards": cards, "count": len(cards)}

    except Exception as e:
        logger.error(f"Error getting due cards: {e}")
        raise HTTPException(500, str(e))


@router.post("/review-cards/{card_id}/review")
async def record_review(
    card_id: str,
    request: RecordReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Record a review for a card using SM-2 algorithm.

    Quality scale:
    - 0: Complete blackout, no recall at all
    - 1: Incorrect, but recognized the answer
    - 2: Incorrect, but answer seemed easy to recall
    - 3: Correct answer with serious difficulty
    - 4: Correct answer with some hesitation
    - 5: Perfect recall, no hesitation
    """
    try:
        result = await spaced_repetition.record_review(
            card_id=card_id, quality=request.quality
        )

        return {"success": True, "result": result}

    except Exception as e:
        logger.error(f"Error recording review: {e}")
        raise HTTPException(500, str(e))


@router.delete("/review-cards/{card_id}")
async def delete_review_card(
    card_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete a review card."""
    try:
        success = await spaced_repetition.delete_card(card_id)

        if success:
            return {"success": True, "message": "Card deleted"}
        else:
            raise HTTPException(500, "Failed to delete card")

    except Exception as e:
        logger.error(f"Error deleting card: {e}")
        raise HTTPException(500, str(e))


@router.get("/review-stats")
async def get_review_stats(
    project_id: Optional[str] = None, current_user: dict = Depends(get_current_user)
):
    """Get spaced repetition statistics."""
    try:
        user_id = current_user["id"]

        stats = await spaced_repetition.get_review_stats(
            user_id=user_id, project_id=project_id
        )

        return {"stats": stats}

    except Exception as e:
        logger.error(f"Error getting review stats: {e}")
        raise HTTPException(500, str(e))


# ============== Dashboard Endpoint ==============


@router.get("/dashboard/{project_id}")
async def get_learning_dashboard(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get comprehensive learning dashboard.

    Returns:
    - Overall performance summary
    - Top 5 weak topics
    - Due review cards
    - Spaced repetition statistics
    - Recent topic performance
    """
    try:
        user_id = current_user["id"]

        dashboard = await learning_service.get_learning_dashboard(
            user_id=user_id, project_id=project_id
        )

        return dashboard

    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        raise HTTPException(500, str(e))


@router.get("/stats/all")
async def get_all_stats(current_user: dict = Depends(get_current_user)):
    """Get overall learning statistics across all projects."""
    try:
        user_id = current_user["id"]

        # Get all performance records
        performance = await performance_tracker.get_all_user_performance(user_id)

        # Get review stats
        review_stats = await spaced_repetition.get_review_stats(user_id)

        # Calculate totals
        total_correct = sum(p.get("correct_count", 0) for p in performance)
        total_wrong = sum(p.get("wrong_count", 0) for p in performance)
        total_attempts = total_correct + total_wrong

        # Group by project
        by_project = {}
        for p in performance:
            pid = p.get("project_id")
            if pid not in by_project:
                by_project[pid] = {"correct": 0, "wrong": 0, "topics": 0}
            by_project[pid]["correct"] += p.get("correct_count", 0)
            by_project[pid]["wrong"] += p.get("wrong_count", 0)
            by_project[pid]["topics"] += 1

        return {
            "overall": {
                "total_topics_studied": len(performance),
                "total_questions_attempted": total_attempts,
                "overall_accuracy": round(
                    (total_correct / total_attempts * 100) if total_attempts > 0 else 0,
                    1,
                ),
                "total_correct": total_correct,
                "total_wrong": total_wrong,
                "projects_studied": len(by_project),
            },
            "review_stats": review_stats,
            "by_project": by_project,
        }

    except Exception as e:
        logger.error(f"Error getting all stats: {e}")
        raise HTTPException(500, str(e))


# ============== Knowledge Graph Endpoints ==============


class BuildGraphRequest(BaseModel):
    topics: List[str]
    force_rebuild: bool = False


class AddRelationRequest(BaseModel):
    from_topic: str
    to_topic: str
    relation_type: str = Field(
        default="related", description="Type: prerequisite, related, or subtopic"
    )
    weight: float = Field(default=0.5, ge=0.1, le=1.0)


@router.post("/knowledge-graph/{project_id}/build")
async def build_knowledge_graph(
    project_id: str,
    request: BuildGraphRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Build knowledge graph from document topics.

    Uses LLM to identify relationships between topics:
    - prerequisite: Topic A should be learned before Topic B
    - related: Topics are related (bidirectional)
    - subtopic: Topic A is a broader category containing Topic B

    DSA: Adjacency List graph representation
    """
    try:
        result = await knowledge_graph.build_graph_from_topics(
            project_id=project_id,
            topics=request.topics,
            force_rebuild=request.force_rebuild,
        )

        return result

    except Exception as e:
        logger.error(f"Error building knowledge graph: {e}")
        raise HTTPException(500, str(e))


@router.post("/knowledge-graph/{project_id}/relation")
async def add_relation(
    project_id: str,
    request: AddRelationRequest,
    current_user: dict = Depends(get_current_user),
):
    """Manually add a relationship between topics."""
    try:
        result = await knowledge_graph.add_relationship(
            project_id=project_id,
            from_topic=request.from_topic,
            to_topic=request.to_topic,
            relation_type=request.relation_type,
            weight=request.weight,
        )

        return {"success": True, "relation": result}

    except Exception as e:
        logger.error(f"Error adding relation: {e}")
        raise HTTPException(500, str(e))


@router.get("/knowledge-graph/{project_id}")
async def get_knowledge_graph(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get full knowledge graph for visualization.

    Returns nodes and edges in a format suitable for graph libraries.
    """
    try:
        graph = await knowledge_graph.get_full_graph(project_id)
        stats = await knowledge_graph.get_graph_stats(project_id)

        return {"graph": graph, "stats": stats}

    except Exception as e:
        logger.error(f"Error getting knowledge graph: {e}")
        raise HTTPException(500, str(e))


@router.get("/knowledge-graph/{project_id}/related/{topic}")
async def get_related_topics(
    project_id: str,
    topic: str,
    max_distance: int = 2,
    current_user: dict = Depends(get_current_user),
):
    """
    Find topics related to a given topic.

    Uses Breadth-First Search (BFS) to find topics within max_distance hops.

    DSA: BFS - O(V + E) time complexity
    """
    try:
        related = await knowledge_graph.find_related_topics(
            project_id=project_id, topic=topic, max_distance=max_distance
        )

        return {"topic": topic, "related": related, "count": len(related)}

    except Exception as e:
        logger.error(f"Error getting related topics: {e}")
        raise HTTPException(500, str(e))


@router.get("/knowledge-graph/{project_id}/prerequisites/{topic}")
async def get_topic_prerequisites(
    project_id: str, topic: str, current_user: dict = Depends(get_current_user)
):
    """Get prerequisite topics that should be learned before this topic."""
    try:
        prerequisites = await knowledge_graph.get_prerequisites(
            project_id=project_id, topic=topic
        )

        dependents = await knowledge_graph.get_dependents(
            project_id=project_id, topic=topic
        )

        return {
            "topic": topic,
            "prerequisites": prerequisites,
            "unlocks": dependents,  # Topics that become available after learning this
        }

    except Exception as e:
        logger.error(f"Error getting prerequisites: {e}")
        raise HTTPException(500, str(e))


@router.get("/knowledge-graph/{project_id}/learning-path")
async def get_learning_path(
    project_id: str,
    target_topics: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate optimal learning path using Topological Sort.

    DSA: Kahn's Algorithm - O(V + E) time complexity

    If target_topics provided (comma-separated), generates path to learn those specific topics.
    Otherwise, generates path for all topics.
    """
    try:
        targets = None
        if target_topics:
            targets = [t.strip() for t in target_topics.split(",") if t.strip()]

        path = await knowledge_graph.generate_learning_path(
            project_id=project_id, target_topics=targets
        )

        return {
            "learning_path": path,
            "total_topics": len(path),
            "target_topics": targets,
        }

    except Exception as e:
        logger.error(f"Error generating learning path: {e}")
        # Return empty path instead of 500 error for better UX
        return {
            "learning_path": [],
            "total_topics": 0,
            "target_topics": None,
            "error": str(e),
        }


@router.get("/knowledge-graph/{project_id}/stats")
async def get_graph_stats(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """Get statistics about the knowledge graph."""
    try:
        stats = await knowledge_graph.get_graph_stats(project_id)
        return {"stats": stats}

    except Exception as e:
        logger.error(f"Error getting graph stats: {e}")
        raise HTTPException(500, str(e))


@router.get("/suggested-topic/{project_id}")
async def get_suggested_topic(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get the next suggested topic to study based on:
    1. Learning path order (topological sort)
    2. User's performance (skip mastered topics, prioritize weak ones)

    Returns the best topic to study next.
    """
    try:
        user_id = current_user["id"]

        # Get learning path
        path = await knowledge_graph.generate_learning_path(project_id)

        if not path:
            return {
                "suggested_topic": None,
                "reason": "No learning path available. Upload documents to generate topics.",
            }

        # Get user's performance
        performance = await performance_tracker.get_performance(user_id, project_id)

        # Create a map of topic -> performance
        perf_map = {}
        for p in performance:
            total = p.get("correct_count", 0) + p.get("wrong_count", 0)
            accuracy = (p.get("correct_count", 0) / total * 100) if total > 0 else 0
            perf_map[p["topic"]] = {
                "accuracy": accuracy,
                "attempts": total,
                "mastered": accuracy >= 80
                and total >= 5,  # 80%+ with at least 5 attempts
            }

        # Find the first non-mastered topic in order, prioritizing weak topics
        weak_topics = []
        unstudied_topics = []

        for item in path:
            topic = item["topic"]
            if topic in perf_map:
                if not perf_map[topic]["mastered"]:
                    if perf_map[topic]["accuracy"] < 60:
                        weak_topics.append(
                            {
                                "topic": topic,
                                "order": item["order"],
                                "accuracy": perf_map[topic]["accuracy"],
                                "reason": "Needs improvement",
                            }
                        )
            else:
                # Not studied yet
                unstudied_topics.append(
                    {
                        "topic": topic,
                        "order": item["order"],
                        "reason": "Not studied yet",
                    }
                )

        # Priority: Weak topics first (in learning order), then unstudied topics
        if weak_topics:
            suggested = weak_topics[0]
            return {
                "suggested_topic": suggested["topic"],
                "reason": f"Needs improvement (accuracy: {suggested['accuracy']:.0f}%)",
                "order": suggested["order"],
                "type": "weak",
            }
        elif unstudied_topics:
            suggested = unstudied_topics[0]
            return {
                "suggested_topic": suggested["topic"],
                "reason": "Next topic in learning path",
                "order": suggested["order"],
                "type": "new",
            }
        else:
            return {
                "suggested_topic": None,
                "reason": "All topics mastered! Great job!",
                "type": "complete",
            }

    except Exception as e:
        logger.error(f"Error getting suggested topic: {e}")
        return {
            "suggested_topic": None,
            "reason": f"Error generating suggestion: {str(e)}",
            "type": "error",
        }


# ============== Mindmap Generation ==============


class GenerateMindmapRequest(BaseModel):
    project_id: str
    topic: str
    selected_documents: List[str] = []


@router.post("/mindmap/generate")
async def generate_mindmap(
    request: GenerateMindmapRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a hierarchical mindmap for a specific topic using RAG context.

    Returns a tree structure with the topic as root, main branches as subtopics,
    and leaf nodes as key details/concepts.
    """
    try:
        # 1. Retrieve relevant document chunks for this topic using RAG
        collection_name = f"project_{request.project_id}"
        from services.qdrant_service import qdrant_service
        from services.embedding_service import embedding_service

        # Get embeddings for the topic query
        query_text = f"{request.topic}: key concepts, subtopics, and important details"
        query_vector = await embedding_service.generate_embedding(query_text)

        # Search for relevant chunks
        filter_conditions = None
        if request.selected_documents:
            filter_conditions = {"document_ids": request.selected_documents}

        results = await qdrant_service.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=8,
            filter_conditions=filter_conditions,
        )

        # Build context from chunks
        context_parts = []
        for result in results:
            text = result.get("text", "")
            if text:
                context_parts.append(text)

        context = "\n\n".join(context_parts) if context_parts else ""

        # 2. Generate mindmap using LLM
        prompt = f"""You are an expert educator. Create a detailed hierarchical mindmap for the topic below.
Use the provided context from study documents to make the mindmap accurate and comprehensive.

TOPIC: {request.topic}

DOCUMENT CONTEXT:
{context[:6000]}

TASK: Create a mindmap as a JSON tree structure with the topic as the root node.

RULES:
1. The root node is the main topic
2. Create 3-6 main branches (major subtopics/themes)
3. Each branch should have 2-4 leaf nodes (specific concepts, facts, or details)
4. Keep node labels concise (2-8 words each)
5. Make it educational and useful for study/review
6. Use information from the context when available

OUTPUT FORMAT - Return ONLY valid JSON, no markdown:
{{
  "label": "{request.topic}",
  "children": [
    {{
      "label": "Main Branch 1",
      "children": [
        {{"label": "Detail 1"}},
        {{"label": "Detail 2"}}
      ]
    }},
    {{
      "label": "Main Branch 2",
      "children": [
        {{"label": "Detail A"}},
        {{"label": "Detail B"}}
      ]
    }}
  ]
}}"""

        messages = [{"role": "user", "content": prompt}]
        response = await llm_service.chat_completion(
            messages, temperature=0.3, max_tokens=2000
        )

        # Parse the mindmap JSON
        mindmap_data = _parse_mindmap_json(response)

        if not mindmap_data:
            raise HTTPException(500, "Failed to generate mindmap structure")

        return {
            "success": True,
            "topic": request.topic,
            "mindmap": mindmap_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating mindmap: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(500, f"Failed to generate mindmap: {str(e)}")


def _parse_mindmap_json(response: str) -> Optional[Dict]:
    """Parse mindmap JSON from LLM response with repair logic."""
    if not response:
        return None

    clean = response.strip()

    # Remove markdown code blocks
    if clean.startswith("```"):
        lines = clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean = "\n".join(lines)

    # Find JSON object
    start = clean.find("{")
    if start == -1:
        return None

    end = clean.rfind("}")
    if end > start:
        json_str = clean[start : end + 1]
        try:
            data = json.loads(json_str)
            if "label" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Try repair: find last complete }
    json_str = clean[start:]
    last_brace = json_str.rfind("}")
    if last_brace > 0:
        truncated = json_str[: last_brace + 1]
        try:
            data = json.loads(truncated)
            if "label" in data:
                return data
        except json.JSONDecodeError:
            pass

    return None


# ============== Flashcard Generation ==============


class GenerateFlashcardsRequest(BaseModel):
    project_id: str
    topic: str
    num_cards: int = Field(default=8, ge=3, le=20)
    selected_documents: List[str] = []


@router.post("/flashcards/generate")
async def generate_flashcards(
    request: GenerateFlashcardsRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate study flashcards for a specific topic using RAG context.

    Returns a list of question/answer flashcard pairs focused on the topic.
    """
    try:
        # 1. Retrieve relevant document chunks for this topic
        collection_name = f"project_{request.project_id}"
        from services.qdrant_service import qdrant_service
        from services.embedding_service import embedding_service

        query_text = f"{request.topic}: important facts, definitions, and key concepts"
        query_vector = await embedding_service.generate_embedding(query_text)

        filter_conditions = None
        if request.selected_documents:
            filter_conditions = {"document_ids": request.selected_documents}

        results = await qdrant_service.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=8,
            filter_conditions=filter_conditions,
        )

        context_parts = []
        for result in results:
            text = result.get("text", "")
            if text:
                context_parts.append(text)

        context = "\n\n".join(context_parts) if context_parts else ""

        # 2. Generate flashcards using LLM
        prompt = f"""You are an expert educator creating study flashcards.

TOPIC: {request.topic}

DOCUMENT CONTEXT:
{context[:6000]}

TASK: Create exactly {request.num_cards} flashcards for studying this topic.

RULES:
1. Each card has a "front" (question/prompt) and "back" (answer/explanation)
2. Cover different aspects of the topic (definitions, concepts, relationships, applications)
3. Questions should be clear and specific
4. Answers should be concise but complete (1-3 sentences)
5. Mix question types: "What is...", "How does...", "Why is...", "Compare...", "Define..."
6. Use information from the provided context
7. Make cards progressively harder

OUTPUT FORMAT - Return ONLY valid JSON array, no markdown:
[
  {{"front": "What is X?", "back": "X is..."}},
  {{"front": "How does Y work?", "back": "Y works by..."}}
]"""

        messages = [{"role": "user", "content": prompt}]
        response = await llm_service.chat_completion(
            messages, temperature=0.4, max_tokens=3000
        )

        # Parse the flashcards JSON
        flashcards = _parse_flashcards_json(response)

        if not flashcards:
            raise HTTPException(500, "Failed to generate flashcards")

        return {
            "success": True,
            "topic": request.topic,
            "flashcards": flashcards,
            "count": len(flashcards),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating flashcards: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(500, f"Failed to generate flashcards: {str(e)}")


def _parse_flashcards_json(response: str) -> Optional[List[Dict]]:
    """Parse flashcards JSON array from LLM response."""
    if not response:
        return None

    clean = response.strip()

    # Remove markdown code blocks
    if clean.startswith("```"):
        lines = clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean = "\n".join(lines)

    # Find JSON array
    start = clean.find("[")
    if start == -1:
        return None

    end = clean.rfind("]")
    if end > start:
        json_str = clean[start : end + 1]
        try:
            data = json.loads(json_str)
            if isinstance(data, list) and len(data) > 0:
                # Validate structure
                valid = [
                    c for c in data if isinstance(c, dict) and "front" in c and "back" in c
                ]
                return valid if valid else None
        except json.JSONDecodeError:
            pass

    # Repair: find last complete object
    json_str = clean[start:]
    last_brace = json_str.rfind("}")
    if last_brace > 0:
        truncated = json_str[: last_brace + 1].rstrip().rstrip(",") + "]"
        try:
            data = json.loads(truncated)
            if isinstance(data, list):
                valid = [
                    c for c in data if isinstance(c, dict) and "front" in c and "back" in c
                ]
                return valid if valid else None
        except json.JSONDecodeError:
            pass

    return None
