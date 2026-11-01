"""Photo questions: image checks, model capability, the chat pipeline, safety and caching."""

import asyncio
import base64
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.v1.endpoints import chat
from services import llm_service as ls
from services import photo_questions as pq

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


def url(data, mime="image/jpeg"):
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def run(c):
    return asyncio.run(c)


def test_decode_accepts_real_images_and_rejects_others(monkeypatch):
    assert pq.decode(url(JPEG)).mime == "image/jpeg"
    assert pq.decode(url(PNG, "image/png")).mime == "image/png"
    for bad in ("not a data url", url(b"GIF89a" + b"\x00" * 50, "image/jpeg"), "data:text/plain;base64,aGk="):
        with pytest.raises(pq.PhotoError):
            pq.decode(bad)
    monkeypatch.setattr(pq.settings, "CHAT_IMAGE_MAX_BYTES", 100)
    with pytest.raises(pq.PhotoError, match="too large"):
        pq.decode(url(JPEG))


def test_vision_follows_the_plan_and_capability(monkeypatch):
    s = ls.settings
    monkeypatch.setattr(s, "SMALL_LLM_VISION", False)
    monkeypatch.setattr(s, "BIG_LLM_VISION", False)
    monkeypatch.setattr(s, "BIG_LLM_MODEL", "")
    assert ls.vision_config("free") is None
    monkeypatch.setattr(s, "SMALL_LLM_VISION", True)
    assert ls.vision_config("free").role == "small"
    monkeypatch.setattr(s, "BIG_LLM_MODEL", "big-m")
    assert ls.vision_config("topper") is None            # paid users read photos with the big model, which can't
    monkeypatch.setattr(s, "BIG_LLM_VISION", True)
    assert ls.vision_config("topper").role == "big" and ls.vision_config("free").role == "small"


@pytest.fixture
def pipeline(monkeypatch):
    state = {"consumed": [], "stored": [], "read": [], "level": "higher_secondary", "unsafe": False,
             "tools": ["chat", "image"], "vision": True}

    async def assert_tool(uid, tool):
        if tool not in state["tools"]:
            raise HTTPException(403, "off")

    async def plan(uid):
        return "free"

    async def consume(uid, feature, amount=1):
        state["consumed"].append(feature)

    async def eff(uid):
        return {"level": state["level"]}

    async def read(photo, level, plan=None):
        state["read"].append(level)
        return ("QUESTION: Find the acceleration of a 2 kg block pushed with $10\\,N$.\nDIAGRAM: block, arrow 10 N", False) \
            if not state["unsafe"] else ("", True)

    async def store(uid, photo):
        state["stored"].append(uid)
        return f"{uid}/abc.jpg"

    monkeypatch.setattr(chat, "assert_tool", assert_tool)
    monkeypatch.setattr(chat.usage, "plan", plan)
    monkeypatch.setattr(chat.usage, "consume", consume)
    monkeypatch.setattr(chat.levels, "effective_for", eff)
    monkeypatch.setattr(pq, "read_photo", read)
    monkeypatch.setattr(pq, "store", store)
    monkeypatch.setattr(ls, "vision_config", lambda plan=None: object() if state["vision"] else None)
    return state


def req(**kw):
    return chat.ChatRequest(project_id="p", message=kw.pop("message", "How do I solve this?"), **kw)


def test_photo_becomes_part_of_the_question(pipeline):
    r = req(image=url(JPEG), image_path="someone-else/secret.jpg")
    assert run(chat._attach_photo(r, {"id": "u1"})) is None
    assert r.message.startswith("How do I solve this?") and pq.PHOTO_MARKER in r.message
    assert "acceleration of a 2 kg block" in r.message
    assert r.image_path == "u1/abc.jpg" and r.image is None
    assert pipeline["consumed"] == ["image"]


def test_no_photo_changes_nothing(pipeline):
    r = req(image_path="someone-else/secret.jpg")
    assert run(chat._attach_photo(r, {"id": "u1"})) is None
    assert r.image_path is None and r.message == "How do I solve this?" and pipeline["consumed"] == []


def test_unsuitable_photo_for_a_child_gets_a_gentle_reply(pipeline):
    pipeline["level"], pipeline["unsafe"] = "school", True
    r = req(image=url(JPEG))
    assert run(chat._attach_photo(r, {"id": "u1"})) == pq.UNSAFE_REPLY
    assert pipeline["stored"] == [] and pq.PHOTO_MARKER not in r.message


def test_refused_without_the_tool_or_a_capable_model_or_a_real_image(pipeline):
    pipeline["tools"] = ["chat"]
    with pytest.raises(HTTPException) as e:
        run(chat._attach_photo(req(image=url(JPEG)), {"id": "u1"}))
    assert e.value.status_code == 403
    pipeline["tools"], pipeline["vision"] = ["chat", "image"], False
    with pytest.raises(HTTPException) as e:
        run(chat._attach_photo(req(image=url(JPEG)), {"id": "u1"}))
    assert e.value.status_code == 403
    pipeline["vision"] = True
    with pytest.raises(HTTPException) as e:
        run(chat._attach_photo(req(image="data:image/jpeg;base64,aGVsbG8="), {"id": "u1"}))
    assert e.value.status_code == 400 and pipeline["consumed"] == []   # a bad photo doesn't use up the quota


def test_photo_questions_skip_the_shared_answer_cache():
    r = SimpleNamespace(system_prompt=None, hints=None, message=pq.with_photo("Explain", "QUESTION: x"))
    assert run(chat._answer_cache_plan(r, [], {"level": "school"})) is None


def test_photo_tool_hidden_when_the_model_cannot_see(monkeypatch):
    from api.v1.endpoints import levels as lv

    async def plan(uid):
        return "free"
    monkeypatch.setattr("services.usage_service.usage.plan", plan)
    monkeypatch.setattr(ls, "vision_config", lambda plan=None: None)
    out = run(lv.with_photo_availability({"tools": ["chat", "image"]}, "u"))
    assert out["tools"] == ["chat"]
    monkeypatch.setattr(ls, "vision_config", lambda plan=None: object())
    assert run(lv.with_photo_availability({"tools": ["chat", "image"]}, "u"))["tools"] == ["chat", "image"]


def test_read_photo_uses_the_child_check_only_for_school(monkeypatch):
    prompts = []

    async def vision(prompt, data_url, max_tokens=800, plan=None):
        prompts.append(prompt)
        return "UNSAFE" if "child" in prompt else "QUESTION: 2+2\nDIAGRAM: none"
    monkeypatch.setattr(ls.llm_service, "vision_completion", vision)
    photo = pq.decode(url(JPEG))
    assert run(pq.read_photo(photo, "school")) == ("", True)
    assert run(pq.read_photo(photo, "ugpg")) == ("QUESTION: 2+2\nDIAGRAM: none", False)
    assert "child" in prompts[0] and "child" not in prompts[1]
