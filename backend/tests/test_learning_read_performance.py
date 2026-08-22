import os
import types
import unittest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("EMBEDDING_API_KEY", "test-key")

from services.knowledge_graph_service import KnowledgeGraph
from services.learning_service import (
    LearningService,
    PerformanceTracker,
    SpacedRepetition,
    WeaknessDetector,
)


class _Query:
    def __init__(self, database, table):
        self.database = database
        self.table_name = table
        self.filters = {}
        self.lte_filters = {}
        self.ordering = None
        self.row_limit = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        self.filters[field] = value
        return self

    def lte(self, field, value):
        self.lte_filters[field] = value
        return self

    def order(self, field, desc=False):
        self.ordering = (field, desc)
        return self

    def limit(self, value):
        self.row_limit = value
        return self

    def execute(self):
        self.database.calls[self.table_name] += 1
        rows = [
            dict(row)
            for row in self.database.rows.get(self.table_name, [])
            if all(row.get(key) == value for key, value in self.filters.items())
            and all(
                row.get(key, "") <= value
                for key, value in self.lte_filters.items()
            )
        ]
        if self.ordering:
            field, desc = self.ordering
            rows.sort(key=lambda row: row.get(field, ""), reverse=desc)
        if self.row_limit is not None:
            rows = rows[: self.row_limit]
        return types.SimpleNamespace(data=rows)


class _Database:
    def __init__(self, rows):
        self.rows = rows
        self.calls = {table: 0 for table in rows}

    def table(self, name):
        return _Query(self, name)


class LearningDashboardPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_reuses_performance_and_preserves_due_ordering(self):
        database = _Database(
            {
                "user_performance": [
                    {
                        "id": "performance-1",
                        "user_id": "user-1",
                        "project_id": "project-1",
                        "topic": "Algebra",
                        "correct_count": 8,
                        "wrong_count": 2,
                        "history": [{"correct": 0, "wrong": 2}],
                        "last_attempt": "2026-08-20T00:00:00",
                    }
                ],
                "review_cards": [
                    {
                        "id": "due-card",
                        "user_id": "user-1",
                        "project_id": "project-1",
                        "next_review": "2000-01-01T00:00:00",
                        "repetition": 0,
                        "easiness_factor": 2.5,
                    },
                    {
                        "id": "future-card",
                        "user_id": "user-1",
                        "project_id": "project-1",
                        "next_review": "2999-01-01T00:00:00",
                        "repetition": 5,
                        "easiness_factor": 2.1,
                    },
                ],
            }
        )
        service = LearningService.__new__(LearningService)
        service.performance = PerformanceTracker.__new__(PerformanceTracker)
        service.weakness = WeaknessDetector.__new__(WeaknessDetector)
        service.spaced_rep = SpacedRepetition.__new__(SpacedRepetition)
        service.performance.client = database
        service.weakness.client = database
        service.spaced_rep.client = database

        dashboard = await service.get_learning_dashboard("user-1", "project-1")

        self.assertEqual(
            {
                "overall",
                "weak_topics",
                "due_cards",
                "review_stats",
                "performance_by_topic",
            },
            set(dashboard),
        )
        self.assertEqual(
            {
                "total_topics_studied",
                "total_questions_attempted",
                "overall_accuracy",
                "total_correct",
                "total_wrong",
            },
            set(dashboard["overall"]),
        )
        self.assertEqual(
            {"total_cards", "due_today", "overdue", "mastered", "learning", "new"},
            set(dashboard["review_stats"]),
        )
        self.assertEqual(["due-card"], [card["id"] for card in dashboard["due_cards"]])
        self.assertEqual(1, database.calls["user_performance"])
        self.assertEqual(2, database.calls["review_cards"])


class KnowledgeGraphReadPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_visualization_reads_relations_and_documents_once(self):
        database = _Database(
            {
                "topic_relations": [
                    {
                        "project_id": "project-1",
                        "from_topic": "Basics",
                        "to_topic": "Advanced",
                        "relation_type": "prerequisite",
                        "weight": 0.9,
                    }
                ],
                "documents": [
                    {
                        "id": "document-1",
                        "project_id": "project-1",
                        "upload_status": "completed",
                        "filename": "Course.pdf",
                        "topics": ["Basics", "Standalone"],
                    }
                ],
            }
        )
        graph_service = KnowledgeGraph.__new__(KnowledgeGraph)
        graph_service.client = database

        graph, stats = await graph_service.get_visualization("project-1")

        self.assertEqual({"nodes", "edges"}, set(graph))
        self.assertEqual(
            {"id", "label", "document"},
            set(graph["nodes"][0]),
        )
        self.assertEqual(
            {"source", "target", "type", "weight"},
            set(graph["edges"][0]),
        )
        self.assertEqual(
            {
                "total_nodes",
                "total_edges",
                "prerequisites",
                "related",
                "subtopics",
                "has_cycle",
            },
            set(stats),
        )
        self.assertEqual(1, database.calls["topic_relations"])
        self.assertEqual(1, database.calls["documents"])
        self.assertEqual(1, stats["total_edges"])
        self.assertFalse(stats["has_cycle"])


if __name__ == "__main__":
    unittest.main()
