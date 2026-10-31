"""Which chat messages may use the shared answer cache."""

import asyncio
from types import SimpleNamespace

from api.v1.endpoints import chat
from services.shared_content import Scope


def req(**kw):
    base = dict(project_id="p", selected_documents=None, system_prompt=None, hints=None, deep=False)
    return SimpleNamespace(**{**base, **kw})


EFF = {"level": "school", "hint_mode": "student_choice", "hints_default": False, "outside_book": True}


def plan(monkeypatch, request, history=None, eff=EFF, shared=True):
    async def scope_for(project_id, docs):
        return Scope(roots=["root"], by_doc={"d": "root"}) if shared else None
    monkeypatch.setattr(chat.shared_content, "scope_for", scope_for)
    return asyncio.run(chat._answer_cache_plan(request, history or [], eff))


def test_first_question_on_a_shared_book_is_cacheable(monkeypatch):
    assert plan(monkeypatch, req()) is not None


def test_follow_ups_personal_books_hints_and_custom_prompts_are_not(monkeypatch):
    assert plan(monkeypatch, req(), history=[{"role": "user", "content": "hi"}]) is None
    assert plan(monkeypatch, req(), shared=False) is None
    assert plan(monkeypatch, req(hints=True)) is None
    assert plan(monkeypatch, req(), eff={**EFF, "hint_mode": "always_on"}) is None
    assert plan(monkeypatch, req(system_prompt="Talk like a pirate")) is None


def test_deep_and_level_change_the_key(monkeypatch):
    k1 = plan(monkeypatch, req())[1]
    assert plan(monkeypatch, req(deep=True))[1] != k1
    assert plan(monkeypatch, req(), eff={**EFF, "level": "ugpg"})[1] != k1
