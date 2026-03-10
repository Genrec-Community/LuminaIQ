"""
Knowledge Graph API Endpoints

Provides:
1. Graph visualization data with book at center
2. Topic summary generation using RAG
3. Analytics recording and retrieval
4. AI-powered learning suggestions
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from api.deps import get_current_user
from services.knowledge_graph_service import knowledge_graph
from services.graph_analytics_service import graph_analytics
from utils.logger import logger

router = APIRouter()


# ============== Request/Response Models ==============

class TopicSummaryRequest(BaseModel):
    project_id: str
    topic: str
    force_regenerate: bool = False


class RecordInteractionRequest(BaseModel):
    project_id: str
    topic: str
    event_type: str  # click, expand, summary_view, summary_generate, hover, navigation
    duration_ms: int = 0
    metadata: Optional[Dict[str, Any]] = None


class BatchInteractionsRequest(BaseModel):
    project_id: str
    interactions: List[Dict[str, Any]]


class SuggestionsRequest(BaseModel):
    project_id: str
    current_topic: Optional[str] = None
    limit: int = 3


class SessionRequest(BaseModel):
    project_id: str


class EndSessionRequest(BaseModel):
    session_id: str
    topics_visited: List[str]
    total_time_ms: int


# ============== Graph Visualization ==============

@router.get("/graph/{project_id}")
async def get_knowledge_graph(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get knowledge graph data for visualization.
    Returns nodes (topics) and edges (relationships) with book as center node.
    """
    try:
        # Get graph data
        graph_data = await knowledge_graph.get_full_graph(project_id)
        
        # Get project info for center node
        from db.client import get_supabase_client
        client = get_supabase_client()
        project = (
            client.table("projects")
            .select("name")
            .eq("id", project_id)
            .execute()
        )
        project_name = project.data[0]["name"] if project.data else "Project"
        
        # Get document names for book nodes
        documents = (
            client.table("documents")
            .select("id, filename, topics")
            .eq("project_id", project_id)
            .eq("upload_status", "completed")
            .execute()
        )
        
        # Build enhanced graph with books
        nodes = []
        edges = []
        
        # Add document (book) nodes
        doc_topics_map = {}
        for doc in documents.data or []:
            doc_id = f"book_{doc['id']}"
            nodes.append({
                "id": doc_id,
                "label": doc["filename"].replace(".pdf", "").replace(".docx", ""),
                "type": "book",
                "document_id": doc["id"]
            })
            
            # Map topics to their document
            for topic in (doc.get("topics") or []):
                doc_topics_map[topic] = doc_id
        
        # Add topic nodes from graph
        existing_topics = set()
        for node in graph_data.get("nodes", []):
            topic_id = node["id"]
            existing_topics.add(topic_id)
            nodes.append({
                "id": topic_id,
                "label": node["label"],
                "type": "topic",
                "document": node.get("document", "Unknown")
            })
            
            # Add edge from book to topic
            if topic_id in doc_topics_map:
                edges.append({
                    "source": doc_topics_map[topic_id],
                    "target": topic_id,
                    "type": "contains",
                    "weight": 1.0
                })
        
        # Add topic relationships
        for edge in graph_data.get("edges", []):
            edges.append({
                "source": edge["source"],
                "target": edge["target"],
                "type": edge.get("type", "related"),
                "weight": edge.get("weight", 0.5)
            })
        
        # Get graph stats
        stats = await knowledge_graph.get_graph_stats(project_id)
        
        return {
            "project_name": project_name,
            "nodes": nodes,
            "edges": edges,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting knowledge graph: {e}")
        raise HTTPException(500, str(e))


# ============== Topic Summaries ==============

@router.post("/topic-summary")
async def get_topic_summary(
    request: TopicSummaryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get or generate a summary for a specific topic using RAG.
    Summaries are cached for performance.
    """
    try:
        result = await graph_analytics.get_topic_summary(
            project_id=request.project_id,
            topic=request.topic,
            user_id=current_user["id"],
            force_regenerate=request.force_regenerate
        )
        return result
        
    except Exception as e:
        logger.error(f"Error getting topic summary: {e}")
        raise HTTPException(500, str(e))


# ============== Analytics Recording ==============

@router.post("/analytics/record")
async def record_interaction(
    request: RecordInteractionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Record a user interaction with the knowledge graph.
    Used for tracking learning behavior.
    """
    try:
        result = await graph_analytics.record_interaction(
            project_id=request.project_id,
            user_id=current_user["id"],
            topic=request.topic,
            event_type=request.event_type,
            duration_ms=request.duration_ms,
            metadata=request.metadata
        )
        return {"success": True, "id": result.get("id")}
        
    except Exception as e:
        logger.error(f"Error recording interaction: {e}")
        raise HTTPException(500, str(e))


@router.post("/analytics/record-batch")
async def record_batch_interactions(
    request: BatchInteractionsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Record multiple interactions at once (for batched client updates).
    """
    try:
        # Add user_id and project_id to each interaction
        for interaction in request.interactions:
            interaction["user_id"] = current_user["id"]
            interaction["project_id"] = request.project_id
        
        count = await graph_analytics.record_batch_interactions(request.interactions)
        return {"success": True, "recorded": count}
        
    except Exception as e:
        logger.error(f"Error recording batch interactions: {e}")
        raise HTTPException(500, str(e))


@router.get("/analytics/{project_id}")
async def get_analytics(
    project_id: str,
    days: int = 7,
    current_user: dict = Depends(get_current_user)
):
    """
    Get user analytics for the knowledge graph.
    """
    try:
        result = await graph_analytics.get_user_analytics(
            project_id=project_id,
            user_id=current_user["id"],
            days=days
        )
        return result
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(500, str(e))


# ============== Learning Suggestions ==============

@router.post("/suggestions")
async def get_suggestions(
    request: SuggestionsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get AI-powered learning suggestions based on user behavior.
    """
    try:
        result = await graph_analytics.get_learning_suggestions(
            project_id=request.project_id,
            user_id=current_user["id"],
            current_topic=request.current_topic,
            limit=request.limit
        )
        return result
        
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(500, str(e))


# ============== Session Management ==============

@router.post("/session/start")
async def start_session(
    request: SessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Start a new learning session.
    """
    try:
        session_id = await graph_analytics.start_session(
            project_id=request.project_id,
            user_id=current_user["id"]
        )
        return {"session_id": session_id}
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(500, str(e))


@router.post("/session/end")
async def end_session(
    request: EndSessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    End a learning session with summary data.
    """
    try:
        result = await graph_analytics.end_session(
            session_id=request.session_id,
            topics_visited=request.topics_visited,
            total_time_ms=request.total_time_ms
        )
        return {"success": True, "session": result}
        
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        raise HTTPException(500, str(e))
