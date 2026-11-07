"""First-question answer cache for shared books (real Postgres)."""

import asyncio
import uuid

import pytest

from config.settings import settings
from db.client import SupabaseClient
from services import answer_cache as ac
from services.shared_content import Scope
from services.telemetry import telemetry


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return self.pg.table(name)


def run(c):
    return asyncio.run(c)


def vec(*hot):
    v = [0.0] * settings.EMBEDDING_DIMENSION
    for i, w in hot:
        v[i] = w
    return v


@pytest.fixture
def cache(pg_client, monkeypatch):
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(pg_client))
    vectors = {}

    async def embed(text):
        return vectors.get(ac.normalise(text), vec((5, 1.0)))
    monkeypatch.setattr("services.embedding_service.embedding_service.generate_embedding", embed)
    root = str(uuid.uuid4())
    alice = Scope(roots=[root], by_doc={"alice-doc": root})
    bob = Scope(roots=[root], by_doc={"bob-doc": root})
    return {"alice": alice, "bob": bob, "root": root, "vectors": vectors, "pg": pg_client}


ANSWER = "Photosynthesis is how plants make food from light [1](1)."


def test_exact_hit_maps_sources_to_the_students_own_copy(cache):
    key = ac.scope_key(cache["alice"], "school", False, True)
    run(ac.store(cache["alice"], key, "What is photosynthesis?", ANSWER,
                 [{"doc_id": "alice-doc", "doc_name": "Bio", "chunk_text": "x", "page": 3}], cost_usd=0.002))
    telemetry._buffer.clear()
    hit = run(ac.lookup(cache["bob"], ac.scope_key(cache["bob"], "school", False, True), "what is  PHOTOSYNTHESIS"))
    assert hit["answer"] == ANSWER and hit["match"] == "exact"
    assert hit["sources"][0]["doc_id"] == "bob-doc" and hit["sources"][0]["page"] == 3
    assert telemetry._buffer[-1]["cache_hit"] and telemetry._buffer[-1]["saved_usd"] == 0.002


def test_semantic_hit_and_miss(cache):
    v = cache["vectors"]
    v[ac.normalise("What is photosynthesis?")] = vec((0, 1.0))
    v[ac.normalise("Explain photosynthesis")] = vec((0, 1.0), (1, 0.1))        # ~0.995 similar
    v[ac.normalise("What is respiration?")] = vec((0, 0.5), (2, 1.0))          # far
    key = ac.scope_key(cache["alice"], "school", False, True)
    run(ac.store(cache["alice"], key, "What is photosynthesis?", ANSWER, []))
    hit = run(ac.lookup(cache["bob"], key, "Explain photosynthesis"))
    assert hit and hit["match"] == "semantic"
    assert run(ac.lookup(cache["bob"], key, "What is respiration?")) is None


def test_level_deep_and_rules_are_separate(cache):
    s = cache["alice"]
    run(ac.store(s, ac.scope_key(s, "school", False, True), "What is a cell?", ANSWER, []))
    for key in (ac.scope_key(s, "ugpg", False, True), ac.scope_key(s, "school", True, True),
                ac.scope_key(s, "school", False, False),
                ac.scope_key(Scope(roots=[str(uuid.uuid4())]), "school", False, True)):
        assert run(ac.lookup(s, key, "What is a cell?")) is None


def test_expired_and_error_answers_are_not_served(cache):
    s = cache["alice"]
    key = ac.scope_key(s, "school", False, True)
    run(ac.store(s, key, "Q one?", "Error: The AI service is busy right now.", []))
    assert run(ac.lookup(s, key, "Q one?")) is None
    run(ac.store(s, key, "Q two?", ANSWER, []))
    cache["pg"].fetch("UPDATE answer_cache SET expires_at = now() - interval '1 day'")
    assert run(ac.lookup(s, key, "Q two?")) is None


def test_disabled_setting(cache, monkeypatch):
    s = cache["alice"]
    key = ac.scope_key(s, "school", False, True)
    run(ac.store(s, key, "Q?", ANSWER, []))
    monkeypatch.setattr(settings, "ANSWER_CACHE_ENABLED", False)
    assert run(ac.lookup(s, key, "Q?")) is None
