import asyncio
import json
import unittest
from weakref import WeakValueDictionary

from services.topic_graph_builder import (
    LLMRelationshipGenerator,
    SupabaseTopicGraphStore,
    TopicGraphBuilder,
)


class _InMemoryStore:
    def __init__(self, existing=False, events=None):
        self.relationships = (
            [{"from_topic": "Old A", "to_topic": "Old B"}] if existing else []
        )
        self.events = events
        self.cleared_projects = []
        self.upserted_edges = []
        self.latest_build_started_at = None

    async def has_relationships(self, project_id):
        return bool(self.relationships)

    async def clear_relationships(self, project_id):
        if self.events is not None:
            self.events.append("clear")
        self.cleared_projects.append(project_id)
        self.relationships = []

    async def upsert_relationships(self, edges):
        if self.events is not None:
            self.events.append("upsert")
        self.upserted_edges.extend(edges)
        self.relationships.extend(edges)

    async def replace_relationships(self, project_id, edges, build_started_at):
        if (
            self.latest_build_started_at is not None
            and build_started_at < self.latest_build_started_at
        ):
            return False
        self.latest_build_started_at = build_started_at
        if self.events is not None:
            self.events.append("replace")
        self.cleared_projects.append(project_id)
        self.upserted_edges.extend(edges)
        self.relationships = list(edges)
        return True


class _RelationshipGenerator:
    def __init__(self, edges=None):
        self.edges = edges or []
        self.calls = []

    async def generate(self, project_id, batch_topics, all_topics):
        self.calls.append((project_id, batch_topics, all_topics))
        return [dict(edge) for edge in self.edges]


class _BlockingGenerator:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, project_id, batch_topics, all_topics):
        self.started.set()
        await self.release.wait()
        return []


class _DelayedGenerator:
    def __init__(self, delay, edge):
        self.delay = delay
        self.edge = edge

    async def generate(self, project_id, batch_topics, all_topics):
        await asyncio.sleep(self.delay)
        return [{"project_id": project_id, **self.edge}]


class _ConcurrentGenerator:
    def __init__(self, events=None, fail_topic=None):
        self.events = events
        self.fail_topic = fail_topic
        self.active_calls = 0
        self.peak_concurrency = 0

    async def generate(self, project_id, batch_topics, all_topics):
        self.active_calls += 1
        self.peak_concurrency = max(self.peak_concurrency, self.active_calls)
        if self.events is not None:
            self.events.append(f"generate:{batch_topics[0]}")
        try:
            await asyncio.sleep(0.01)
            if self.fail_topic in batch_topics:
                raise RuntimeError("provider unavailable")
            if self.events is not None:
                self.events.append(f"generated:{batch_topics[0]}")
            return [
                {
                    "project_id": project_id,
                    "from_topic": batch_topics[0],
                    "to_topic": batch_topics[1],
                    "relation_type": "related",
                    "weight": 0.5,
                }
            ]
        finally:
            self.active_calls -= 1


