"""LaTeX survives model JSON (quizzes, flashcards, mindmaps)."""

import pytest

from utils.json_latex import extract, loads, repair


def test_latex_commands_keep_their_backslash():
    raw = r'{"q": "Kinetic energy is $\frac{1}{2}mv^2$, angle $\theta$, $\nabla \cdot E$, $\sigma$, $\times$, $\beta$"}'
    out = loads(raw)["q"]
    for cmd in (r"\frac{1}{2}", r"\theta", r"\nabla", r"\cdot", r"\sigma", r"\times", r"\beta"):
        assert cmd in out


def test_real_json_escapes_still_work():
    out = loads(r'{"a": "line one\nThe next line", "b": "tab\there", "c": "say \"hi\"", "d": "é", "e": "a\\b"}')
    assert out == {"a": "line one\nThe next line", "b": "tab\there", "c": 'say "hi"', "d": "é", "e": "a\\b"}


def test_already_escaped_latex_is_left_alone():
    assert loads(r'{"q": "$\\frac{a}{b}$ and $\\alpha$"}')["q"] == r"$\frac{a}{b}$ and $\alpha$"


def test_extract_from_a_chatty_reply_with_fences():
    reply = 'Here you go:\n```json\n[{"front": "Area of a circle?", "back": "$\\pi r^2$"}]\n```'
    assert extract(reply, "[") == [{"front": "Area of a circle?", "back": r"$\pi r^2$"}]
    assert extract('{"nodes": [], "edges": []} trailing', "{") == {"nodes": [], "edges": []}
    with pytest.raises(ValueError):
        extract("no json here")


def test_repair_is_idempotent_on_plain_text():
    assert repair('{"a": "no maths"}') == '{"a": "no maths"}'


def test_quiz_parser_keeps_latex():
    from services.mcq_service import MCQService
    reply = r'''[{"question": "What is $\frac{d}{dx}x^2$?", "options": [{"option": "A", "text": "$2x$"},
      {"option": "B", "text": "$x$"}], "correct_answer": "A", "explanation": "Power rule: $\theta$-free, $\nabla$ not needed."}]'''
    q = MCQService()._parse_mcq_response(reply)[0]
    assert r"\frac{d}{dx}" in q["question"] and r"\theta" in q["explanation"] and r"\nabla" in q["explanation"]


def test_flashcard_parser_keeps_latex():
    from services.flashcard_service import FlashcardService
    cards = FlashcardService()._parse_flashcards_response(r'[{"front": "Formula for $\tau$?", "back": "$\tau = r \times F$"}]', 5)
    assert cards[0]["back"] == r"$\tau = r \times F$"
