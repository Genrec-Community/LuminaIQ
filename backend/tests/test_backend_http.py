import asyncio
import os
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("EMBEDDING_API_KEY", "test-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from api.v1.endpoints import chat, documents, progress, projects
from config.settings import settings
from utils.embedding_queue import EmbeddingQueue


class _Query:
    def __init__(self, database, table):
        self.database = database
        self.table_name = table
        self.filters = {}
        self.in_filters = {}
        self.inserted = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        self.filters[field] = value
        return self

    def in_(self, field, values):
        self.in_filters[field] = set(values)
        return self

    def insert(self, value):
        self.inserted = value
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        if self.inserted is not None:
            row = {"id": f"new-{self.table_name}", **self.inserted}
            self.database.storage_for(self.table_name).append(row)
            return types.SimpleNamespace(data=[row])
        return types.SimpleNamespace(
            data=self.database.rows(self.table_name, self.filters, self.in_filters)
        )


class _StorageBucket:
    def create_signed_url(self, path, expiry):
        return {"signedURL": f"https://storage.example/{path}"}


class _Storage:
    def from_(self, bucket):
        return _StorageBucket()


class _ProgressManager:
    async def subscribe(self, document_id):
        yield types.SimpleNamespace(
            stage="completed",
            progress=100,
            message="done",
            timestamp="2026-01-01T00:00:00",
        )


class _FakeSupabase:
    def __init__(self, projects=None, documents=None, chat_messages=None):
        self.projects = projects or []
        self.documents = documents or []
        self.chat_messages = chat_messages or []
        self.storage = _Storage()

    def table(self, name):
        return _Query(self, name)

    def rows(self, table, filters, in_filters=None):
        rows = self.storage_for(table)
        return [
            row
            for row in rows
            if all(row.get(field) == value for field, value in filters.items())
            and all(
                row.get(field) in values for field, values in (in_filters or {}).items()
            )
        ]

    def storage_for(self, table):
        return {
            "projects": self.projects,
            "documents": self.documents,
            "chat_messages": self.chat_messages,
        }[table]


async def _user_one():
    return {"id": "user-1", "email": "one@example.com"}


class TenantIsolationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(documents.router, prefix="/documents")
        self.app.include_router(chat.router, prefix="/chat")
        self.app.dependency_overrides[documents.get_current_user] = _user_one
        self.app.dependency_overrides[chat.get_current_user] = _user_one
        self.client = TestClient(self.app)
        self.original_client = documents.document_service.client
        self.original_process_document = documents.document_service.process_document
        self.original_delete_document = documents.document_service.delete_document
        self.original_get_client = documents.get_supabase_client
        self.original_generate_embedding = (
            documents.embedding_service.generate_embedding
        )
        self.original_vector_search = documents.qdrant_service.search
        self.original_get_queue = documents.get_embedding_queue
        self.original_chat_get_client = chat.get_supabase_client
        self.original_generate_summary = chat.rag_service.generate_summary
        self.original_get_answer = chat.rag_service.get_answer
        self.original_answer_stream = chat.rag_service.get_answer_stream
        self.original_user_context = chat.get_user_context_string

    def tearDown(self):
        self.client.close()
        documents.document_service.client = self.original_client
        documents.document_service.process_document = self.original_process_document
        documents.document_service.delete_document = self.original_delete_document
        documents.get_supabase_client = self.original_get_client
        documents.embedding_service.generate_embedding = (
            self.original_generate_embedding
        )
        documents.qdrant_service.search = self.original_vector_search
        documents.get_embedding_queue = self.original_get_queue
        chat.get_supabase_client = self.original_chat_get_client
        chat.rag_service.generate_summary = self.original_generate_summary
        chat.rag_service.get_answer = self.original_get_answer
        chat.rag_service.get_answer_stream = self.original_answer_stream
        chat.get_user_context_string = self.original_user_context

    def test_user_cannot_list_another_users_project_documents(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
            documents=[
                {
                    "id": "doc-2",
                    "project_id": "project-2",
                    "filename": "private.pdf",
                    "file_type": "application/pdf",
                    "file_size": 100,
                    "upload_status": "completed",
                }
            ],
        )
        documents.document_service.client = database

        response = self.client.get("/documents/project-2")

        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "Not authorized to access this project", response.json()["detail"]
        )

    def test_owner_can_list_project_documents(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
            documents=[
                {
                    "id": "doc-1",
                    "project_id": "project-1",
                    "filename": "biology.pdf",
                    "file_type": "application/pdf",
                    "file_size": 100,
                    "upload_status": "completed",
                }
            ],
        )
        documents.document_service.client = database

        response = self.client.get("/documents/project-1")

        self.assertEqual(200, response.status_code)
        self.assertEqual("biology.pdf", response.json()["documents"][0]["filename"])

    def test_user_cannot_upload_into_another_users_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
        )
        documents.document_service.client = database
        documents.document_service.process_document = AsyncMock(return_value=None)
        documents.get_supabase_client = lambda: database

        response = self.client.post(
            "/documents/upload",
            data={"project_id": "project-2"},
            files={"file": ("notes.txt", b"private notes", "text/plain")},
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "Not authorized to access this project", response.json()["detail"]
        )
        documents.document_service.process_document.assert_not_called()

    def test_user_cannot_get_signed_url_for_another_users_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
            documents=[
                {
                    "id": "doc-2",
                    "project_id": "project-2",
                    "filename": "private.pdf",
                }
            ],
        )
        documents.document_service.client = database
        documents.get_supabase_client = lambda: database

        response = self.client.get("/documents/project-2/doc-2/url")

        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "Not authorized to access this project", response.json()["detail"]
        )

    def test_owner_can_get_document_signed_url(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
            documents=[
                {"id": "doc-1", "project_id": "project-1", "filename": "book.pdf"}
            ],
        )
        documents.document_service.client = database
        documents.get_supabase_client = lambda: database

        response = self.client.get("/documents/project-1/doc-1/url")

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["url"].startswith("https://storage.example/"))

    def test_user_cannot_get_foreign_document_url_through_owned_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
            documents=[
                {"id": "doc-2", "project_id": "project-2", "filename": "private.pdf"}
            ],
        )
        documents.document_service.client = database
        documents.get_supabase_client = lambda: database

        response = self.client.get("/documents/project-1/doc-2/url")

        self.assertEqual(404, response.status_code)
        self.assertEqual("Document not found in project", response.json()["detail"])

    def test_user_cannot_delete_document_from_another_users_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
            documents=[{"id": "doc-2", "project_id": "project-2"}],
        )
        documents.document_service.client = database
        documents.document_service.delete_document = AsyncMock(return_value=None)

        response = self.client.delete(
            "/documents/doc-2",
            params={"project_id": "project-2"},
        )

        self.assertEqual(403, response.status_code)
        documents.document_service.delete_document.assert_not_called()

    def test_user_cannot_delete_foreign_document_through_owned_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
            documents=[{"id": "doc-2", "project_id": "project-2"}],
        )
        documents.document_service.client = database
        documents.document_service.delete_document = AsyncMock(return_value=None)

        response = self.client.delete(
            "/documents/doc-2",
            params={"project_id": "project-1"},
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual("Document not found in project", response.json()["detail"])
        documents.document_service.delete_document.assert_not_called()

    def test_user_cannot_search_another_users_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
        )
        documents.document_service.client = database
        documents.embedding_service.generate_embedding = AsyncMock(
            return_value=[0.1, 0.2]
        )
        documents.qdrant_service.search = AsyncMock(return_value=[])

        response = self.client.post(
            "/documents/project-2/search",
            json={"query": "private topic", "limit": 5},
        )

        self.assertEqual(403, response.status_code)
        documents.embedding_service.generate_embedding.assert_not_called()
        documents.qdrant_service.search.assert_not_called()

    def test_owner_can_search_project_documents(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
            documents=[
                {
                    "id": "doc-1",
                    "project_id": "project-1",
                    "filename": "biology.pdf",
                }
            ],
        )
        documents.document_service.client = database
        documents.embedding_service.generate_embedding = AsyncMock(
            return_value=[0.1, 0.2]
        )
        documents.qdrant_service.search = AsyncMock(
            return_value=[
                {
                    "text": "Plants use light.",
                    "document_id": "doc-1",
                    "chunk_id": 1,
                    "score": 0.9,
                }
            ]
        )

        response = self.client.post(
            "/documents/project-1/search",
            json={"query": "plants", "limit": 5},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("biology.pdf", response.json()["results"][0]["document_name"])

    def test_user_cannot_read_another_users_document_queue_status(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
            documents=[{"id": "doc-2", "project_id": "project-2"}],
        )
        queue = types.SimpleNamespace(
            get_document_status=lambda document_id: {
                "document_id": document_id,
                "filename": "private.pdf",
                "status": "processing",
            }
        )
        documents.document_service.client = database
        documents.get_embedding_queue = lambda: queue

        response = self.client.get("/documents/queue/doc-2")

        self.assertEqual(403, response.status_code)

    def test_global_queue_status_is_filtered_to_current_user(self):
        requested_users = []

        class Queue:
            def get_queue_stats(self, user_id):
                requested_users.append(user_id)
                return {"queued": 0, "processing": 0, "current_jobs": []}

        documents.get_embedding_queue = Queue

        response = self.client.get("/documents/queue/status")

        self.assertEqual(200, response.status_code)
        self.assertEqual(["user-1"], requested_users)

    def test_user_cannot_summarize_another_users_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
        )
        chat.get_supabase_client = lambda: database
        chat.rag_service.generate_summary = AsyncMock(
            return_value={"answer": "secret", "sources": []}
        )

        response = self.client.post(
            "/chat/summary",
            json={"project_id": "project-2", "selected_documents": []},
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "Not authorized to access this project", response.json()["detail"]
        )
        chat.rag_service.generate_summary.assert_not_called()

    def test_owner_can_summarize_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
        )
        chat.get_supabase_client = lambda: database
        chat.rag_service.generate_summary = AsyncMock(
            return_value={"answer": "A biology summary.", "sources": []}
        )

        response = self.client.post(
            "/chat/summary",
            json={"project_id": "project-1", "selected_documents": []},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("A biology summary.", response.json()["answer"])

    def test_user_cannot_read_another_users_chat_history(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
            chat_messages=[
                {
                    "id": "message-1",
                    "project_id": "project-2",
                    "role": "assistant",
                    "content": "private answer",
                }
            ],
        )
        chat.get_supabase_client = lambda: database

        response = self.client.get("/chat/history/project-2")

        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "Not authorized to access this project", response.json()["detail"]
        )

    def test_owner_can_read_project_chat_history(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
            chat_messages=[
                {
                    "id": "message-1",
                    "project_id": "project-1",
                    "role": "assistant",
                    "content": "Study photosynthesis.",
                }
            ],
        )
        chat.get_supabase_client = lambda: database

        response = self.client.get("/chat/history/project-1")

        self.assertEqual(200, response.status_code)
        self.assertEqual("Study photosynthesis.", response.json()[0]["content"])

    def test_user_cannot_message_another_users_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
        )
        chat.get_supabase_client = lambda: database
        chat.get_user_context_string = AsyncMock(return_value="")
        chat.rag_service.get_answer = AsyncMock(
            return_value={"answer": "private", "sources": []}
        )

        response = self.client.post(
            "/chat/message",
            json={
                "project_id": "project-2",
                "message": "Reveal it",
                "selected_documents": [],
                "session_history": [],
            },
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual([], database.chat_messages)
        chat.rag_service.get_answer.assert_not_called()

    def test_owner_can_send_non_streaming_chat_message(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
        )
        chat.get_supabase_client = lambda: database
        chat.get_user_context_string = AsyncMock(return_value="")
        chat.rag_service.get_answer = AsyncMock(
            return_value={"answer": "Plants use light.", "sources": []}
        )

        response = self.client.post(
            "/chat/message",
            json={
                "project_id": "project-1",
                "message": "How do plants grow?",
                "selected_documents": [],
                "session_history": [],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("Plants use light.", response.json()["answer"])
        self.assertEqual(
            ["user", "assistant"], [row["role"] for row in database.chat_messages]
        )

    def test_user_cannot_stream_chat_from_another_users_project(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
        )
        calls = []

        async def answer_stream(**kwargs):
            calls.append(kwargs)
            yield "secret"
            yield "\n\n__SOURCES__:[]"

        chat.get_supabase_client = lambda: database
        chat.get_user_context_string = AsyncMock(return_value="")
        chat.rag_service.get_answer_stream = answer_stream

        response = self.client.post(
            "/chat/stream",
            json={
                "project_id": "project-2",
                "message": "Reveal the book",
                "selected_documents": [],
                "session_history": [],
            },
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual([], calls)
        self.assertEqual([], database.chat_messages)

    def test_authorized_upload_returns_pending_document_and_schedules_processing(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
        )
        processed_paths = []

        async def process_document(**kwargs):
            processed_paths.append(kwargs["file_path"])
            os.unlink(kwargs["file_path"])

        documents.document_service.client = database
        documents.document_service.process_document = AsyncMock(
            side_effect=process_document
        )
        documents.get_supabase_client = lambda: database

        response = self.client.post(
            "/documents/upload",
            data={"project_id": "project-1"},
            files={"file": ("notes.txt", b"study notes", "text/plain")},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("pending", response.json()["upload_status"])
        self.assertEqual("project-1", response.json()["project_id"])
        documents.document_service.process_document.assert_called_once()
        self.assertEqual(1, len(processed_paths))
        self.assertFalse(os.path.exists(processed_paths[0]))

    def test_authorized_chat_stream_preserves_answer_and_sources(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
        )

        async def answer_stream(**kwargs):
            yield "Plants"
            yield " grow"
            yield (
                '\n\n__SOURCES__:[{"doc_id":"doc-1","doc_name":"Biology.pdf",'
                '"chunk_text":"Plants grow"}]'
            )

        chat.get_supabase_client = lambda: database
        chat.get_user_context_string = AsyncMock(return_value="")
        chat.rag_service.get_answer_stream = answer_stream

        response = self.client.post(
            "/chat/stream",
            json={
                "project_id": "project-1",
                "message": "What grows?",
                "selected_documents": ["doc-1"],
                "session_history": [],
            },
        )

        self.assertEqual(200, response.status_code)
        answer = response.text.split("__SOURCES__:", 1)[0]
        self.assertEqual(1, answer.count("Plants grow"))
        self.assertEqual(1, response.text.count("__SOURCES__:"))
        self.assertEqual(
            ["user", "assistant"], [row["role"] for row in database.chat_messages]
        )


class _FakeProjectService:
    def __init__(self):
        self.items = []

    async def create_project(self, user_id, name):
        project = {
            "id": "project-1",
            "user_id": user_id,
            "name": name,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        self.items.append(project)
        return project

    async def get_projects(self, user_id):
        return [project for project in self.items if project["user_id"] == user_id]

    async def get_project(self, project_id):
        return next(
            (project for project in self.items if project["id"] == project_id), None
        )

    async def delete_project(self, project_id):
        self.items = [project for project in self.items if project["id"] != project_id]
        return True


class ProjectsCRUDHTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(projects.router, prefix="/projects")
        self.app.dependency_overrides[projects.get_current_user] = _user_one
        self.client = TestClient(self.app)
        self.original_service = projects.project_service
        self.fake_service = _FakeProjectService()
        projects.project_service = self.fake_service

    def tearDown(self):
        self.client.close()
        projects.project_service = self.original_service

    def test_authenticated_user_can_create_and_list_own_project(self):
        created = self.client.post("/projects/", json={"name": "Biology"})
        listed = self.client.get("/projects/")

        self.assertEqual(200, created.status_code)
        self.assertEqual("user-1", created.json()["user_id"])
        self.assertEqual("Biology", listed.json()[0]["name"])

    def test_user_cannot_delete_another_users_project(self):
        self.fake_service.items.append(
            {
                "id": "project-2",
                "user_id": "user-2",
                "name": "Private",
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        )

        response = self.client.delete("/projects/project-2")

        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "Not authorized to delete this project", response.json()["detail"]
        )

    def test_projects_endpoint_requires_authentication(self):
        app = FastAPI()
        app.include_router(projects.router, prefix="/projects")

        with TestClient(app) as client:
            response = client.get("/projects/")

        self.assertEqual(401, response.status_code)


class ProgressHTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(progress.router, prefix="/progress")
        self.client = TestClient(self.app)
        self.original_verify = progress._verify_token
        self.original_manager = progress.get_progress_manager
        self.had_get_client = hasattr(progress, "get_supabase_client")
        self.original_get_client = getattr(progress, "get_supabase_client", None)

    def tearDown(self):
        self.client.close()
        progress._verify_token = self.original_verify
        progress.get_progress_manager = self.original_manager
        if self.had_get_client:
            progress.get_supabase_client = self.original_get_client
        elif hasattr(progress, "get_supabase_client"):
            delattr(progress, "get_supabase_client")

    def test_user_cannot_subscribe_to_another_users_document_progress(self):
        database = _FakeSupabase(
            projects=[{"id": "project-2", "user_id": "user-2"}],
            documents=[{"id": "doc-2", "project_id": "project-2"}],
        )
        progress._verify_token = AsyncMock(return_value={"id": "user-1"})
        progress.get_progress_manager = lambda: _ProgressManager()
        progress.get_supabase_client = lambda: database

        response = self.client.get(
            "/progress/doc-2",
            params={"token": "valid-token"},
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "Not authorized to access this project", response.json()["detail"]
        )

    def test_owner_can_subscribe_with_signed_jwt(self):
        database = _FakeSupabase(
            projects=[{"id": "project-1", "user_id": "user-1"}],
            documents=[{"id": "doc-1", "project_id": "project-1"}],
        )
        progress.get_progress_manager = lambda: _ProgressManager()
        progress.get_supabase_client = lambda: database
        token = jwt.encode(
            {"sub": "user-1", "email": "one@example.com"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        response = self.client.get(
            "/progress/doc-1",
            params={"token": token},
        )

        self.assertEqual(200, response.status_code)
        self.assertIn('"stage": "completed"', response.text)

    def test_progress_rejects_invalid_jwt(self):
        response = self.client.get(
            "/progress/doc-1",
            params={"token": "not-a-jwt"},
        )

        self.assertEqual(401, response.status_code)


class QueueLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_job_is_not_reported_as_active(self):
        original_semaphore = EmbeddingQueue._doc_semaphore
        EmbeddingQueue._doc_semaphore = asyncio.Semaphore(1)
        queue = EmbeddingQueue()
        started = asyncio.Event()

        async def process(job):
            started.set()
            await asyncio.Event().wait()

        try:
            job_id = await queue.enqueue(
                document_id="doc-1",
                project_id="project-1",
                filename="book.pdf",
                chunks=["private chunk"],
                process_callback=process,
                user_id="user-1",
            )
            await started.wait()

            await queue.stop()

            status = queue.get_job_status(job_id)
            stats = queue.get_queue_stats("user-1")
            self.assertEqual("failed", status["status"])
            self.assertEqual("Processing cancelled", status["error_message"])
            self.assertEqual(0, stats["active_tasks"])
            self.assertEqual([], queue._jobs[job_id].chunks)
        finally:
            EmbeddingQueue._doc_semaphore = original_semaphore


if __name__ == "__main__":
    unittest.main()
