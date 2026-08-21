import os
import types
import unittest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("EMBEDDING_API_KEY", "test-key")

from services.flashcard_service import FlashcardService


class _Query:
    def __init__(self, database, table):
        self.database = database
        self.table_name = table
        self.filters = {}
        self.in_filters = {}

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        self.filters[field] = value
        return self

    def in_(self, field, values):
        self.in_filters[field] = set(values)
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        self.database.execute_count += 1
        rows = self.database.rows[self.table_name]
        data = [
            dict(row)
            for row in rows
            if all(row.get(key) == value for key, value in self.filters.items())
            and all(
                row.get(key) in values for key, values in self.in_filters.items()
            )
        ]
        return types.SimpleNamespace(data=data)


class _Database:
    def __init__(self):
        self.execute_count = 0
        self.rows = {
            "flashcard_sets": [
                {"id": "set-1", "user_id": "user-1", "project_id": "project-1"},
                {"id": "set-2", "user_id": "user-1", "project_id": "project-1"},
                {"id": "foreign", "user_id": "user-2", "project_id": "project-1"},
            ],
            "flashcards": [
                {"id": "card-1", "set_id": "set-1", "position": 0},
                {"id": "card-2", "set_id": "set-1", "position": 1},
                {"id": "card-3", "set_id": "set-2", "position": 0},
                {"id": "foreign-card", "set_id": "foreign", "position": 0},
            ],
        }

    def table(self, name):
        return _Query(self, name)


class FlashcardPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_listing_uses_two_queries_and_groups_cards(self):
        database = _Database()
        service = FlashcardService.__new__(FlashcardService)
        service.supabase = database

        sets = await service.get_flashcard_sets("user-1", "project-1")

        self.assertEqual(2, database.execute_count)
        self.assertEqual([2, 1], [item["card_count"] for item in sets])
        self.assertEqual(
            [["card-1", "card-2"], ["card-3"]],
            [[card["id"] for card in item["cards"]] for item in sets],
        )


if __name__ == "__main__":
    unittest.main()
