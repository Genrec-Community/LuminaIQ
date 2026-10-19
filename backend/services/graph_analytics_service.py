"""
Graph Analytics Service - Learning Behavior Tracking & AI Suggestions

Features:
1. Track user interactions (clicks, time spent, navigation patterns)
2. Generate topic summaries using RAG
3. Provide AI-powered learning suggestions based on behavior
4. Session-based analytics for learning patterns
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from db.client import get_supabase_client, async_db
from services.llm_service import llm_service
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service
from utils.logger import logger
from uuid import uuid4
import json


class GraphAnalyticsService:
    """
    Service for tracking and analyzing user interactions with the knowledge graph.
    Provides AI-powered learning suggestions based on behavior patterns.
    """

    def __init__(self):
        self.client = get_supabase_client()

    # ============== Analytics Recording ==============

    async def record_interaction(
        self,
        project_id: str,
        user_id: str,
        topic: str,
        event_type: str,
        duration_ms: int = 0,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Record a user interaction with the knowledge graph.
        
        Event types:
        - click: User clicked on a topic node
        - expand: User expanded a topic to view details
        - summary_view: User viewed a cached summary
        - summary_generate: User triggered summary generation
        - hover: User hovered over a topic
        - navigation: User navigated between topics
        """
        try:
            record = {
                "id": str(uuid4()),
                "project_id": project_id,
                "user_id": user_id,
                "topic": topic,
                "event_type": event_type,
                "duration_ms": duration_ms,
                "metadata": metadata or {}
            }
            
            result = (await async_db(lambda: self.client.table("graph_analytics").insert(record).execute()))
            logger.info(f"Recorded {event_type} event for topic '{topic}'")
            
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
            return {}

    async def record_batch_interactions(
        self,
        interactions: List[Dict[str, Any]]
    ) -> int:
        """Record multiple interactions at once (for batched client updates)."""
        try:
            if not interactions:
                return 0
                
            # Add IDs
            for interaction in interactions:
                if "id" not in interaction:
                    interaction["id"] = str(uuid4())
            
            (await async_db(lambda: self.client.table("graph_analytics").insert(interactions).execute()))
            logger.info(f"Recorded {len(interactions)} batch interactions")
            return len(interactions)
            
        except Exception as e:
            logger.error(f"Error recording batch interactions: {e}")
            return 0

    # ============== Topic Summary Generation ==============

    async def get_topic_summary(
        self,
        project_id: str,
        topic: str,
        user_id: str = None,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Get or generate a summary for a specific topic using RAG.
        
        Returns cached summary if available, otherwise generates new one.
        """
        try:
            # Check cache first
            if not force_regenerate:
                cached = (
                    (await async_db(lambda: self.client.table("topic_summaries")
                    .select("*")
                    .eq("project_id", project_id)
                    .eq("topic", topic)
                    .execute()))
                )
                
                if cached.data:
                    logger.info(f"Returning cached summary for topic '{topic}'")
                    
                    # Record view event
                    if user_id:
                        await self.record_interaction(
                            project_id, user_id, topic, "summary_view"
                        )
                    
                    return {
                        "topic": topic,
                        "summary": cached.data[0]["summary"],
                        "sources": cached.data[0].get("sources", []),
                        "cached": True
                    }
            
            # Generate new summary using RAG
            logger.info(f"Generating new summary for topic '{topic}'")
            
            # Record generation event
            if user_id:
                await self.record_interaction(
                    project_id, user_id, topic, "summary_generate"
                )
            
            # Search for relevant content
            collection_name = f"project_{project_id}"
            query_embedding = await embedding_service.generate_embedding(topic)
            
            results = await qdrant_service.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=8
            )
            
            context_parts = []
            sources = []
            seen_docs = set()
            reindexing = []

            if not results:
                # Vector search found nothing even though the project has documents:
                # the search index is missing. Rebuild it in the background and
                # answer from the stored document text in the meantime.
                from services.document_service import document_service

                try:
                    reindexing = await document_service.ensure_project_indexed(project_id)
                except Exception as reindex_err:
                    logger.error(f"Failed to check/rebuild index for {project_id}: {reindex_err}")

                context_parts, sources = await self.keyword_context_from_stored_text(
                    project_id, topic
                )

                if not context_parts:
                    msg = f"No content found for '{topic}' in the uploaded documents."
                    if reindexing:
                        msg = (
                            f"Your documents are being re-indexed ({len(reindexing)} "
                            f"document(s)). Please try '{topic}' again in a few minutes."
                        )
                    return {
                        "topic": topic,
                        "summary": msg,
                        "sources": [],
                        "cached": False
                    }

            for hit in results:
                context_parts.append(hit["text"])
                doc_id = hit.get("document_id", "")
                if doc_id and doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    # Get document name
                    try:
                        doc_res = (
                            (await async_db(lambda: self.client.table("documents")
                            .select("filename")
                            .eq("id", doc_id)
                            .execute()))
                        )
                        if doc_res.data:
                            sources.append({
                                "doc_id": doc_id,
                                "doc_name": doc_res.data[0]["filename"],
                                "chunk_text": hit["text"][:100] + "..."
                            })
                    except:
                        pass
            
            context = "\n\n".join(context_parts)
            
            # Generate summary with LLM
            prompt = f"""You are an expert educational assistant. Generate a comprehensive yet concise summary about the topic "{topic}" based on the following content from the user's study materials.

CONTENT:
{context[:8000]}

INSTRUCTIONS:
1. Focus specifically on "{topic}" - what it is, why it matters, key concepts
2. Use clear, educational language suitable for studying
3. Include key definitions, formulas, or important points if relevant
4. Structure with bullet points or short paragraphs for easy reading
5. Keep it between 150-300 words
6. Use **bold** for key terms and concepts

Generate the summary now:"""

            messages = [{"role": "user", "content": prompt}]
            summary = await llm_service.chat_completion(
                messages, temperature=0.3, max_tokens=1000, light=True
            )
            
            # Don't cache summaries built from the keyword fallback — once the
            # index is rebuilt, vector search gives better context.
            if not results:
                return {
                    "topic": topic,
                    "summary": summary,
                    "sources": sources,
                    "cached": False
                }

            # Cache the summary
            try:
                (await async_db(lambda: self.client.table("topic_summaries").upsert(
                    {
                        "project_id": project_id,
                        "topic": topic,
                        "summary": summary,
                        "sources": sources,
                        "updated_at": datetime.utcnow().isoformat()
                    },
                    on_conflict="project_id,topic"
                ).execute()))
            except Exception as cache_err:
                logger.warning(f"Failed to cache summary: {cache_err}")
            
            return {
                "topic": topic,
                "summary": summary,
                "sources": sources,
                "cached": False
            }
            
        except Exception as e:
            logger.error(f"Error getting topic summary: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "topic": topic,
                "summary": f"Error generating summary: {str(e)}",
                "sources": [],
                "cached": False
            }

    async def keyword_context_from_stored_text(
        self,
        project_id: str,
        topic: str,
        max_passages: int = 8,
        window: int = 1200,
        document_ids: Optional[List[str]] = None,
        per_passage_sources: bool = False,
        overview_if_empty: bool = False,
    ) -> tuple:
        """
        Fallback retrieval when the vector index is unavailable: scan each
        document's stored text for passages that mention the topic's keywords.
        Returns (context_parts, sources). With per_passage_sources, sources[i]
        describes context_parts[i] (so inline citations [n] line up).
        """
        import re
        from services.document_service import document_service

        stopwords = {
            "a", "an", "and", "the", "of", "in", "on", "by", "to", "for", "with",
            "its", "their", "is", "are", "as", "at", "from", "or", "e", "g", "eg",
            # question words that would otherwise match every page
            "what", "which", "who", "whom", "why", "how", "when", "where", "does",
            "did", "can", "could", "would", "should", "this", "that", "these",
            "those", "about", "tell", "explain", "describe", "give", "me", "you",
            "your", "book", "document", "chapter", "text", "please", "main", "mean",
        }
        keywords = [
            w for w in re.findall(r"[a-z0-9]+", topic.lower())
            if len(w) > 2 and w not in stopwords
        ]
        if not keywords and not overview_if_empty:
            return [], []

        try:
            query = (
                self.client.table("documents")
                .select("id, project_id, filename, text_storage_path")
                .eq("project_id", project_id)
                .eq("upload_status", "completed")
            )
            if document_ids:
                query = query.in_("id", document_ids)
            docs = await async_db(lambda: query.execute())
        except Exception as e:
            logger.warning(f"Keyword fallback: failed to list documents: {e}")
            return [], []

        texts = []  # (doc, text)
        for doc in docs.data or []:
            text = await document_service.load_stored_text(doc)
            if text:
                texts.append((doc, text))

        candidates = []  # (score, passage, doc)
        if keywords:
            for doc, text in texts:
                lower = text.lower()
                for start in range(0, len(lower), window // 2):
                    segment = lower[start:start + window]
                    # Require most keywords to appear so passages are actually on-topic
                    distinct = sum(1 for k in keywords if k in segment)
                    if distinct >= max(1, (len(keywords) + 1) // 2):
                        score = sum(segment.count(k) for k in keywords)
                        candidates.append((distinct * 10 + score, text[start:start + window], doc))
            candidates.sort(key=lambda c: c[0], reverse=True)

        if not candidates and overview_if_empty:
            # Broad question ("what is this book about?"): opening pages plus
            # evenly spaced samples give the model a view of the whole book.
            per_doc = max(2, max_passages // max(1, len(texts)))
            for doc, text in texts:
                step = max(window, len(text) // per_doc)
                for i, start in enumerate(range(0, len(text), step)):
                    if i >= per_doc:
                        break
                    candidates.append((0, text[start:start + window], doc))

        context_parts, sources, seen_docs = [], [], set()
        for _, passage, doc in candidates[:max_passages]:
            context_parts.append(passage)
            if per_passage_sources or doc["id"] not in seen_docs:
                seen_docs.add(doc["id"])
                sources.append({
                    "doc_id": doc["id"],
                    "doc_name": doc["filename"],
                    "chunk_text": passage if per_passage_sources else passage[:100] + "...",
                })

        logger.info(
            f"Keyword fallback for '{topic}': {len(context_parts)} passages "
            f"from {len(seen_docs)} document(s)"
        )
        return context_parts, sources

    # ============== Learning Suggestions ==============

    async def get_learning_suggestions(
        self,
        project_id: str,
        user_id: str,
        current_topic: str = None,
        limit: int = 3
    ) -> Dict[str, Any]:
        """
        Get AI-powered learning suggestions based on user behavior.
        
        Analyzes:
        - Topics visited and time spent
        - Navigation patterns
        - Topics not yet explored
        - Knowledge graph relationships
        """
        try:
            # Get user's interaction history
            history = (
                (await async_db(lambda: self.client.table("graph_analytics")
                .select("topic, event_type, duration_ms, created_at")
                .eq("project_id", project_id)
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(100)
                .execute()))
            )
            
            interactions = history.data or []
            
            # Analyze patterns
            topic_clicks = Counter()
            topic_time = defaultdict(int)
            visited_topics = set()
            
            for interaction in interactions:
                topic = interaction["topic"]
                visited_topics.add(topic)
                
                if interaction["event_type"] in ["click", "expand"]:
                    topic_clicks[topic] += 1
                    
                topic_time[topic] += interaction.get("duration_ms", 0)
            
            # Get all available topics
            from services.knowledge_graph_service import knowledge_graph
            
            graph_data = await knowledge_graph.get_full_graph(project_id)
            all_topics = {node["id"] for node in graph_data.get("nodes", [])}
            
            # Find unvisited topics
            unvisited = all_topics - visited_topics
            
            # Get graph relationships for context
            adj_list = await knowledge_graph.get_adjacency_list(project_id)
            
            suggestions = []
            reasons = []
            
            # 1. Suggest based on current topic's relationships
            if current_topic and current_topic in adj_list:
                related = adj_list[current_topic]
                for rel in related[:2]:
                    if rel["to"] not in visited_topics or topic_time[rel["to"]] < 30000:
                        suggestions.append(rel["to"])
                        if rel["type"] == "prerequisite":
                            reasons.append(f"'{rel['to']}' is a prerequisite for better understanding")
                        else:
                            reasons.append(f"'{rel['to']}' is closely related to what you're studying")
            
            # 2. Suggest unvisited topics
            if len(suggestions) < limit and unvisited:
                # Prioritize topics with prerequisites you've already covered
                for topic in list(unvisited)[:limit - len(suggestions)]:
                    prereqs = await knowledge_graph.get_prerequisites(project_id, topic)
                    if not prereqs or all(p in visited_topics for p in prereqs):
                        suggestions.append(topic)
                        reasons.append(f"You're ready to learn '{topic}' - prerequisites covered!")
            
            # 3. Suggest revisiting topics with low time spent
            if len(suggestions) < limit:
                quick_visits = [
                    t for t, time in topic_time.items() 
                    if time < 20000 and t not in suggestions  # Less than 20 seconds
                ]
                for topic in quick_visits[:limit - len(suggestions)]:
                    suggestions.append(topic)
                    reasons.append(f"Consider revisiting '{topic}' for deeper understanding")
            
            # Build analytics summary
            analytics_summary = {
                "total_topics_visited": len(visited_topics),
                "total_topics_available": len(all_topics),
                "coverage_percent": round(len(visited_topics) / max(1, len(all_topics)) * 100, 1),
                "most_studied": topic_clicks.most_common(3),
                "total_study_time_ms": sum(topic_time.values()),
                "avg_time_per_topic_ms": round(sum(topic_time.values()) / max(1, len(visited_topics)))
            }
            
            return {
                "suggestions": suggestions[:limit],
                "reasons": reasons[:limit],
                "analytics": analytics_summary,
                "current_topic": current_topic
            }
            
        except Exception as e:
            logger.error(f"Error getting learning suggestions: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "suggestions": [],
                "reasons": [],
                "analytics": {},
                "current_topic": current_topic
            }

    # ============== Session Management ==============

    async def start_session(
        self,
        project_id: str,
        user_id: str
    ) -> str:
        """Start a new learning session."""
        try:
            session = {
                "id": str(uuid4()),
                "project_id": project_id,
                "user_id": user_id,
                "started_at": datetime.utcnow().isoformat()
            }
            
            result = (await async_db(lambda: self.client.table("learning_sessions").insert(session).execute()))
            session_id = result.data[0]["id"] if result.data else session["id"]
            
            logger.info(f"Started learning session {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error starting session: {e}")
            return str(uuid4())

    async def end_session(
        self,
        session_id: str,
        topics_visited: List[str],
        total_time_ms: int
    ) -> Dict[str, Any]:
        """End a learning session with summary data."""
        try:
            update = {
                "ended_at": datetime.utcnow().isoformat(),
                "topics_visited": topics_visited,
                "total_time_ms": total_time_ms
            }
            
            result = (
                (await async_db(lambda: self.client.table("learning_sessions")
                .update(update)
                .eq("id", session_id)
                .execute()))
            )
            
            logger.info(f"Ended learning session {session_id}")
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            return {}

    # ============== Analytics Queries ==============

    async def get_user_analytics(
        self,
        project_id: str,
        user_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get comprehensive analytics for a user."""
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Get all interactions
            interactions = (
                (await async_db(lambda: self.client.table("graph_analytics")
                .select("*")
                .eq("project_id", project_id)
                .eq("user_id", user_id)
                .gte("created_at", cutoff)
                .order("created_at", desc=True)
                .execute()))
            ).data or []
            
            # Get sessions
            sessions = (
                (await async_db(lambda: self.client.table("learning_sessions")
                .select("*")
                .eq("project_id", project_id)
                .eq("user_id", user_id)
                .gte("started_at", cutoff)
                .execute()))
            ).data or []
            
            # Analyze
            topic_stats = defaultdict(lambda: {"clicks": 0, "time_ms": 0, "summaries": 0})
            event_counts = Counter()
            daily_activity = defaultdict(int)
            
            for interaction in interactions:
                topic = interaction["topic"]
                event = interaction["event_type"]
                
                topic_stats[topic]["clicks"] += 1 if event == "click" else 0
                topic_stats[topic]["time_ms"] += interaction.get("duration_ms", 0)
                topic_stats[topic]["summaries"] += 1 if event in ["summary_view", "summary_generate"] else 0
                
                event_counts[event] += 1
                
                date = interaction["created_at"][:10]
                daily_activity[date] += 1
            
            # Find focus areas and gaps
            sorted_topics = sorted(
                topic_stats.items(),
                key=lambda x: x[1]["time_ms"],
                reverse=True
            )
            
            return {
                "period_days": days,
                "total_interactions": len(interactions),
                "total_sessions": len(sessions),
                "event_breakdown": dict(event_counts),
                "daily_activity": dict(daily_activity),
                "top_topics": [
                    {"topic": t, **stats} 
                    for t, stats in sorted_topics[:10]
                ],
                "total_study_time_ms": sum(t["time_ms"] for t in topic_stats.values()),
                "unique_topics_studied": len(topic_stats)
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}


# Singleton instance
graph_analytics = GraphAnalyticsService()
