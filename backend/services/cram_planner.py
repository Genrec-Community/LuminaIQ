"""
Exam Tonight planner — turns a book and a time budget into the plan that buys
the most exam marks per minute, in an order where each topic makes the next
easier.

Pure functions (no I/O) so the algorithm is easy to test.

Inputs per topic (from services.topic_ordering via the learning path):
  foundation  0..1  weighted, depth-damped share of topics that build on it
  coverage    0..1  how much of the book's text is about it (exam-weight proxy)
  mastery     0..1  what the student already knows (quiz accuracy / completed)
  prerequisites     topics it builds on

1. Value  v(t) = W_COVERAGE·coverage + W_FOUNDATION·foundation + W_BASE
   ("how many marks and how much understanding does this unlock?")
2. Cost   c(t) = minutes to learn it now: bigger topics take longer, mastered
   topics only need a quick review.
3. Selection = precedence-constrained knapsack, solved greedily by closure
   density: a topic can only be chosen together with its not-yet-chosen
   prerequisites (its "closure"); repeatedly add the closure with the best
   value-per-minute that still fits. Prerequisites are never skipped for a
   topic that depends on them, so the plan stays understandable.
4. Order = the learning path order (weighted topological sort), so every
   topic arrives after the ones it builds on.
5. Leftover time buys a 1-minute "skim" of the next most valuable topics; a
   fixed slice is reserved for a final rapid revision; breaks are inserted
   every BREAK_EVERY minutes of study.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

W_COVERAGE = 0.5
W_FOUNDATION = 0.35
W_BASE = 0.15

MIN_LEARN_MIN = 3.0       # smallest topic
EXTRA_LEARN_MIN = 6.0     # added for the biggest topic (coverage = 1)
REVIEW_MIN = 1.5          # already-mastered topic: quick refresh
SKIM_MIN = 1.0
REVISION_SHARE = 0.10     # final rapid revision slice
MIN_REVISION = 5.0
BREAK_EVERY = 50.0
BREAK_MIN = 5.0


def topic_cost(coverage: float, mastery: float) -> float:
    if mastery >= 0.8:
        return REVIEW_MIN
    learn = MIN_LEARN_MIN + EXTRA_LEARN_MIN * max(0.0, min(1.0, coverage))
    # partial knowledge shortens the session
    return round(learn * (1.0 - 0.5 * max(0.0, min(1.0, mastery))), 1)


def topic_value(coverage: float, foundation: float) -> float:
    return W_COVERAGE * coverage + W_FOUNDATION * foundation + W_BASE


def _reason(item: Dict[str, Any], unlocks: int) -> str:
    bits = []
    if unlocks >= 2:
        bits.append(f"unlocks {unlocks} other topics")
    elif unlocks == 1:
        bits.append("needed for another topic")
    if item.get("coverage", 0) >= 0.6:
        bits.append("a big part of the book")
    elif item.get("coverage", 0) >= 0.3:
        bits.append("well covered in the book")
    if item.get("mastery", 0) >= 0.8:
        bits.append("you know it — quick refresh")
    if not bits:
        bits.append("rounds out the chapter")
    return ", ".join(bits).capitalize()


def plan_session(
    path: List[Dict[str, Any]],
    budget_minutes: float,
    coverage: Optional[Dict[str, float]] = None,
    mastery: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Args:
        path: learning-path items in learning order: {topic, prerequisites,
              foundation, unlocks?, chapter?, level?}
        budget_minutes: total time the student has (study + breaks + revision)
        coverage / mastery: topic -> 0..1
    """
    coverage = coverage or {}
    mastery = mastery or {}
    budget = max(10.0, float(budget_minutes))

    # Reserve revision and estimate break overhead up front
    revision = max(MIN_REVISION, round(budget * REVISION_SHARE))
    study_and_breaks = budget - revision
    study_budget = study_and_breaks * BREAK_EVERY / (BREAK_EVERY + BREAK_MIN)

    order = {it["topic"]: i for i, it in enumerate(path)}
    items: Dict[str, Dict[str, Any]] = {}
    for it in path:
        t = it["topic"]
        cov = float(coverage.get(t, 0.0))
        mas = float(mastery.get(t, 0.0))
        items[t] = {
            **it,
            "coverage": round(cov, 3),
            "mastery": round(mas, 3),
            "value": topic_value(cov, float(it.get("foundation", 0.0))),
            "cost": topic_cost(cov, mas),
            "prerequisites": [p for p in (it.get("prerequisites") or []) if p in order],
        }

    # Transitive prerequisites (path is topologically ordered, so one pass works)
    ancestors: Dict[str, set] = {}
    for it in path:
        t = it["topic"]
        acc = set()
        for p in items[t]["prerequisites"]:
            acc.add(p)
            acc |= ancestors.get(p, set())
        ancestors[t] = acc

    unlocks_count = {t: 0 for t in items}
    for t in items:
        for a in ancestors[t]:
            unlocks_count[a] += 1

    # Greedy closure-density selection (precedence-constrained knapsack)
    chosen: set = set()
    remaining = study_budget
    while True:
        best, best_density, best_closure, best_cost = None, 0.0, None, 0.0
        for t in items:
            if t in chosen:
                continue
            closure = {t} | {a for a in ancestors[t] if a not in chosen}
            cost = sum(items[x]["cost"] for x in closure)
            if cost > remaining + 1e-9:
                continue
            value = sum(items[x]["value"] for x in closure)
            density = value / cost if cost else 0.0
            # tie-break: earlier in the learning path
            if density > best_density + 1e-12 or (
                abs(density - best_density) <= 1e-12 and best is not None and order[t] < order[best]
            ):
                best, best_density, best_closure, best_cost = t, density, closure, cost
        if best is None:
            break
        chosen |= best_closure
        remaining -= best_cost

    # Skims for the most valuable leftovers, while time remains
    leftovers = sorted((t for t in items if t not in chosen), key=lambda t: -items[t]["value"])
    skims = set()
    for t in leftovers:
        if remaining >= SKIM_MIN:
            skims.add(t)
            remaining -= SKIM_MIN

    # Build the timeline in learning order with breaks
    timeline: List[Dict[str, Any]] = []
    clock, since_break = 0.0, 0.0
    for it in path:
        t = it["topic"]
        if t not in chosen and t not in skims:
            continue
        minutes = items[t]["cost"] if t in chosen else SKIM_MIN
        if since_break + minutes > BREAK_EVERY and since_break > 0:
            timeline.append({"type": "break", "minutes": BREAK_MIN, "start": round(clock, 1)})
            clock += BREAK_MIN
            since_break = 0.0
        timeline.append({
            "type": "topic",
            "topic": t,
            "tier": "learn" if t in chosen else "skim",
            "minutes": minutes,
            "start": round(clock, 1),
            "chapter": it.get("chapter"),
            "prerequisites": items[t]["prerequisites"][:3],
            "unlocks": unlocks_count[t],
            "coverage": items[t]["coverage"],
            "mastery": items[t]["mastery"],
            "reason": _reason(items[t], unlocks_count[t]),
        })
        clock += minutes
        since_break += minutes
    # Don't spend more on revision than makes sense for what was studied
    revision = min(revision, max(MIN_REVISION, round(0.25 * clock)))
    timeline.append({"type": "revision", "minutes": revision, "start": round(clock, 1)})
    clock += revision

    total_value = sum(v["value"] for v in items.values()) or 1.0
    covered_value = sum(items[t]["value"] for t in chosen)
    skipped = [t for t in (it["topic"] for it in path) if t not in chosen and t not in skims]

    return {
        "budget_minutes": round(budget, 1),
        "planned_minutes": round(clock, 1),
        "spare_minutes": round(max(0.0, budget - clock), 1),
        "timeline": timeline,
        "summary": {
            "learn": len(chosen),
            "skim": len(skims),
            "skip": len(skipped),
            "total_topics": len(items),
            # share of the book's weighted importance you'll have properly studied
            "coverage_percent": round(100 * covered_value / total_value),
        },
        "skipped": skipped,
    }


def coverage_from_text(topics: List[str], texts: List[str], window: int = 1500) -> Dict[str, float]:
    """
    How much of the book is about each topic: the number of text windows where
    most of the topic's key words appear, normalised to 0..1 (max = 1).
    """
    import re

    stop = {
        "a", "an", "and", "the", "of", "in", "on", "by", "to", "for", "with", "its", "their",
        "is", "are", "as", "at", "from", "or", "into", "between", "through", "how", "what",
        "introduction", "basics", "overview", "concept", "concepts", "types", "type",
    }
    lowered = [t.lower() for t in texts if t]
    raw: Dict[str, float] = {}
    for topic in topics:
        words = [w for w in re.findall(r"[a-z0-9]+", topic.lower()) if len(w) > 2 and w not in stop]
        if not words:
            raw[topic] = 0.0
            continue
        need = max(1, (len(words) + 1) // 2)
        hits = 0
        for text in lowered:
            for start in range(0, len(text), window):
                seg = text[start:start + window]
                if sum(1 for w in words if w in seg) >= need:
                    hits += 1
        raw[topic] = float(hits)
    top = max(raw.values(), default=0.0) or 1.0
    return {t: round(v / top, 3) for t, v in raw.items()}
