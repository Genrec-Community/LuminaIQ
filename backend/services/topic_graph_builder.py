"""Build and persist Topic Graph relationships behind one interface."""

import asyncio
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, TypedDict
from uuid import uuid4
from weakref import WeakValueDictionary

from utils.logger import logger


class GraphBuildResult(TypedDict):
    edges_created: int
    message: str


class TopicGraphStore(Protocol):
    async def request_build(
        self,
        project_id: str,
        source_fingerprint: str,
        request_id: str,
        requested_at: str,
        force_rebuild: bool,
    ) -> bool: ...

    async def replace_relationships(
        self,
        project_id: str,
        edges: List[Dict[str, Any]],
        source_fingerprint: str,
        request_id: str,
    ) -> bool: ...


class RelationshipGenerator(Protocol):
    async def generate(
        self, project_id: str, batch_topics: List[str], all_topics: List[str]
    ) -> List[Dict[str, Any]]: ...


def canonical_topics(topics: List[str]) -> List[str]:
    """Normalize, deduplicate, and sort the Topic source deterministically."""
    normalized = {
        unicodedata.normalize("NFC", topic.strip())
        for topic in topics
        if isinstance(topic, str) and topic.strip()
    }
    return sorted(normalized, key=lambda topic: (topic.casefold(), topic))


def topic_source_fingerprint(topics: List[str]) -> str:
    """Hash the compact UTF-8 JSON encoding of canonical Topics."""
    unique_topics = canonical_topics(topics)
    encoded_topics = json.dumps(
        unique_topics, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded_topics).hexdigest()


