import asyncio
import json
import unittest

from services.topic_graph_builder import LLMRelationshipGenerator, TopicGraphBuilder


class _InMemoryStore:
    def __init__(self, existing=False):
        self.existing = existing
        self.cleared_projects = []
        self.upserted_edges = []

    async def has_relationships(self, project_id):
        return self.existing

    async def clear_relationships(self, project_id):
        self.cleared_projects.append(project_id)
        self.existing = False

    async def upsert_relationships(self, edges):
        self.upserted_edges.extend(edges)
        self.existing = bool(edges)


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
        builder = TopicGraphBuilder(store, generator, inter_batch_delay_seconds=0)

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
        delays = []

        async def record_delay(delay):
            delays.append(delay)

        builder = TopicGraphBuilder(
            store,
            generator,
            batch_size=4,
            batch_overlap=1,
            inter_batch_delay_seconds=0.5,
            sleep=record_delay,
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
        self.assertEqual([0.5], delays)

    async def test_concurrent_build_for_same_project_returns_without_waiting(self):
        generator = _BlockingGenerator()
        builder = TopicGraphBuilder(
            _InMemoryStore(), generator, inter_batch_delay_seconds=0
        )

        first = asyncio.create_task(builder.build("project-1", ["A", "B"], True))
        await generator.started.wait()
        second = await builder.build("project-1", ["A", "B"], True)
        generator.release.set()
        await first

        self.assertEqual(
            {"edges_created": 0, "message": "Build already in progress"}, second
        )

    async def test_operational_failure_is_returned_at_the_interface(self):
        class BrokenStore(_InMemoryStore):
            async def has_relationships(self, project_id):
                raise RuntimeError("database unavailable")

        builder = TopicGraphBuilder(
            BrokenStore(), _RelationshipGenerator(), inter_batch_delay_seconds=0
        )

        result = await builder.build("project-1", ["A", "B"])

        self.assertEqual(0, result["edges_created"])
        self.assertEqual("Error: database unavailable", result["message"])


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


if __name__ == "__main__":
    unittest.main()
