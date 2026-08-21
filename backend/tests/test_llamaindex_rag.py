import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

from llama_index.core.llms import MockLLM


MODULE_NAMES = (
    "config.settings",
    "db.client",
    "services.embedding_service",
    "services.llm_service",
    "services.qdrant_service",
    "utils.logger",
)


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _stub(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module


def _load_rag_module():
    settings = types.SimpleNamespace(RAG_TOP_K=5, RAG_HISTORY_MESSAGES=2)

    async def async_db(callable_fn):
        return callable_fn()

    _stub("config.settings", settings=settings)
    _stub(
        "db.client",
        async_db=async_db,
        get_supabase_client=lambda: object(),
    )
    _stub("services.embedding_service", embedding_service=object())
    _stub(
        "services.llm_service",
        llm_service=types.SimpleNamespace(_get_client=lambda **kwargs: object()),
    )
    _stub("services.qdrant_service", qdrant_service=object())
    _stub("utils.logger", logger=_Logger())

    path = Path(__file__).resolve().parents[1] / "services" / "rag_service.py"
    spec = importlib.util.spec_from_file_location("rag_service_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _EmbeddingProvider:
    def __init__(self):
        self.queries = []

    async def generate_embedding(self, query):
        self.queries.append(query)
        return [0.1, 0.2]


class _VectorStore:
    def __init__(self):
        self.calls = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {
                "id": "point-1",
                "score": 0.91,
                "text": "Photosynthesis converts light into chemical energy.",
                "document_id": "doc-1",
                "document_name": "Biology.pdf",
                "chunk_id": 4,
            }
        ]


class _Response:
    def __str__(self):
        return "Plants convert light into chemical energy [1](1)."


class _StreamingResponse:
    async def async_response_gen(self):
        for token in ("Plants ", "use light."):
            yield token


class _BrokenStreamingResponse:
    async def async_response_gen(self):
        yield "Partial answer"
        raise TimeoutError("stream interrupted")


class _Synthesizer:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def asynthesize(self, question, nodes):
        self.calls.append((question, nodes))
        return self.response


class LlamaIndexRAGTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_modules = {name: sys.modules.get(name) for name in MODULE_NAMES}
        self.module = _load_rag_module()

    def tearDown(self):
        for name, original in self.original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    async def test_retriever_preserves_filters_scores_and_source_metadata(self):
        embeddings = _EmbeddingProvider()
        vectors = _VectorStore()
        retriever = self.module.ExistingQdrantRetriever(
            collection_name="project-p1",
            selected_documents=["doc-1"],
            top_k=3,
            embedding_provider=embeddings,
            vector_store=vectors,
        )

        nodes = await retriever.aretrieve("How do plants store energy?")

        self.assertEqual(["How do plants store energy?"], embeddings.queries)
        self.assertEqual(
            {"document_ids": ["doc-1"]}, vectors.calls[0]["filter_conditions"]
        )
        self.assertEqual(3, vectors.calls[0]["limit"])
        self.assertEqual(0.91, nodes[0].score)
        self.assertEqual("doc-1", nodes[0].metadata["document_id"])
        self.assertEqual("Biology.pdf", nodes[0].metadata["document_name"])
        self.assertTrue(nodes[0].get_content().startswith("[Source 1]"))

    async def test_empty_hits_do_not_shift_citation_numbers(self):
        vectors = _VectorStore()

        async def search(**kwargs):
            return [
                {"id": "empty", "score": 1.0, "text": ""},
                {
                    "id": "point-1",
                    "score": 0.9,
                    "text": "Usable context.",
                    "document_id": "doc-1",
                    "document_name": "Book.pdf",
                    "chunk_id": 1,
                },
            ]

        vectors.search = search
        retriever = self.module.ExistingQdrantRetriever(
            "project-p1",
            embedding_provider=_EmbeddingProvider(),
            vector_store=vectors,
        )

        nodes = await retriever.aretrieve("question")

        self.assertEqual(1, nodes[0].metadata["source_number"])
        self.assertTrue(nodes[0].get_content().startswith("[Source 1]"))

    async def test_answer_keeps_existing_frontend_contract(self):
        nodes = await self.module.ExistingQdrantRetriever(
            "project-p1",
            embedding_provider=_EmbeddingProvider(),
            vector_store=_VectorStore(),
        ).aretrieve("question")
        synthesizer = _Synthesizer(_Response())
        service = self.module.RAGService(client=object(), llm=object())

        async def retrieve(*args, **kwargs):
            return nodes

        service._retrieve = retrieve
        service._synthesizer = lambda *args, **kwargs: synthesizer

        result = await service.get_answer("p1", "question")

        self.assertIn("[1](1)", result["answer"])
        self.assertEqual("doc-1", result["sources"][0]["doc_id"])
        self.assertEqual("Biology.pdf", result["sources"][0]["doc_name"])
        self.assertFalse(result["sources"][0]["chunk_text"].startswith("[Source"))

    async def test_transient_retrieval_failure_is_retried(self):
        nodes = await self.module.ExistingQdrantRetriever(
            "project-p1",
            embedding_provider=_EmbeddingProvider(),
            vector_store=_VectorStore(),
        ).aretrieve("question")
        synthesizer = _Synthesizer(_Response())
        service = self.module.RAGService(client=object(), llm=object())
        calls = 0

        async def retrieve(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("temporary retrieval timeout")
            return nodes

        async def no_sleep(delay):
            pass

        service._retrieve = retrieve
        service._synthesizer = lambda *args, **kwargs: synthesizer
        original_sleep = self.module._sleep
        self.module._sleep = no_sleep
        try:
            result = await service.get_answer("p1", "question")
        finally:
            self.module._sleep = original_sleep

        self.assertEqual(2, calls)
        self.assertTrue(result["answer"])

    async def test_stream_ends_with_sources_envelope(self):
        nodes = await self.module.ExistingQdrantRetriever(
            "project-p1",
            embedding_provider=_EmbeddingProvider(),
            vector_store=_VectorStore(),
        ).aretrieve("question")
        service = self.module.RAGService(client=object(), llm=object())

        async def retrieve(*args, **kwargs):
            return nodes

        service._retrieve = retrieve
        service._synthesizer = lambda *args, **kwargs: _Synthesizer(
            _StreamingResponse()
        )

        chunks = [chunk async for chunk in service.get_answer_stream("p1", "question")]

        self.assertEqual("Plants use light.", "".join(chunks[:-1]))
        self.assertIn("__SOURCES__:", chunks[-1])
        sources = json.loads(chunks[-1].split("__SOURCES__:", 1)[1])
        self.assertEqual("doc-1", sources[0]["doc_id"])

    async def test_midstream_failure_still_sends_sources_envelope(self):
        nodes = await self.module.ExistingQdrantRetriever(
            "project-p1",
            embedding_provider=_EmbeddingProvider(),
            vector_store=_VectorStore(),
        ).aretrieve("question")
        service = self.module.RAGService(client=object(), llm=object())

        async def retrieve(*args, **kwargs):
            return nodes

        service._retrieve = retrieve
        service._synthesizer = lambda *args, **kwargs: _Synthesizer(
            _BrokenStreamingResponse()
        )

        chunks = [chunk async for chunk in service.get_answer_stream("p1", "question")]

        self.assertEqual("Partial answer", chunks[0])
        self.assertTrue(any("Error:" in chunk for chunk in chunks))
        self.assertIn("__SOURCES__:", chunks[-1])

    async def test_real_llamaindex_synthesizers_support_async_and_streaming(self):
        nodes = await self.module.ExistingQdrantRetriever(
            "project-p1",
            embedding_provider=_EmbeddingProvider(),
            vector_store=_VectorStore(),
        ).aretrieve("question")
        service = self.module.RAGService(client=object(), llm=MockLLM(max_tokens=20))

        async def retrieve(*args, **kwargs):
            return nodes

        service._retrieve = retrieve

        result = await service.get_answer("p1", "question")
        streamed = [
            chunk async for chunk in service.get_answer_stream("p1", "question")
        ]

        self.assertTrue(result["answer"])
        self.assertIn("__SOURCES__:", streamed[-1])

    def test_prompt_limits_history_for_lower_latency(self):
        prompt = self.module._build_prompt(
            None,
            None,
            [
                {"role": "user", "content": "old"},
                {"role": "assistant", "content": "recent answer"},
                {"role": "user", "content": "recent question"},
            ],
        ).template

        self.assertNotIn("Student: old", prompt)
        self.assertIn("Tutor: recent answer", prompt)
        self.assertIn("Student: recent question", prompt)


if __name__ == "__main__":
    unittest.main()
