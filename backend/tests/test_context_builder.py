"""Token budgets for prompt parts."""

from config.settings import settings
from services import context_builder as cb
from services import rag_service
from services.retrieval import Passage


def p(text):
    return Passage(text=text, document_id="d", page=1)


def test_passages_keep_rank_order_and_trim_the_last():
    out = cb.fit_passages([p("a" * 400), p("b" * 400), p("c" * 4000)], budget=300)
    assert [x.text[0] for x in out] == ["a", "b", "c"]
    assert cb.tokens(out[2].text) <= 101 and out[2].text.endswith("…")


def test_tiny_leftovers_are_dropped():
    out = cb.fit_passages([p("a" * 1000), p("b" * 1000)], budget=260)
    assert len(out) == 1


def test_history_keeps_newest_turns_and_starts_with_the_student():
    history = [{"role": "user", "content": "old " * 400}, {"role": "assistant", "content": "x" * 400},
               {"role": "user", "content": "recent question"}, {"role": "assistant", "content": "recent answer"}]
    out = cb.fit_history(history, budget=120)
    assert out[0]["role"] == "user" and out[-1]["content"] == "recent answer"
    assert all("old" not in m["content"] for m in out)


def test_trim_prefers_a_line_end():
    text = "line one is here\n" * 20
    out = cb.trim(text, 20)
    assert out.endswith("…") and len(out) <= 20 * 4 + 2


def test_chat_prompt_respects_budgets(monkeypatch):
    monkeypatch.setattr(settings, "CONTEXT_BUDGET_EXCERPTS", 200)
    monkeypatch.setattr(settings, "CONTEXT_BUDGET_HISTORY", 100)
    passages = [p("Photosynthesis " * 200), p("Respiration " * 200)]
    history = [{"role": "user", "content": "q" * 2000}, {"role": "assistant", "content": "a" * 2000}] * 3
    msgs = rag_service.build_messages("why?", passages, True, history, None)
    system = msgs[0]["content"]
    assert "Respiration" not in system and cb.tokens(system) < cb.tokens(rag_service.BASE_PROMPT) + 400
    assert sum(cb.tokens(m["content"]) for m in msgs[1:-1]) <= 100
