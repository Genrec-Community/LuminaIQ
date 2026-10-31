"""Level-aware answer rules, hints-first resolution, outside-book rule and child safety."""

import asyncio

import pytest

from services import safety
from services.prompts.levels import build_level_block, resolve_hints


def eff(level="school", hint_mode="student_choice", hints_default=False, outside_book=True):
    return {"level": level, "hint_mode": hint_mode, "hints_default": hints_default, "outside_book": outside_book}


def test_level_block_in_system_prompt():
    school = build_level_block(eff("school"), hints=False)
    research = build_level_block(eff("research"), hints=False)
    assert "Class 5" in school and "step" in school.lower()
    assert "SAFETY" in school and "SAFETY" not in research
    assert "technical" in research.lower()
    assert build_level_block(eff(None), hints=False)   # no level yet: still a sensible default


def test_hints_resolution():
    assert resolve_hints(eff(hint_mode="always_on"), requested=False) is True
    assert resolve_hints(eff(hint_mode="always_off"), requested=True) is False
    assert resolve_hints(eff(), requested=True) is True
    assert resolve_hints(eff(), requested=None) is False
    assert resolve_hints(eff(hints_default=True), requested=None) is True
    block = build_level_block(eff(), hints=True)
    assert "HINTS FIRST" in block and "full solution" in block.lower()


def test_outside_book_rule_toggles():
    on = build_level_block(eff(outside_book=True), hints=False)
    off = build_level_block(eff(outside_book=False), hints=False)
    assert "Not from your book" in on
    assert "Not from your book" not in off and "couldn't find" in off.lower()


@pytest.mark.parametrize("text", ["I want to kill myself", "i feel like ending my life", "how to self harm",
                                  "I want to die", "mujhe marna hai"])
def test_school_distress_gets_helpline(text, monkeypatch):
    recorded = []
    monkeypatch.setattr(safety, "_record", lambda *a: recorded.append(a) or asyncio.sleep(0))
    reply = asyncio.run(safety.screen(text, "school", "u1"))
    assert reply and "14416" in reply
    assert recorded and recorded[0][2] == "distress"


def test_safety_only_for_school(monkeypatch):
    monkeypatch.setattr(safety, "_record", lambda *a: asyncio.sleep(0))
    assert asyncio.run(safety.screen("I want to die", "research", "u1")) is None
    assert asyncio.run(safety.screen("What is photosynthesis?", "school", "u1")) is None
    assert asyncio.run(safety.screen("The character dies in chapter 3", "school", "u1")) is None
