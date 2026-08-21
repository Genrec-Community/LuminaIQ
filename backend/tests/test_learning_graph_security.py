import os
import unittest
from unittest.mock import AsyncMock

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("EMBEDDING_API_KEY", "test-key")

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.v1.endpoints import learning


async def _user_one():
    return {"id": "user-1", "email": "one@example.com"}


class LearningGraphSecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(learning.router, prefix="/learning")
        self.app.dependency_overrides[learning.get_current_user] = _user_one
        self.client = TestClient(self.app)
        self.original_owner_check = learning.require_project_owner
        self.original_builder = learning.topic_graph_builder
        learning.topic_graph_builder = AsyncMock()

    def tearDown(self):
        learning.require_project_owner = self.original_owner_check
        learning.topic_graph_builder = self.original_builder

    def test_user_cannot_force_rebuild_another_users_graph(self):
        learning.require_project_owner = AsyncMock(
            side_effect=HTTPException(403, "Not authorized to access this project")
        )

        response = self.client.post(
            "/learning/knowledge-graph/project-2/build",
            json={"topics": ["A", "B"], "force_rebuild": True},
        )

        self.assertEqual(403, response.status_code)
        learning.topic_graph_builder.build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
