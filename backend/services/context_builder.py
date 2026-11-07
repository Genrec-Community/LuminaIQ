"""
Token budgets for what goes into a prompt (AGENTS.md Phase 4), and the learner context
(Phase 5): what the tutor knows about the student, assembled within its own budget.

Each part of a prompt gets a hard budget, so a long chat, a huge profile or many long
passages can't make one request slow and expensive. Token counts are estimates
(characters / 4), which is close enough for budgeting and needs no tokenizer.

    passages = fit_passages(passages, settings.CONTEXT_BUDGET_EXCERPTS)   # best first, last one trimmed
    history  = fit_history(history, settings.CONTEXT_BUDGET_HISTORY)      # newest turns kept
    profile  = trim(profile, settings.CONTEXT_BUDGET_PROFILE)
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List

CHARS_PER_TOKEN = 4
MIN_USEFUL_TOKENS = 60     # don't keep a sliver of a passage or turn


def tokens(text: str) -> int:
    return (len(text or "") + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def trim(text: str, budget: int) -> str:
    """Text cut to the budget, at a line or sentence end when one is close."""
    text = text or ""
    limit = max(0, budget) * CHARS_PER_TOKEN
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("\n", ". "):
        pos = cut.rfind(sep)
        if pos > limit * 0.7:
            return cut[:pos + 1].rstrip() + " …"
    return cut.rstrip() + " …"


def fit_passages(passages: List[Any], budget: int) -> List[Any]:
    """Passages (objects with .text) in rank order until the budget runs out."""
    out, left = [], budget
    for p in passages:
        cost = tokens(p.text)
        if cost <= left:
            out.append(p)
            left -= cost
        elif left >= MIN_USEFUL_TOKENS:
            out.append(replace(p, text=trim(p.text, left)))
            break
        else:
            break
    return out


def fit_history(history: List[Dict[str, str]], budget: int) -> List[Dict[str, str]]:
    """The most recent turns that fit; an over-long turn is trimmed rather than dropped."""
    kept, left = [], budget
    for m in reversed(history or []):
        cost = tokens(m.get("content", ""))
        if cost <= left:
            kept.append(m)
            left -= cost
        else:
            if left >= MIN_USEFUL_TOKENS:
                kept.append({**m, "content": trim(m["content"], left)})
            break
    kept.reverse()
    # A conversation sent to the model should start with the student's turn
    while kept and kept[0].get("role") == "assistant":
        kept.pop(0)
    return kept


# --------------------------------------------------------------------------- learner context (Phase 5)

def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def learner_block(snapshot, memories: List[Dict[str, Any]], summary: str, budget: int) -> str:
    """
    The "what you know about this student" part of the system prompt: the chat so far
    (summary), weak and strong topics, open mistakes and remembered facts. Parts are added
    in that order of importance until the budget runs out.
    """
    parts: List[str] = []
    if summary:
        parts.append(f"Earlier in this chat (summary):\n{summary.strip()}")
    if snapshot is not None and not snapshot.empty():
        lines = []
        if snapshot.weak:
            lines.append("Finding hard: " + ", ".join(f"{t} ({_pct(m)})" for t, m in snapshot.weak))
        if snapshot.strong:
            lines.append("Comfortable with: " + ", ".join(t for t, _ in snapshot.strong))
        if snapshot.other_books_weak:
            lines.append("Finding hard in other books: " + ", ".join(t for t, _ in snapshot.other_books_weak))
        for m in snapshot.mistakes[:3]:
            why = f" (likely: {m['misconception']})" if m.get("misconception") else ""
            lines.append(f"Recent mistake on {m.get('topic') or 'a question'}: answered "
                         f"\"{m.get('wrong_answer', '')[:80]}\" instead of \"{m.get('correct_answer', '')[:80]}\"{why}")
        if lines:
            parts.append("Learning progress:\n" + "\n".join(f"- {line}" for line in lines))
    if memories:
        parts.append("Remembered about the student:\n" + "\n".join(f"- {m['content']}" for m in memories))
    if not parts:
        return ""
    head = "=== WHAT YOU KNOW ABOUT THIS STUDENT ===\n"
    tail = ("\nUse this to pitch and personalise the explanation (revisit weak spots, address the misconception, "
            "use their interests). Don't recite it back unless they ask what you remember.")
    left = budget - tokens(head + tail)
    kept = []
    for part in parts:
        cost = tokens(part)
        if cost <= left:
            kept.append(part)
            left -= cost
        elif left >= MIN_USEFUL_TOKENS:
            kept.append(trim(part, left))
            break
    return head + "\n\n".join(kept) + tail if kept else ""
