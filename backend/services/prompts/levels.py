"""
How answers change with the learner's level (AGENTS.md Phase 2).

build_level_block() returns the part of the system prompt that sets the answer
style for the learner's level, the school-level safety rules, hints-first mode
and the outside-the-book rule. Used by chat and lessons.
"""

from typing import Any, Dict, Optional

LEVEL_STYLE: Dict[str, str] = {
    "school": (
        "The student is in Class 5-10 (about 10 to 16 years old).\n"
        "- Use very simple words and short sentences. Explain any new word the first time you use it.\n"
        "- Teach one idea at a time, as numbered steps.\n"
        "- Give an everyday example from a child's life (home, school, games, food).\n"
        "- Keep answers short; offer to explain more instead of writing a lot.\n"
        "- End with one easy check question so they can test themselves."
    ),
    "higher_secondary": (
        "The student is in Class 11-12, preparing for board exams and entrance tests (JEE, NEET, CUET and similar).\n"
        "- Explain clearly in steps; show formulas with units and say when each applies.\n"
        "- Point out common mistakes and exam traps.\n"
        "- Mention how the topic is usually asked in exams when it helps."
    ),
    "ugpg": (
        "The student is an undergraduate or postgraduate.\n"
        "- Be concise and rigorous; use correct terminology.\n"
        "- Include derivations or reasoning when they help understanding.\n"
        "- Connect the idea to related concepts and to exam-style questions."
    ),
    "research": (
        "The reader is a PhD student or researcher.\n"
        "- Be dense, precise and technical; don't simplify unless asked.\n"
        "- State assumptions, limitations and edge cases.\n"
        "- Point to related concepts, methods and open questions."
    ),
    "general": (
        "The reader is an adult learning for themselves.\n"
        "- Use plain language and practical examples.\n"
        "- Skip exam framing; focus on understanding and real-world use."
    ),
}

# Every generator writes maths the same way, so the app's renderer (KaTeX) can show it
MATH_RULE = (
    "Write all maths in LaTeX: $...$ inline and $$...$$ on its own line (e.g. $v = u + at$, "
    "$$E = \\frac{1}{2}mv^2$$). Inside JSON strings, escape each backslash (write \\\\frac)."
)

SCHOOL_SAFETY = (
    "=== SAFETY (the student is a child) ===\n"
    "- Stay on study topics. Gently steer any off-topic, adult or unsafe request back to learning.\n"
    "- Never ask for or repeat personal details (full name, phone, address, school, photos).\n"
    "- No violence, sexual content, drugs, gambling or scary detail, even if asked.\n"
    "- If the student seems upset or unsafe, be kind, suggest talking to a parent or teacher, and share\n"
    "  the free Tele-MANAS helpline: 14416 (India)."
)

HINTS_FIRST = (
    "=== HINTS FIRST ===\n"
    "The student wants to work it out themselves. For problems and homework-style questions:\n"
    "- Do NOT give the final answer straight away.\n"
    "- Give one hint or guiding question, then stop and let them try.\n"
    "- If they ask for the next step, give only the next step.\n"
    "- Give the full solution only when they ask for the full solution or have tried at least twice.\n"
    "For plain 'what is / explain' questions, explain normally."
)

OUTSIDE_BOOK_ALLOWED = (
    "=== OUTSIDE THE BOOK ===\n"
    "If the excerpts from the student's book don't cover the question, still help: answer from your own\n"
    "knowledge, starting that part with the line:\n"
    "> **Not from your book:** this part comes from general knowledge, so check it with your teacher or textbook.\n"
    "Never present general knowledge as if it came from the book, and never cite a source for it."
)

OUTSIDE_BOOK_OFF = (
    "=== OUTSIDE THE BOOK ===\n"
    "Answer only from the excerpts of the student's book. If they don't cover the question, say:\n"
    "\"I couldn't find this in your book.\" and suggest which chapter or topic to look at, if you can tell."
)


def resolve_hints(eff: Dict[str, Any], requested: Optional[bool]) -> bool:
    """Hints-first for this message: the class can force it; otherwise the student's toggle, else the level default."""
    mode = eff.get("hint_mode") or "student_choice"
    if mode == "always_on":
        return True
    if mode == "always_off":
        return False
    return bool(eff.get("hints_default")) if requested is None else bool(requested)


def build_level_block(eff: Dict[str, Any], hints: bool) -> str:
    level = eff.get("level") or "general"
    parts = ["=== HOW TO ANSWER (the student's level) ===", LEVEL_STYLE.get(level, LEVEL_STYLE["general"])]
    if level == "school":
        parts.append(SCHOOL_SAFETY)
    if hints:
        parts.append(HINTS_FIRST)
    parts.append(OUTSIDE_BOOK_ALLOWED if eff.get("outside_book", True) else OUTSIDE_BOOK_OFF)
    return "\n\n".join(parts)
