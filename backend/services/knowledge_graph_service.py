"""
Knowledge Graph Service - Topic Relationship Mapping

Features:
1. Store graph in adjacency list format
2. Find related topics using BFS/DFS
3. Generate learning paths using Topological Sort
4. Suggest prerequisites for any topic
5. Track document source for each topic

DSA Used:
- Adjacency List for graph storage
- BFS for finding related topics at distance K
- DFS for detecting cycles
- Topological Sort (Kahn's Algorithm) for learning path generation
- Priority Queue for weighted path finding
"""

import heapq
from collections import defaultdict, deque
from typing import List, Dict, Any, Optional, Set, Tuple
from db.client import get_supabase_client, async_db
from utils.logger import logger
from uuid import uuid4


class KnowledgeGraph:
    """
    Knowledge Graph implementation using Adjacency List.

    Graph Structure:
    - Nodes: Topics (strings)
    - Edges: Relationships (prerequisite, related, subtopic)
    - Weights: Relationship strength (0.0-1.0)

    Storage: Supabase `topic_relations` table

    DSA:
    - Adjacency List: O(1) add edge, O(V+E) traversal
    - BFS: Find topics within K hops
    - Topological Sort: Generate learning order
    """

    def __init__(self):
        self.client = get_supabase_client()

    async def _get_edges(self, project_id: str) -> List[Dict[str, Any]]:
        result = await async_db(
            lambda: self.client.table("topic_relations")
            .select("*")
            .eq("project_id", project_id)
            .execute()
        )
        return result.data or []

    async def _get_completed_documents(self, project_id: str) -> List[Dict[str, Any]]:
        result = await async_db(
            lambda: self.client.table("documents")
            .select("id, filename, topics")
            .eq("project_id", project_id)
            .eq("upload_status", "completed")
            .execute()
        )
        return result.data or []

    @staticmethod
    def _topic_document_mapping(documents: List[Dict[str, Any]]) -> Dict[str, str]:
        topic_doc_map = {}
        for doc in documents:
            doc_name = doc.get("filename", "Unknown")
            for topic in doc.get("topics") or []:
                if topic not in topic_doc_map:
                    topic_doc_map[topic] = doc_name
        return topic_doc_map

    async def add_relationship(
        self,
        project_id: str,
        from_topic: str,
        to_topic: str,
        relation_type: str = "related",
        weight: float = 0.5,
    ) -> Dict[str, Any]:
        """Manually add a relationship between topics."""
        try:
            edge = {
                "id": str(uuid4()),
                "project_id": project_id,
                "from_topic": from_topic,
                "to_topic": to_topic,
                "relation_type": relation_type,
                "weight": min(1.0, max(0.1, weight)),
            }

            result = await async_db(lambda: self.client.table("topic_relations").insert(edge).execute())
            return result.data[0] if result.data else {}

        except Exception as e:
            logger.error(f"Error adding relationship: {e}")
            raise

    # ============== Graph Queries ==============

    async def get_adjacency_list(
        self, project_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get graph as adjacency list."""
        try:
            result = await async_db(lambda: 
                self.client.table("topic_relations")
                .select("*")
                .eq("project_id", project_id)
                .execute()
            )

            edges = result.data or []
            adj_list = defaultdict(list)

            for edge in edges:
                adj_list[edge["from_topic"]].append(
                    {
                        "to": edge["to_topic"],
                        "type": edge["relation_type"],
                        "weight": edge["weight"],
                    }
                )

                if edge["relation_type"] == "related":
                    adj_list[edge["to_topic"]].append(
                        {
                            "to": edge["from_topic"],
                            "type": "related",
                            "weight": edge["weight"],
                        }
                    )

            return dict(adj_list)

        except Exception as e:
            logger.error(f"Error getting adjacency list: {e}")
            return {}

    async def find_related_topics(
        self, project_id: str, topic: str, max_distance: int = 2
    ) -> List[Dict[str, Any]]:
        """Find topics related to a given topic using BFS."""
        try:
            adj_list = await self.get_adjacency_list(project_id)

            if topic not in adj_list and not any(
                topic in [e["to"] for e in edges] for edges in adj_list.values()
            ):
                return []

            visited = {topic}
            queue = deque([(topic, 0)])
            related = []

            while queue:
                current, distance = queue.popleft()

                if distance > 0:
                    related.append({"topic": current, "distance": distance})

                if distance < max_distance:
                    for neighbor in adj_list.get(current, []):
                        if neighbor["to"] not in visited:
                            visited.add(neighbor["to"])
                            queue.append((neighbor["to"], distance + 1))

            related.sort(key=lambda x: x["distance"])
            return related

        except Exception as e:
            logger.error(f"Error finding related topics: {e}")
            return []

    async def get_prerequisites(self, project_id: str, topic: str) -> List[str]:
        """Get all prerequisite topics for a given topic."""
        try:
            result = await async_db(lambda: 
                self.client.table("topic_relations")
                .select("from_topic")
                .eq("project_id", project_id)
                .eq("to_topic", topic)
                .eq("relation_type", "prerequisite")
                .execute()
            )

            return [edge["from_topic"] for edge in (result.data or [])]

        except Exception as e:
            logger.error(f"Error getting prerequisites: {e}")
            return []

    async def get_dependents(self, project_id: str, topic: str) -> List[str]:
        """Get topics that depend on the given topic."""
        try:
            result = await async_db(lambda: 
                self.client.table("topic_relations")
                .select("to_topic")
                .eq("project_id", project_id)
                .eq("from_topic", topic)
                .eq("relation_type", "prerequisite")
                .execute()
            )

            return [edge["to_topic"] for edge in (result.data or [])]

        except Exception as e:
            logger.error(f"Error getting dependents: {e}")
            return []

    # ============== Learning Path Generation ==============

    async def generate_learning_path(
        self, project_id: str, target_topics: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate optimal learning path using Topological Sort.
        Includes document source for each topic.
        """
        try:
            # Get topic-to-document mapping
            topic_doc_map = await self._get_topic_document_mapping(project_id)

            # Get all edges
            result = await async_db(lambda: 
                self.client.table("topic_relations")
                .select("*")
                .eq("project_id", project_id)
                .eq("relation_type", "prerequisite")
                .execute()
            )

            edges = result.data or []

            if not edges:
                # No prerequisites - return topics with doc info
                if target_topics:
                    return [
                        {
                            "topic": t,
                            "order": i + 1,
                            "prerequisites": [],
                            "document": topic_doc_map.get(t, "Unknown"),
                        }
                        for i, t in enumerate(target_topics)
                    ]

                # Get all topics from documents
                all_topics = list(topic_doc_map.keys())
                if all_topics:
                    return [
                        {
                            "topic": t,
                            "order": i + 1,
                            "prerequisites": [],
                            "document": topic_doc_map.get(t, "Unknown"),
                        }
                        for i, t in enumerate(sorted(all_topics))
                    ]

                return []

            # Build graph adjacency list + in-degree counts from edges
            graph = defaultdict(list)
            in_degree = defaultdict(int)

            for edge in edges:
                from_topic = edge["from_topic"]
                to_topic = edge["to_topic"]
                graph[from_topic].append(to_topic)
                in_degree[to_topic] += 1
                if from_topic not in in_degree:
                    in_degree[from_topic] = 0

            # ── Seed all_topics from documents (source of truth) ─────────────
            # Every topic from every completed document MUST appear in the path,
            # even if the LLM created no edges for it during graph build.
            all_topics = set(topic_doc_map.keys())

            # Defensive: include any edge-endpoint topics not in doc map
            for edge in edges:
                all_topics.add(edge["from_topic"])
                all_topics.add(edge["to_topic"])

            # Ensure every topic has an in_degree entry (default 0 = queue-ready)
            for t in all_topics:
                if t not in in_degree:
                    in_degree[t] = 0

            # Filter if target_topics provided
            if target_topics:
                needed = set(target_topics)
                to_check = list(target_topics)

                while to_check:
                    topic = to_check.pop()
                    for edge in edges:
                        if (
                            edge["to_topic"] == topic
                            and edge["from_topic"] not in needed
                        ):
                            needed.add(edge["from_topic"])
                            to_check.append(edge["from_topic"])

                all_topics = needed

            # Kahn's Algorithm
            queue = deque()
            for topic in all_topics:
                if in_degree.get(topic, 0) == 0:
                    queue.append(topic)

            learning_path = []
            order = 1

            while queue:
                topic = queue.popleft()

                if topic in all_topics:
                    prereqs = [
                        e["from_topic"]
                        for e in edges
                        if e["to_topic"] == topic and e["from_topic"] in all_topics
                    ]

                    learning_path.append(
                        {
                            "topic": topic,
                            "order": order,
                            "prerequisites": prereqs,
                            "document": topic_doc_map.get(topic, "Unknown"),
                        }
                    )
                    order += 1

                for dependent in graph.get(topic, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            # Handle cycles
            processed_topics = {item["topic"] for item in learning_path}
            remaining_topics = all_topics - processed_topics

            if remaining_topics:
                logger.warning(
                    f"Cycle detected - adding {len(remaining_topics)} remaining topics"
                )
                for topic in sorted(remaining_topics):
                    prereqs = [
                        e["from_topic"]
                        for e in edges
                        if e["to_topic"] == topic and e["from_topic"] in all_topics
                    ]
                    learning_path.append(
                        {
                            "topic": topic,
                            "order": order,
                            "prerequisites": prereqs,
                            "document": topic_doc_map.get(topic, "Unknown"),
                        }
                    )
                    order += 1

            return learning_path

        except Exception as e:
            logger.error(f"Error generating learning path: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []

    async def _get_topic_document_mapping(self, project_id: str) -> Dict[str, str]:
        """Get mapping of topic -> document name"""
        try:
            documents = await self._get_completed_documents(project_id)
            return self._topic_document_mapping(documents)

        except Exception as e:
            logger.error(f"Error getting topic-document mapping: {e}")
            return {}

    async def detect_cycle(self, project_id: str) -> bool:
        """Detect if there's a cycle in the prerequisite graph."""
        try:
            result = await async_db(lambda: 
                self.client.table("topic_relations")
                .select("*")
                .eq("project_id", project_id)
                .eq("relation_type", "prerequisite")
                .execute()
            )

            edges = result.data or []

            if not edges:
                return False

            graph = defaultdict(list)
            all_topics = set()

            for edge in edges:
                graph[edge["from_topic"]].append(edge["to_topic"])
                all_topics.add(edge["from_topic"])
                all_topics.add(edge["to_topic"])

            color = {topic: 0 for topic in all_topics}

            def dfs(node: str) -> bool:
                color[node] = 1

                for neighbor in graph.get(node, []):
                    if color.get(neighbor, 0) == 1:
                        return True
                    if color.get(neighbor, 0) == 0 and dfs(neighbor):
                        return True

                color[node] = 2
                return False

            for topic in all_topics:
                if color[topic] == 0:
                    if dfs(topic):
                        return True

            return False

        except Exception as e:
            logger.error(f"Error detecting cycle: {e}")
            return False

    # ============== Graph Statistics ==============

    async def get_graph_stats(self, project_id: str) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        try:
            return self._build_graph_stats(await self._get_edges(project_id))

        except Exception as e:
            logger.error(f"Error getting graph stats: {e}")
            return {}

    @staticmethod
    def _build_graph_stats(edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        nodes = set()
        edge_counts = {"prerequisite": 0, "related": 0, "subtopic": 0}
        graph = defaultdict(list)

        for edge in edges:
            from_topic = edge["from_topic"]
            to_topic = edge["to_topic"]
            nodes.update((from_topic, to_topic))
            edge_type = edge.get("relation_type", "related")
            edge_counts[edge_type] = edge_counts.get(edge_type, 0) + 1
            if edge_type == "prerequisite":
                graph[from_topic].append(to_topic)

        color = {}

        def has_cycle(topic: str) -> bool:
            color[topic] = 1
            for neighbor in graph.get(topic, []):
                if color.get(neighbor) == 1:
                    return True
                if color.get(neighbor, 0) == 0 and has_cycle(neighbor):
                    return True
            color[topic] = 2
            return False

        cycle_found = any(
            color.get(topic, 0) == 0 and has_cycle(topic) for topic in nodes
        )
        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "prerequisites": edge_counts.get("prerequisite", 0),
            "related": edge_counts.get("related", 0),
            "subtopics": edge_counts.get("subtopic", 0),
            "has_cycle": cycle_found,
        }

    @staticmethod
    def _build_full_graph(
        edges: List[Dict[str, Any]], topic_doc_map: Dict[str, str]
    ) -> Dict[str, Any]:
        nodes = set(topic_doc_map)
        vis_edges = []
        for edge in edges:
            nodes.update((edge["from_topic"], edge["to_topic"]))
            vis_edges.append(
                {
                    "source": edge["from_topic"],
                    "target": edge["to_topic"],
                    "type": edge["relation_type"],
                    "weight": edge["weight"],
                }
            )
        return {
            "nodes": [
                {"id": node, "label": node, "document": topic_doc_map.get(node, "Unknown")}
                for node in nodes
            ],
            "edges": vis_edges,
        }

    async def get_visualization(
        self,
        project_id: str,
        documents: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Build graph and stats while reading each backing table at most once."""
        if documents is None:
            documents = await self._get_completed_documents(project_id)
        edges = await self._get_edges(project_id)
        topic_doc_map = self._topic_document_mapping(documents)
        return (
            self._build_full_graph(edges, topic_doc_map),
            self._build_graph_stats(edges),
        )

    async def get_full_graph(self, project_id: str) -> Dict[str, Any]:
        """Get full graph data for visualization.
        
        Always includes ALL topics from documents, even if no relations exist yet.
        """
        try:
            graph, _ = await self.get_visualization(project_id)
            return graph

        except Exception as e:
            logger.error(f"Error getting full graph: {e}")
            return {"nodes": [], "edges": []}


# Singleton instance
knowledge_graph = KnowledgeGraph()