class TopicGraphBuilder:
    """Generate a complete Topic Graph with process-local per-project locking."""

    _build_locks: WeakValueDictionary = WeakValueDictionary()
    _locks_meta_lock = asyncio.Lock()

    def __init__(
        self,
        store: TopicGraphStore,
        generator: RelationshipGenerator,
        *,
        batch_size: int = 25,
        batch_overlap: int = 5,
        batch_concurrency: int = 2,
    ):
        if batch_size <= batch_overlap:
            raise ValueError("batch_size must be greater than batch_overlap")
        if batch_concurrency < 1:
            raise ValueError("batch_concurrency must be at least 1")
        self._store = store
        self._generator = generator
        self._batch_size = batch_size
        self._batch_overlap = batch_overlap
        self._batch_concurrency = batch_concurrency
        self._batch_semaphore = asyncio.Semaphore(batch_concurrency)

    async def build(
        self, project_id: str, topics: List[str], force_rebuild: bool = False
    ) -> GraphBuildResult:
        """Build serially per project, raising operational errors to the caller."""
        project_lock = await self._get_project_lock(project_id)
        async with project_lock:
            return await self._build_locked(project_id, topics, force_rebuild)

    async def _get_project_lock(self, project_id: str) -> asyncio.Lock:
        async with self._locks_meta_lock:
            lock = self._build_locks.get(project_id)
            if lock is None:
                lock = asyncio.Lock()
                self._build_locks[project_id] = lock
            return lock

    async def _build_locked(
        self, project_id: str, topics: List[str], force_rebuild: bool
    ) -> GraphBuildResult:
        unique_topics = canonical_topics(topics)
        source_fingerprint = topic_source_fingerprint(unique_topics)
        request_id = str(uuid4())
        requested_at = datetime.now(timezone.utc).isoformat()
        should_build = await self._store.request_build(
            project_id,
            source_fingerprint,
            request_id,
            requested_at,
            force_rebuild,
        )
        if not should_build:
            return {
                "edges_created": 0,
                "message": "Topic Graph source is unchanged",
            }

        if len(unique_topics) < 2:
            published = await self._store.replace_relationships(
                project_id, [], source_fingerprint, request_id
            )
            if not published:
                return {
                    "edges_created": 0,
                    "message": "Build superseded by a newer Topic Graph build",
                }
            return {"edges_created": 0, "message": "Need at least 2 topics"}

        logger.info(f"Building Topic Graph for {len(unique_topics)} topics")
        batches = self._create_batches(unique_topics)
        async def generate_batch(index: int, batch: List[str]):
            async with self._batch_semaphore:
                logger.info(
                    f"Processing batch {index + 1}/{len(batches)} ({len(batch)} topics)"
                )
                return await self._generator.generate(project_id, batch, unique_topics)

        tasks = [
            asyncio.create_task(generate_batch(index, batch))
            for index, batch in enumerate(batches)
        ]
        try:
            batch_edges = await asyncio.gather(*tasks)
        except Exception as error:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.exception(f"Error generating Topic Graph: {error}")
            raise

        unique_edges = self._deduplicate(
            [edge for edges in batch_edges for edge in edges]
        )

        # Publish only after every provider batch has completed successfully.
        published = await self._store.replace_relationships(
            project_id, unique_edges, source_fingerprint, request_id
        )
        if not published:
            return {
                "edges_created": 0,
                "message": "Build superseded by a newer Topic Graph build",
            }

        if unique_edges:
            logger.info(
                f"Published {len(unique_edges)} topic relationships for {project_id}"
            )

        return {
            "edges_created": len(unique_edges),
            "message": f"Successfully created {len(unique_edges)} relationships",
        }

    def _create_batches(self, topics: List[str]) -> List[List[str]]:
        if len(topics) <= self._batch_size:
            return [topics]

        stride = self._batch_size - self._batch_overlap
        return [
            topics[index : index + self._batch_size]
            for index in range(0, len(topics), stride)
            if len(topics[index : index + self._batch_size]) >= 3
        ]

    @staticmethod
    def _deduplicate(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique_edges = []
        for edge in edges:
            key = (edge["from_topic"], edge["to_topic"])
            if key not in seen:
                seen.add(key)
                unique_edges.append(edge)
        return unique_edges


class SupabaseTopicGraphStore:
    """Production adapter for Topic Graph persistence."""

    def __init__(self, client=None):
        if client is None:
            from db.client import get_supabase_client

            client = get_supabase_client()
        self._client = client

    async def request_build(
        self,
        project_id: str,
        source_fingerprint: str,
        request_id: str,
        requested_at: str,
        force_rebuild: bool,
    ) -> bool:
        from db.client import async_db

        try:
            result = await async_db(
                lambda: self._client.rpc(
                    "request_topic_graph_build",
                    {
                        "p_project_id": project_id,
                        "p_source_fingerprint": source_fingerprint,
                        "p_request_id": request_id,
                        "p_requested_at": requested_at,
                        "p_force_rebuild": force_rebuild,
                    },
                ).execute()
            )
            return self._read_boolean_rpc(result.data, "Topic Graph request RPC")
        except Exception as error:
            self._raise_missing_migration(error, "request_topic_graph_build")
            raise

    async def replace_relationships(
        self,
        project_id: str,
        edges: List[Dict[str, Any]],
        source_fingerprint: str,
        request_id: str,
    ) -> bool:
        from db.client import async_db

        try:
            result = await async_db(
                lambda: self._client.rpc(
                    "replace_topic_graph_relationships",
                    {
                        "p_project_id": project_id,
                        "p_edges": edges,
                        "p_source_fingerprint": source_fingerprint,
                        "p_request_id": request_id,
                    },
                ).execute()
            )
            return self._read_boolean_rpc(result.data, "Topic Graph publication RPC")
        except Exception as error:
            self._raise_missing_migration(error, "replace_topic_graph_relationships")
            raise

    @staticmethod
    def _read_boolean_rpc(data: Any, operation: str) -> bool:
        if isinstance(data, bool):
            return data
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], bool):
            return data[0]
        raise RuntimeError(f"{operation} returned an invalid result")

    @staticmethod
    def _raise_missing_migration(error: Exception, rpc_name: str) -> None:
        message = str(error)
        missing_rpc = "PGRST202" in message or (
            rpc_name in message
            and ("not find" in message.lower() or "404" in message)
        )
        if missing_rpc:
            raise RuntimeError(
                "Topic Graph migration 007 is not installed; refusing to build"
            ) from error