class _LLM:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def chat_completion(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.response


class TopicGraphBuilderTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_graph_skips_generation(self):
        store = _InMemoryStore(existing=True)
        generator = _RelationshipGenerator()
        builder = TopicGraphBuilder(store, generator)

        result = await builder.build("project-1", ["A", "B"])

        self.assertEqual(0, result["edges_created"])
        self.assertIn("already exists", result["message"])
        self.assertEqual([], generator.calls)
        self.assertEqual([], store.cleared_projects)

    async def test_force_build_hides_batching_deduplication_and_replacement(self):
        duplicate_edge = {
            "project_id": "project-1",
            "from_topic": "A",
            "to_topic": "B",
            "relation_type": "prerequisite",
            "weight": 0.9,
        }
        store = _InMemoryStore(existing=True)
        generator = _RelationshipGenerator([duplicate_edge])
        builder = TopicGraphBuilder(
            store,
            generator,
            batch_size=4,
            batch_overlap=1,
        )

        result = await builder.build(
            "project-1", ["A", "B", "C", "D", "E", "F", "G"], True
        )

        self.assertEqual(
            {"edges_created": 1, "message": "Successfully created 1 relationships"},
            result,
        )
        self.assertEqual(["project-1"], store.cleared_projects)
        self.assertEqual([duplicate_edge], store.upserted_edges)
        self.assertEqual(2, len(generator.calls))

    async def test_concurrent_build_for_same_project_returns_without_waiting(self):
        generator = _BlockingGenerator()
        builder = TopicGraphBuilder(_InMemoryStore(), generator)

        first = asyncio.create_task(builder.build("project-1", ["A", "B"], True))
        await generator.started.wait()
        second = await builder.build("project-1", ["A", "B"], True)
        generator.release.set()
        await first

        self.assertEqual(
            {"edges_created": 0, "message": "Build already in progress"}, second
        )

    async def test_operational_failure_is_raised_at_the_interface(self):
        class BrokenStore(_InMemoryStore):
            async def has_relationships(self, project_id):
                raise RuntimeError("database unavailable")

        builder = TopicGraphBuilder(BrokenStore(), _RelationshipGenerator())

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await builder.build("project-1", ["A", "B"])

    async def test_failed_batch_preserves_active_graph(self):
        store = _InMemoryStore(existing=True)
        original_relationships = list(store.relationships)
        generator = _ConcurrentGenerator(fail_topic="D")
        builder = TopicGraphBuilder(
            store, generator, batch_size=3, batch_overlap=0, batch_concurrency=2
        )

        with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            await builder.build("project-1", ["A", "B", "C", "D", "E", "F"], True)

        self.assertEqual(original_relationships, store.relationships)
        self.assertEqual([], store.cleared_projects)
        self.assertEqual([], store.upserted_edges)

    async def test_batch_concurrency_is_bounded(self):
        generator = _ConcurrentGenerator()
        builder = TopicGraphBuilder(
            _InMemoryStore(),
            generator,
            batch_size=3,
            batch_overlap=0,
        )

        await builder.build("project-1", list("ABCDEFGHIJKL"), True)

        self.assertEqual(2, generator.peak_concurrency)

    async def test_batch_concurrency_is_shared_across_projects(self):
        generator = _ConcurrentGenerator()
        builder = TopicGraphBuilder(
            _InMemoryStore(),
            generator,
            batch_size=3,
            batch_overlap=0,
            batch_concurrency=2,
        )

        await asyncio.gather(
            builder.build("project-1", list("ABCDEF"), True),
            builder.build("project-2", list("GHIJKL"), True),
        )

        self.assertEqual(2, generator.peak_concurrency)

    async def test_successful_replacement_happens_after_ordered_generation(self):
        events = []
        store = _InMemoryStore(existing=True, events=events)
        generator = _ConcurrentGenerator(events=events)
        builder = TopicGraphBuilder(
            store, generator, batch_size=3, batch_overlap=0, batch_concurrency=2
        )

        result = await builder.build(
            "project-1", ["A", "B", "C", "D", "E", "F"], True
        )

        self.assertEqual({"generate:A", "generate:D"}, set(events[:2]))
        self.assertEqual({"generated:A", "generated:D"}, set(events[2:4]))
        self.assertEqual(["replace"], events[4:])
        self.assertEqual(
            [("A", "B"), ("D", "E")],
            [(edge["from_topic"], edge["to_topic"]) for edge in store.relationships],
        )
        self.assertEqual(2, result["edges_created"])

    async def test_older_cross_process_build_cannot_replace_newer_graph(self):
        class WorkerOneBuilder(TopicGraphBuilder):
            _build_locks = WeakValueDictionary()
            _locks_meta_lock = asyncio.Lock()

        class WorkerTwoBuilder(TopicGraphBuilder):
            _build_locks = WeakValueDictionary()
            _locks_meta_lock = asyncio.Lock()

        store = _InMemoryStore(existing=True)
        old_builder = WorkerOneBuilder(
            store,
            _DelayedGenerator(
                0.05,
                {
                    "from_topic": "Old",
                    "to_topic": "Graph",
                    "relation_type": "related",
                    "weight": 0.5,
                },
            ),
        )
        new_builder = WorkerTwoBuilder(
            store,
            _DelayedGenerator(
                0.01,
                {
                    "from_topic": "New",
                    "to_topic": "Graph",
                    "relation_type": "related",
                    "weight": 0.5,
                },
            ),
        )

        old_task = asyncio.create_task(old_builder.build("project-1", ["A", "B"], True))
        await asyncio.sleep(0.005)
        new_result = await new_builder.build("project-1", ["A", "B"], True)
        old_result = await old_task

        self.assertEqual(1, new_result["edges_created"])
        self.assertEqual(0, old_result["edges_created"])
        self.assertIn("superseded", old_result["message"].lower())
        self.assertEqual("New", store.relationships[0]["from_topic"])


class LLMRelationshipGeneratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_normalizes_model_output(self):
        response = json.dumps(
            [
                {
                    "from_topic": "topic a",
                    "to_topic": "TOPIC B",
                    "relation_type": "builds_on",
                    "weight": 2,
                },
                {
                    "from_topic": "Invented Topic",
                    "to_topic": "Topic B",
                    "relation_type": "related",
                },
            ]
        )
        llm = _LLM(f"```json\n{response}\n```")
        generator = LLMRelationshipGenerator(llm)

        edges = await generator.generate(
            "project-1", ["Topic A", "Topic B"], ["Topic A", "Topic B"]
        )

        self.assertEqual(1, len(edges))
        self.assertEqual("Topic A", edges[0]["from_topic"])
        self.assertEqual("Topic B", edges[0]["to_topic"])
        self.assertEqual("prerequisite", edges[0]["relation_type"])
        self.assertEqual(1.0, edges[0]["weight"])
        self.assertEqual(4000, llm.calls[0][1]["max_tokens"])

    async def test_generate_repairs_a_truncated_array(self):
        llm = _LLM(
            '[{"from_topic":"A","to_topic":"B",'
            '"relation_type":"related","weight":0.5}, {'
        )
        generator = LLMRelationshipGenerator(llm)

        edges = await generator.generate("project-1", ["A", "B"], ["A", "B"])

        self.assertEqual(1, len(edges))
        self.assertEqual(("A", "B"), (edges[0]["from_topic"], edges[0]["to_topic"]))

    async def test_provider_failure_is_not_reported_as_empty_relationships(self):
        class FailingLLM:
            async def chat_completion(self, messages, **kwargs):
                raise RuntimeError("provider unavailable")

        generator = LLMRelationshipGenerator(FailingLLM())

        with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            await generator.generate("project-1", ["A", "B"], ["A", "B"])

    async def test_valid_empty_relationships_are_successful(self):
        generator = LLMRelationshipGenerator(_LLM("[]"))

        edges = await generator.generate("project-1", ["A", "B"], ["A", "B"])

        self.assertEqual([], edges)

    async def test_unparseable_response_fails_generation(self):
        generator = LLMRelationshipGenerator(_LLM("not json"))

        with self.assertRaisesRegex(ValueError, "no JSON array"):
            await generator.generate("project-1", ["A", "B"], ["A", "B"])


class SupabaseTopicGraphStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_atomic_rpc_fails_without_destructive_fallback(self):
        class Request:
            def execute(self):
                raise RuntimeError(
                    "PGRST202 Could not find function replace_topic_graph_relationships"
                )

        class Client:
            def rpc(self, name, payload):
                return Request()

        store = SupabaseTopicGraphStore(Client())

        with self.assertRaisesRegex(RuntimeError, "migrations 004/006"):
            await store.replace_relationships(
                "project-1", [], "2026-08-22T00:00:00+00:00"
            )


if __name__ == "__main__":
    unittest.main()
