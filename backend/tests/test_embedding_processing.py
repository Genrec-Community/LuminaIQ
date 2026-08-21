import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _Progress:
    async def emit(self, *args, **kwargs):
        pass


class _EmbeddingQueue:
    pass


class _Constructable:
    def __init__(self, *args, **kwargs):
        pass


def _stub_module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module


def _load_document_service_module():
    settings = types.SimpleNamespace(
        CHUNK_SIZE=800,
        CHUNK_OVERLAP=80,
        EMBEDDING_BATCH_SIZE=2,
        MAX_GLOBAL_EMBEDDINGS=2,
        MAX_GLOBAL_DB_OPERATIONS=2,
        EMBEDDING_MAX_RETRIES=5,
        EMBEDDING_MAX_RETRY_DELAY_S=8.0,
        EMBEDDING_REQUEST_TIMEOUT_S=60.0,
        BOOK_IMPORT_TEXTS_BUCKET="texts",
    )

    async def async_db(callable_fn):
        return callable_fn()

    _stub_module(
        "db.client",
        get_supabase_client=lambda: object(),
        async_db=async_db,
    )
    _stub_module("config.settings", settings=settings)
    _stub_module("utils.file_parser", FileParser=_Constructable)
    _stub_module("utils.text_chunker", TextChunker=_Constructable)
    _stub_module("utils.logger", logger=_Logger())
    _stub_module(
        "utils.embedding_queue",
        get_embedding_queue=lambda: None,
        EmbeddingJob=object,
        EmbeddingQueue=_EmbeddingQueue,
    )
    _stub_module(
        "utils.progress_manager",
        get_progress_manager=lambda: _Progress(),
    )
    _stub_module("services.embedding_service", embedding_service=object())
    _stub_module("services.qdrant_service", qdrant_service=object())

    module_path = (
        Path(__file__).resolve().parents[1] / "services" / "document_service.py"
    )
    spec = importlib.util.spec_from_file_location(
        "embedding_document_service_under_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Qdrant:
    def __init__(self):
        self.upserts = []
        self.deletions = []
        self.finalizations = []

    async def upsert_chunks(self, **kwargs):
        self.upserts.append(kwargs)

    async def delete_vectors(self, collection_name, document_id, raise_on_error=False):
        self.deletions.append((collection_name, document_id, raise_on_error))

    async def delete_vectors_except(self, collection_name, document_id, keep_ids):
        self.finalizations.append((collection_name, document_id, keep_ids))


class EmbeddingProcessingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stubbed_module_names = (
            "db.client",
            "config.settings",
            "utils.file_parser",
            "utils.text_chunker",
            "utils.logger",
            "utils.embedding_queue",
            "utils.progress_manager",
            "utils.embedding_scheduler",
            "services.embedding_service",
            "services.qdrant_service",
        )
        self.original_modules = {
            name: sys.modules.get(name) for name in self.stubbed_module_names
        }
        sys.modules.pop("utils.embedding_scheduler", None)
        self.module = _load_document_service_module()
        self.service = self.module.DocumentService.__new__(self.module.DocumentService)
        self.service.batch_size = 2
        self.qdrant = _Qdrant()
        self.module.qdrant_service = self.qdrant

    def tearDown(self):
        for name, original in self.original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    async def test_rejects_partial_embedding_response(self):
        class PartialEmbeddingProvider:
            async def generate_embeddings(self, texts):
                return [[0.1, 0.2] for _ in texts[:-1]]

        self.module.embedding_service = PartialEmbeddingProvider()

        with self.assertRaisesRegex(Exception, "embedding count"):
            await self.service._process_embeddings_direct(
                ["one", "two"], "doc-1", "book.txt", "project-1"
            )

        self.assertEqual([], self.qdrant.upserts)
        self.assertEqual([], self.qdrant.finalizations)

    async def test_permanent_error_is_not_retried(self):
        class PermanentFailureProvider:
            def __init__(self):
                self.calls = 0

            async def generate_embeddings(self, texts):
                self.calls += 1
                raise ValueError("input is too long")

        provider = PermanentFailureProvider()
        self.module.embedding_service = provider

        with self.assertRaises(Exception):
            await self.service._process_embeddings_direct(
                ["one", "two"], "doc-1", "book.txt", "project-1"
            )

        self.assertEqual(1, provider.calls)

    async def test_transient_retry_delay_is_bounded(self):
        class RecoveringProvider:
            def __init__(self):
                self.calls = 0

            async def generate_embeddings(self, texts):
                self.calls += 1
                if self.calls <= 5:
                    raise TimeoutError("temporary timeout")
                return [[0.1, 0.2] for _ in texts]

        delays = []

        async def capture_sleep(delay):
            delays.append(delay)

        provider = RecoveringProvider()
        self.module.embedding_service = provider
        scheduler = self.module.get_embedding_scheduler()
        original_sleep = scheduler.sleep
        scheduler.sleep = capture_sleep
        try:
            await self.service._process_embeddings_direct(
                ["one", "two"], "doc-1", "book.txt", "project-1"
            )
        finally:
            scheduler.sleep = original_sleep

        self.assertEqual(6, provider.calls)
        self.assertLessEqual(max(delays), 8)
        self.assertLessEqual(sum(delays), 23)

    async def test_transient_qdrant_write_is_retried(self):
        class SuccessfulProvider:
            async def generate_embeddings(self, texts):
                return [[0.1, 0.2] for _ in texts]

        calls = 0
        delays = []

        async def flaky_upsert(**kwargs):
            nonlocal calls
            calls += 1
            if calls <= 2:
                raise TimeoutError("Qdrant temporarily unavailable")
            self.qdrant.upserts.append(kwargs)

        async def capture_sleep(delay):
            delays.append(delay)

        self.module.embedding_service = SuccessfulProvider()
        self.qdrant.upsert_chunks = flaky_upsert
        scheduler = self.module.get_embedding_scheduler()
        original_sleep = scheduler.sleep
        scheduler.sleep = capture_sleep
        try:
            await self.service._process_embeddings_direct(
                ["one", "two"], "doc-1", "book.txt", "project-1"
            )
        finally:
            scheduler.sleep = original_sleep

        self.assertEqual(3, calls)
        self.assertEqual(2, len(delays))
        self.assertEqual(1, len(self.qdrant.upserts))

    async def test_large_book_uses_fixed_worker_count(self):
        active = 0
        peak_active = 0
        worker_tasks = set()

        class TrackingProvider:
            async def generate_embeddings(inner_self, texts):
                nonlocal active, peak_active
                worker_tasks.add(id(asyncio.current_task()))
                active += 1
                peak_active = max(peak_active, active)
                await asyncio.sleep(0)
                active -= 1
                return [[0.1, 0.2] for _ in texts]

        self.module.embedding_service = TrackingProvider()
        chunks = [f"chunk-{index}" for index in range(200)]

        await self.service._process_embeddings_direct(
            chunks, "doc-1", "large-book.txt", "project-1"
        )

        self.assertLessEqual(peak_active, 2)
        self.assertLessEqual(len(worker_tasks), 2)
        self.assertEqual(100, len(self.qdrant.upserts))

    async def test_same_document_jobs_do_not_overlap(self):
        active = 0
        peak_active = 0

        class TrackingProvider:
            async def generate_embeddings(inner_self, texts):
                nonlocal active, peak_active
                active += 1
                peak_active = max(peak_active, active)
                await asyncio.sleep(0)
                active -= 1
                return [[0.1, 0.2] for _ in texts]

        self.module.embedding_service = TrackingProvider()

        await asyncio.gather(
            self.service._process_embeddings_direct(
                ["one", "two"], "doc-1", "book.txt", "project-1"
            ),
            self.service._process_embeddings_direct(
                ["one", "two"], "doc-1", "book.txt", "project-1"
            ),
        )

        self.assertEqual(1, peak_active)

    async def test_embedding_limit_is_shared_across_documents(self):
        active = 0
        peak_active = 0

        class TrackingProvider:
            async def generate_embeddings(inner_self, texts):
                nonlocal active, peak_active
                active += 1
                peak_active = max(peak_active, active)
                await asyncio.sleep(0)
                active -= 1
                return [[0.1, 0.2] for _ in texts]

        self.module.embedding_service = TrackingProvider()
        chunks = [f"chunk-{index}" for index in range(40)]

        await asyncio.gather(
            self.service._process_embeddings_direct(
                chunks, "doc-1", "book-1.txt", "project-1"
            ),
            self.service._process_embeddings_direct(
                chunks, "doc-2", "book-2.txt", "project-1"
            ),
        )

        self.assertLessEqual(peak_active, 2)

    def test_embedding_point_ids_are_idempotent(self):
        point_id = sys.modules["utils.embedding_scheduler"].embedding_point_id

        first = point_id("project-1", "doc-1", 7)
        repeated = point_id("project-1", "doc-1", 7)
        different_chunk = point_id("project-1", "doc-1", 8)

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, different_chunk)

    def test_qdrant_transport_errors_are_transient(self):
        classifier = sys.modules[
            "utils.embedding_scheduler"
        ].is_transient_embedding_error
        connect_error = type("ConnectError", (Exception,), {})()
        pool_timeout = type("PoolTimeout", (Exception,), {})()
        response_error = type("ResponseHandlingException", (Exception,), {})()

        self.assertTrue(classifier(connect_error))
        self.assertTrue(classifier(pool_timeout))
        self.assertTrue(classifier(response_error))
        self.assertTrue(classifier(Exception("Temporary failure in name resolution")))


if __name__ == "__main__":
    unittest.main()