class LLMRelationshipGenerator:
    """Production adapter that turns one topic batch into relationships."""

    def __init__(self, llm=None, max_tokens: int = 4000):
        if llm is None:
            from services.llm_service import llm_service

            llm = llm_service
        self._llm = llm
        self._max_tokens = max_tokens

    async def generate(
        self, project_id: str, batch_topics: List[str], all_topics: List[str]
    ) -> List[Dict[str, Any]]:
        topics_str = "\n".join(
            f"{index + 1}. {topic}" for index, topic in enumerate(batch_topics)
        )
        target_relationships = max(15, len(batch_topics) * 2)
        prompt = f"""You are an expert curriculum designer. Create a learning dependency graph for these topics.

TOPICS:
{topics_str}

TASK: Identify which topics must be learned before others.

RELATIONSHIP TYPES:
- "prerequisite": Topic A MUST be learned before Topic B
- "related": Topics are connected but order doesn't matter

RULES:
1. Use EXACT topic names from the numbered list (copy exactly)
2. Every topic should connect to at least one other topic
3. Foundational/intro topics have no prerequisites
4. Create {target_relationships} relationships total
5. Weight: 0.9 = essential prerequisite, 0.5 = helpful, 0.3 = loosely related

OUTPUT FORMAT - Return ONLY valid JSON, no markdown:
[
  {{"from_topic": "Topic 1 Name", "to_topic": "Topic 2 Name", "relation_type": "prerequisite", "weight": 0.9}}
]"""
        try:
            response = await self._llm.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=self._max_tokens,
            )
        except Exception as error:
            logger.error(f"LLM call failed for Topic Graph batch: {error}")
            raise

        relations = self._parse_json_with_repair(response)
        topics_by_normalized_name = {
            topic.lower().strip(): topic for topic in all_topics
        }
        edges = []
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            from_raw = relation.get("from_topic", "").strip()
            to_raw = relation.get("to_topic", "").strip()
            if (
                from_raw.lower() not in topics_by_normalized_name
                or to_raw.lower() not in topics_by_normalized_name
            ):
                continue

            from_topic = topics_by_normalized_name[from_raw.lower()]
            to_topic = topics_by_normalized_name[to_raw.lower()]
            if from_topic == to_topic:
                continue

            relation_type = relation.get("relation_type", "related")
            if relation_type in ("builds_on", "subtopic"):
                relation_type = "prerequisite"
            elif relation_type not in ("prerequisite", "related"):
                relation_type = "related"

            edges.append(
                {
                    "id": str(uuid4()),
                    "project_id": project_id,
                    "from_topic": from_topic,
                    "to_topic": to_topic,
                    "relation_type": relation_type,
                    "weight": min(1.0, max(0.1, float(relation.get("weight", 0.5)))),
                }
            )

        logger.info(f"Generated {len(edges)} edges from batch")
        return edges

    def _parse_json_with_repair(self, response: str) -> List[Dict[str, Any]]:
        if not response:
            raise ValueError("Topic Graph provider returned an empty response")

        clean_response = response.strip()
        if clean_response.startswith("```"):
            lines = clean_response.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_response = "\n".join(lines)

        start = clean_response.find("[")
        if start == -1:
            logger.warning("No JSON array start '[' found")
            raise ValueError("Topic Graph provider response has no JSON array")

        end = clean_response.rfind("]")
        if end > start:
            try:
                return json.loads(clean_response[start : end + 1])
            except json.JSONDecodeError as error:
                logger.warning(f"JSON parse error: {error}")

        logger.warning("JSON appears truncated, attempting repair...")
        json_str = clean_response[start:]
        repaired = self._repair_truncated_json_array(json_str)
        if repaired:
            try:
                result = json.loads(repaired)
                logger.info(
                    f"Successfully repaired JSON, got {len(result)} relationships"
                )
                return result
            except json.JSONDecodeError:
                pass

        objects = self._extract_json_objects(json_str)
        if objects:
            logger.info(f"Extracted {len(objects)} objects from truncated JSON")
            return objects

        logger.error("Failed to parse or repair JSON response")
        raise ValueError("Topic Graph provider response is not valid JSON")

    @staticmethod
    def _repair_truncated_json_array(json_str: str) -> Optional[str]:
        last_complete = json_str.rfind("}")
        if last_complete == -1:
            return None
        return json_str[: last_complete + 1].rstrip().rstrip(",") + "]"

    @staticmethod
    def _extract_json_objects(json_str: str) -> List[Dict[str, Any]]:
        objects = []
        depth = 0
        current_obj = ""
        in_string = False
        escape_next = False

        for char in json_str:
            if escape_next:
                current_obj += char
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                current_obj += char
                continue
            if char == '"':
                in_string = not in_string
            if not in_string:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
            if depth > 0 or char == "{":
                current_obj += char
            if depth == 0 and current_obj.strip():
                try:
                    obj = json.loads(current_obj)
                    if (
                        isinstance(obj, dict)
                        and "from_topic" in obj
                        and "to_topic" in obj
                    ):
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                current_obj = ""

        return objects
