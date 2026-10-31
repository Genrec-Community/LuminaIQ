"""
Token budgets for what goes into a prompt (AGENTS.md Phase 4; Phase 5 adds memory).

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
