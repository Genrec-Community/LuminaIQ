"""Generated quiz questions don't always have the right answer in the same place."""
import asyncio
import json

from services import mcq_service as M


def test_correct_answer_is_not_always_first(monkeypatch):
    qs = [{"question": f"Q{i}", "options": [{"option": L, "text": f"{L}{i}"} for L in "ABCD"],
           "correct_answer": "A", "explanation": "because"} for i in range(12)]

    async def fake_completion(*a, **k):
        return json.dumps(qs)

    async def no_context(*a, **k):
        return "some passage"

    monkeypatch.setattr(M.llm_service, "chat_completion", fake_completion)
    svc = M.MCQService.__new__(M.MCQService)
    monkeypatch.setattr(svc, "_get_context_content", no_context)
    out = asyncio.run(svc.make_questions("p", "topic", 12, None, "medium", "school"))
    assert len(out) == 12
    for q in out:   # the right text is still the right answer
        right = next(o["text"] for o in q["options"] if o["option"] == q["correct_answer"])
        assert right == "A" + q["question"][1:]
    assert len({q["correct_answer"] for q in out}) > 1
