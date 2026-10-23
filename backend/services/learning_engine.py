"""
Learning engine — decides what a student should learn next, how well they know
each topic, and when to revisit it.

Three problems, solved together:

1. Knowledge architecture — what depends on what. The project's topic graph
   (topic_relations) with typed edges: REQUIRES (strict prerequisite),
   SUPPORTS, PART_OF, CONTRASTS_WITH, APPLIED_IN.
2. Learner model — what this student knows. Bayesian Knowledge Tracing per
   topic (guess/slip depend on the kind and difficulty of the evidence) plus a
   memory-stability estimate: knowledge fades between reviews, and each
   successful *spaced* recall makes it last longer.
3. Path planning — what to learn next for the greatest benefit per minute:

       V = 0.30·Importance + 0.25·Dependency leverage + 0.20·Transfer
           + 0.15·Knowledge gap + 0.10·Retention urgency
       P = V · ExpectedGain / Minutes

   with a hard rule: a topic is only eligible once its essential prerequisites
   are known well enough. The planner looks one step ahead (what a topic
   unlocks) and re-plans after every piece of evidence.

The weights are a starting hypothesis, not established constants; every
answer is stored as a learning event so they can be tuned against measured
learning gains later.

Everything above the "Storage" section is pure (no I/O) so it is easy to test.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ── Scoring weights (initial hypothesis) ────────────────────────────────────
W_IMPORTANCE = 0.30
W_LEVERAGE = 0.25
W_TRANSFER = 0.20
W_GAP = 0.15
W_RETENTION = 0.10

TARGET = 0.85            # mastery target for a topic
READY = 0.60             # an essential prerequisite counts as known from here
ESSENTIAL_WEIGHT = 0.6   # prerequisite edges at least this strong are hard rules

# ── Bayesian Knowledge Tracing ──────────────────────────────────────────────
P_INIT = 0.15            # prior: unfamiliar topic
P_TRANSIT = 0.12         # chance of learning from one practice opportunity

# (guess, slip) per kind of evidence
EVIDENCE = {
    "mcq": (0.25, 0.10),
    "quick_check": (0.25, 0.10),
    "feed": (0.25, 0.10),
    "flashcard": (0.15, 0.10),   # self-graded recall
    "recall": (0.05, 0.12),      # explained / reconstructed from memory
    "written": (0.05, 0.12),
}
DIFFICULTY_SHIFT = {      # (guess shift, slip shift, evidence weight)
    "easy": (+0.10, -0.03, 0.6),
    "medium": (0.0, 0.0, 1.0),
    "hard": (-0.08, +0.06, 1.4),
}

# ── Memory model ────────────────────────────────────────────────────────────
# Retention after t days: R = 0.9 ** (t / S); S = days until recall drops to 90%.
S_INITIAL = 1.0
S_MAX = 180.0
REVIEW_AT = 0.9


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ════════════════════════════════════════════════════════════════════════════
# Learner model
# ════════════════════════════════════════════════════════════════════════════

def blank_state(topic: str) -> Dict[str, Any]:
    return {
        "topic": topic, "p_known": P_INIT, "attempts": 0, "correct": 0, "evidence": 0.0,
        "stability_days": S_INITIAL, "review_days": 0, "first_seen": None, "last_seen": None,
        "last_day": None, "next_review": None,
    }


def bkt_update(p: float, correct: bool, kind: str = "mcq", difficulty: str = "medium",
               hinted: bool = False) -> Tuple[float, float]:
    """One BKT step. Returns (new P(known), evidence weight of this observation)."""
    guess, slip = EVIDENCE.get(kind, EVIDENCE["mcq"])
    g_shift, s_shift, weight = DIFFICULTY_SHIFT.get(difficulty or "medium", DIFFICULTY_SHIFT["medium"])
    guess, slip = _clamp(guess + g_shift, 0.02, 0.6), _clamp(slip + s_shift, 0.02, 0.4)
    if hinted:
        # Right with help says little about independent mastery
        guess, weight = max(guess, 0.5), weight * 0.5
    if kind in ("recall", "written"):
        weight *= 1.5
    p = _clamp(p, 0.001, 0.999)
    if correct:
        post = p * (1 - slip) / (p * (1 - slip) + (1 - p) * guess)
    else:
        post = p * slip / (p * slip + (1 - p) * (1 - guess))
    return _clamp(post + (1 - post) * P_TRANSIT, 0.001, 0.999), weight


def retention(state: Dict[str, Any], now: Optional[datetime] = None) -> float:
    """Estimated probability of still recalling the topic now (1.0 if never studied)."""
    last = _parse_ts(state.get("last_seen"))
    if not last:
        return 1.0
    days = max(0.0, ((now or _now()) - last).total_seconds() / 86400)
    s = max(0.25, float(state.get("stability_days") or S_INITIAL))
    return REVIEW_AT ** (days / s)


def effective_mastery(state: Dict[str, Any], now: Optional[datetime] = None) -> float:
    """What the student knows *now*: BKT estimate faded by forgetting."""
    return _clamp(float(state.get("p_known", P_INIT)) * retention(state, now))


def apply_event(state: Dict[str, Any], event: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Update a topic's learner state with one piece of evidence (returns a new dict)."""
    now = now or _now()
    s = dict(state)
    correct = bool(event.get("correct"))
    kind = event.get("kind") or "mcq"
    difficulty = event.get("difficulty") or "medium"
    hinted = bool(event.get("hinted"))

    # Forgetting since the last review shows up as a lower prior
    prior = effective_mastery(s, now) if s.get("last_seen") else float(s.get("p_known", P_INIT))
    p_after, weight = bkt_update(prior, correct, kind, difficulty, hinted)

    last = _parse_ts(s.get("last_seen"))
    gap_days = ((now - last).total_seconds() / 86400) if last else None
    stability = float(s.get("stability_days") or S_INITIAL)
    if correct and not hinted:
        if gap_days is None:
            stability = S_INITIAL
        elif gap_days >= 0.5:
            # Spaced success: the longer it survived, the more durable it becomes
            growth = 1.8 + (0.6 if difficulty == "hard" else 0.0) + min(1.0, gap_days / max(stability, 0.5)) * 0.8
            stability = stability * growth * (0.6 + 0.4 * p_after)
        else:
            stability = stability * 1.1     # massed practice: small gain
    elif not correct:
        stability = max(0.5, stability * 0.45)
    stability = min(S_MAX, stability)

    today = now.date().isoformat()
    s.update({
        "p_known": round(p_after, 4),
        "attempts": int(s.get("attempts") or 0) + 1,
        "correct": int(s.get("correct") or 0) + (1 if correct else 0),
        "evidence": round(float(s.get("evidence") or 0) + weight, 3),
        "stability_days": round(stability, 3),
        "review_days": int(s.get("review_days") or 0) + (0 if s.get("last_day") == today else 1),
        "first_seen": s.get("first_seen") or now.isoformat(),
        "last_seen": now.isoformat(),
        "last_day": today,
        # Review when recall is predicted to fall to 90% (sooner while still weak)
        "next_review": (now + timedelta(days=stability * (0.5 + 0.5 * p_after))).isoformat(),
    })
    s["_p_before"] = round(prior, 4)
    return s


def confidence_label(state: Dict[str, Any]) -> str:
    """How well the mastery estimate is supported by evidence."""
    ev = float(state.get("evidence") or 0)
    if not state.get("attempts"):
        return "untested"
    if ev < 1.5:
        return "uncertain"
    if ev >= 4 and int(state.get("review_days") or 0) >= 2:
        return "well supported"
    return "emerging"


def status_label(mastery: float, attempts: int) -> str:
    if not attempts:
        return "untested"
    if mastery >= TARGET:
        return "strong"
    if mastery >= READY:
        return "developing"
    return "weak"


def seed_from_legacy(topic: str, correct: int, wrong: int, completed: bool) -> Dict[str, Any]:
    """A starting state from older data (quiz tallies, topics marked done)."""
    s = blank_state(topic)
    total = correct + wrong
    if total:
        acc = correct / total
        s["p_known"] = round(_clamp(P_INIT + (0.8 - P_INIT) * acc * min(1.0, total / 6)), 4)
        s["attempts"], s["correct"], s["evidence"] = total, correct, round(min(total, 6) * 0.6, 2)
    if completed:
        s["p_known"] = max(s["p_known"], 0.7)
        s["attempts"] = max(s["attempts"], 1)
        s["evidence"] = max(s["evidence"], 1.0)
    return s


# ════════════════════════════════════════════════════════════════════════════
# Knowledge graph features
# ════════════════════════════════════════════════════════════════════════════

KIND_OF_TYPE = {"prerequisite": "REQUIRES", "related": "SUPPORTS", "subtopic": "PART_OF"}
TRANSFER_KINDS = {"SUPPORTS", "APPLIED_IN", "CONTRASTS_WITH", "PART_OF"}


def edge_kind(edge: Dict[str, Any]) -> str:
    kind = (edge.get("kind") or "").upper()
    return kind or KIND_OF_TYPE.get(edge.get("relation_type") or "related", "SUPPORTS")


def _normalize(values: Dict[str, float]) -> Dict[str, float]:
    top = max(values.values(), default=0.0) or 1.0
    return {k: v / top for k, v in values.items()}


def graph_features(path: List[Dict[str, Any]], edges: Iterable[Dict[str, Any]],
                   coverage: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
    """
    Per topic: leverage (weighted downstream reach), transfer (connections that
    make other topics easier), importance (share of the material, plus
    leverage), essential prerequisites and the contrasting topics.

    path: services.topic_ordering output (prerequisite DAG, cycle-free, with
          foundation = weighted damped downstream reach).
    """
    topics = [p["topic"] for p in path]
    known = set(topics)
    supports_out: Dict[str, float] = defaultdict(float)
    transfer: Dict[str, float] = defaultdict(float)
    contrasts: Dict[str, List[str]] = defaultdict(list)
    essential: Dict[str, List[str]] = defaultdict(list)
    prereq_weight: Dict[Tuple[str, str], float] = {}

    for e in edges or []:
        u, v = e.get("from_topic"), e.get("to_topic")
        if u not in known or v not in known or u == v:
            continue
        w = _clamp(float(e.get("weight") or 0.5), 0.1, 1.0)
        conf = e.get("confidence")
        conf = 1.0 if conf is None else _clamp(float(conf))
        kind = edge_kind(e)
        if kind == "REQUIRES":
            prereq_weight[(u, v)] = max(prereq_weight.get((u, v), 0.0), w * conf)
        elif kind == "SUPPORTS":
            supports_out[u] += w * conf
        if kind in TRANSFER_KINDS:
            transfer[u] += w * conf
            transfer[v] += 0.5 * w * conf
        if kind == "CONTRASTS_WITH":
            contrasts[u].append(v)
            contrasts[v].append(u)

    # Only keep prerequisites that survived the DAG (cycles broken by ordering)
    dag_prereqs = {p["topic"]: set(p.get("prerequisites") or []) for p in path}
    for (u, v), w in prereq_weight.items():
        if u in dag_prereqs.get(v, set()) and w >= ESSENTIAL_WEIGHT:
            essential[v].append(u)

    sup = _normalize({t: supports_out.get(t, 0.0) for t in topics})
    trans = _normalize({t: transfer.get(t, 0.0) for t in topics})
    cov = _normalize({t: float(coverage.get(t, 0.0)) for t in topics}) if coverage else {t: 0.5 for t in topics}

    out: Dict[str, Dict[str, Any]] = {}
    for p in path:
        t = p["topic"]
        leverage = _clamp(0.8 * float(p.get("foundation") or 0.0) + 0.2 * sup.get(t, 0.0))
        out[t] = {
            "leverage": round(leverage, 3),
            "transfer": round(trans.get(t, 0.0), 3),
            "coverage": round(float(coverage.get(t, 0.0)) if coverage else 0.0, 3),
            "importance": round(_clamp(0.7 * cov.get(t, 0.5) + 0.3 * leverage), 3),
            "essential": essential.get(t, []),
            "prerequisites": list(p.get("prerequisites") or []),
            "unlocks": list(p.get("unlocks") or []),
            "contrasts": sorted(set(contrasts.get(t, [])))[:3],
            "level": p.get("level", 1),
            "chapter": p.get("chapter"),
            "order": p.get("order"),
        }
    return out


# ════════════════════════════════════════════════════════════════════════════
# Path planning
# ════════════════════════════════════════════════════════════════════════════

def topic_minutes(coverage: float, mastery: float, review: bool) -> float:
    if review:
        return 2.0
    learn = 3.0 + 6.0 * _clamp(coverage)
    return round(max(1.5, learn * (1.0 - 0.5 * _clamp(mastery))), 1)


def _days_ago(ts: Any, now: datetime) -> Optional[int]:
    dt = _parse_ts(ts)
    return None if not dt else max(0, int((now - dt).total_seconds() // 86400))


def plan(features: Dict[str, Dict[str, Any]], states: Dict[str, Dict[str, Any]],
         goal_topics: Optional[List[str]] = None, horizon: int = 12,
         budget_minutes: Optional[float] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Choose the next topics, best first, with an explanation for each.

    Re-plans from scratch every call (cheap): the path is an evolving plan,
    not a checklist. Simulates each chosen topic being learned to target so
    the topics it unlocks can follow it in the same sequence.
    """
    now = now or _now()
    topics = list(features.keys())
    if not topics:
        return {"next": None, "sequence": [], "profile": [], "summary": {}, "layers": {}}

    # Goal importance: the goal topics and everything they need
    goal = set()
    if goal_topics:
        stack = [t for t in goal_topics if t in features]
        while stack:
            t = stack.pop()
            if t in goal:
                continue
            goal.add(t)
            stack.extend(features[t]["prerequisites"])

    def importance(t: str) -> float:
        base = features[t]["importance"]
        if not goal:
            return base
        return 1.0 if t in goal_topics else (0.8 if t in goal else 0.25 * base)

    mastery = {t: effective_mastery(states.get(t) or blank_state(t), now) for t in topics}
    seen = {t: bool((states.get(t) or {}).get("attempts")) for t in topics}

    def urgency(t: str) -> float:
        s = states.get(t)
        if not s or not s.get("attempts") or float(s.get("p_known", 0)) < 0.5:
            return 0.0
        r = retention(s, now)
        due = _parse_ts(s.get("next_review"))
        overdue = bool(due and due <= now)
        return _clamp((1.0 - r) * 3.0 + (0.4 if overdue else 0.0))

    def readiness(t: str, m: Dict[str, float]) -> float:
        ess = features[t]["essential"]
        if not ess:
            return 1.0
        return min(_clamp(m[p] / READY) for p in ess)

    def score(t: str, m: Dict[str, float]) -> Tuple[float, Dict[str, float], bool]:
        f = features[t]
        known = float((states.get(t) or {}).get("p_known", 0))
        # Known once, now fading: a review, not a fresh lesson
        review = seen[t] and known >= READY and urgency(t) > 0.15 and m[t] < TARGET
        gap = max(0.0, TARGET - m[t]) / TARGET
        r = urgency(t)
        v = (W_IMPORTANCE * importance(t) + W_LEVERAGE * f["leverage"] + W_TRANSFER * f["transfer"]
             + W_GAP * gap + W_RETENTION * r)
        gain = (max(0.0, known - m[t]) + 0.1) if review else max(0.0, TARGET - m[t]) * readiness(t, m)
        minutes = topic_minutes(f["coverage"], m[t], review)
        return (v * gain / minutes if minutes else 0.0), {"value": v, "gain": gain, "minutes": minutes, "gap": gap, "urgency": r}, review

    def eligible(t: str, m: Dict[str, float]) -> bool:
        return all(m[p] >= READY for p in features[t]["essential"])

    sim = dict(mastery)
    chosen: List[Dict[str, Any]] = []
    picked = set()
    spent = 0.0
    limit = max(1, horizon)
    while len(chosen) < limit:
        best, best_total, best_info = None, -1.0, None
        for t in topics:
            if t in picked or not eligible(t, sim):
                continue
            p, info, review = score(t, sim)
            if p <= 0 or (not review and sim[t] >= TARGET):
                continue
            # One-step lookahead: credit what learning t makes available next
            look = 0.0
            if not review:
                trial = dict(sim)
                trial[t] = TARGET
                for c in features[t]["unlocks"]:
                    if c not in picked and c in features and not eligible(c, sim) and eligible(c, trial):
                        look = max(look, score(c, trial)[0])
            total = p + 0.5 * look
            if total > best_total:
                best, best_total, best_info = t, total, (p, info, review)
        if best is None:
            break
        p, info, review = best_info
        if budget_minutes is not None and spent + info["minutes"] > budget_minutes and chosen:
            break
        spent += info["minutes"]
        picked.add(best)
        chosen.append(_explain(best, features, states, mastery, info, review, p, now, chosen))
        sim[best] = TARGET if not review else max(sim[best], TARGET)

    # Blocked high-value topics tell the student why the foundation comes first
    blocked = []
    for t in topics:
        if t in picked or mastery[t] >= TARGET or eligible(t, mastery):
            continue
        missing = [p for p in features[t]["essential"] if mastery[p] < READY]
        blocked.append({"topic": t, "needs": missing, "value": round(importance(t) * 0.6 + features[t]["leverage"] * 0.4, 3)})
    blocked.sort(key=lambda b: -b["value"])

    profile = []
    for t in topics:
        s = states.get(t) or blank_state(t)
        m = mastery[t]
        profile.append({
            "topic": t,
            "mastery": round(m, 3),
            "p_known": round(float(s.get("p_known", P_INIT)), 3),
            "retention": round(retention(s, now), 3),
            "status": status_label(m, int(s.get("attempts") or 0)),
            "confidence": confidence_label(s),
            "attempts": int(s.get("attempts") or 0),
            "last_seen_days": _days_ago(s.get("last_seen"), now),
            "next_review": s.get("next_review"),
            "due": bool(seen[t] and float(s.get("p_known", 0)) >= 0.5 and urgency(t) > 0.15),
            "leverage": features[t]["leverage"],
            "layer": _layer(t, features, s, m, urgency(t)),
            "chapter": features[t]["chapter"],
            "unlocks": features[t]["unlocks"][:4],
            "needs": [p for p in features[t]["essential"] if mastery[p] < READY],
        })

    counts = defaultdict(int)
    for row in profile:
        counts[row["status"]] += 1
    covered = sum(1 for row in profile if row["attempts"])
    summary = {
        "topics": len(topics),
        "strong": counts["strong"], "developing": counts["developing"],
        "weak": counts["weak"], "untested": counts["untested"],
        "due_reviews": sum(1 for row in profile if row["due"]),
        "coverage": round(covered / len(topics), 3),
        "average_mastery": round(sum(mastery.values()) / len(topics), 3),
    }

    layers: Dict[str, List[str]] = {"foundation": [], "expansion": [], "completeness": [], "retention": []}
    for row in profile:
        layers[row["layer"]].append(row["topic"])

    return {
        "next": chosen[0] if chosen else None,
        "sequence": chosen,
        "blocked": blocked[:5],
        "profile": profile,
        "summary": summary,
        "layers": layers,
        "weights": {"importance": W_IMPORTANCE, "leverage": W_LEVERAGE, "transfer": W_TRANSFER,
                    "gap": W_GAP, "retention": W_RETENTION},
    }


def _layer(t: str, features: Dict[str, Dict[str, Any]], s: Dict[str, Any], m: float, urgent: float) -> str:
    f = features[t]
    if s.get("attempts") and float(s.get("p_known", 0)) >= READY and (urgent > 0.15 or m >= TARGET):
        return "retention"
    if f["leverage"] >= 0.35 or (f["level"] == 1 and f["unlocks"]):
        return "foundation"
    if f["leverage"] < 0.1 and f["importance"] < 0.35 and not f["unlocks"]:
        return "completeness"
    return "expansion"


def _explain(t: str, features, states, mastery, info, review: bool, priority: float,
             now: datetime, chosen: List[Dict[str, Any]]) -> Dict[str, Any]:
    f = features[t]
    s = states.get(t) or blank_state(t)
    why: List[str] = []
    if review:
        ago = _days_ago(s.get("last_seen"), now)
        why.append(f"Due for review — last practised {ago} day{'s' if ago != 1 else ''} ago" if ago is not None else "Due for review")
    else:
        n = len(f["unlocks"])
        if n >= 2:
            why.append(f"Unlocks {n} other topics")
        elif n == 1:
            why.append(f"Needed for “{f['unlocks'][0]}”")
        if f["coverage"] >= 0.6:
            why.append("A big part of your material")
        elif f["coverage"] >= 0.3:
            why.append("Well covered in your material")
        if s.get("attempts"):
            why.append(f"You're at {round(mastery[t] * 100)}% — room to grow")
        known_pre = [p for p in f["prerequisites"] if mastery.get(p, 0) >= READY]
        if known_pre:
            why.append(f"Builds on “{known_pre[0]}”, which you know")
        earlier = [c["topic"] for c in chosen if c["topic"] in f["prerequisites"]]
        if earlier:
            why.append(f"Follows “{earlier[-1]}” in this plan")
        if f["contrasts"]:
            why.append(f"Compare with “{f['contrasts'][0]}” — easily confused")
    if not why:
        why.append("Rounds out the subject")
    return {
        "topic": t,
        "kind": "review" if review else "learn",
        "layer": "retention" if review else _layer(t, features, s, mastery[t], 0.0),
        "minutes": info["minutes"],
        "mastery": round(mastery[t], 3),
        "status": status_label(mastery[t], int(s.get("attempts") or 0)),
        "confidence": confidence_label(s),
        "priority": round(priority, 4),
        "value": round(info["value"], 3),
        "why": why[:3],
        "reason": why[0],
        "unlocks": f["unlocks"][:4],
        "contrasts": f["contrasts"],
        "chapter": f["chapter"],
    }


# ════════════════════════════════════════════════════════════════════════════
# Storage
# ════════════════════════════════════════════════════════════════════════════

class LearningEngine:
    """Loads graph + learner state, records evidence, returns plans."""

    def __init__(self):
        from db.client import get_supabase_client
        self.client = get_supabase_client()

    # ---------------------------------------------------------------- state

    async def load_states(self, user_id: str, project_id: str, topics: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        from db.client import async_db
        from utils.logger import logger

        states: Dict[str, Dict[str, Any]] = {}
        try:
            res = await async_db(lambda: self.client.table("topic_mastery").select("*")
                                 .eq("user_id", user_id).eq("project_id", project_id).execute())
            for row in res.data or []:
                states[row["topic"]] = row
        except Exception as e:
            logger.warning(f"[LearningEngine] mastery unavailable: {e}")

        # Topics without engine state start from older data (quiz tallies, done marks)
        missing = [t for t in (topics or []) if t not in states]
        if missing:
            legacy: Dict[str, Tuple[int, int]] = {}
            try:
                perf = await async_db(lambda: self.client.table("user_performance")
                                      .select("topic, correct_count, wrong_count")
                                      .eq("user_id", user_id).eq("project_id", project_id).execute())
                for p in perf.data or []:
                    legacy[p["topic"]] = (int(p.get("correct_count") or 0), int(p.get("wrong_count") or 0))
            except Exception:
                pass
            completed = set()
            try:
                from services.user_data_service import user_data
                completed = set(await user_data.get_learning_progress(user_id, project_id))
            except Exception:
                pass
            for t in missing:
                c, w = legacy.get(t, (0, 0))
                if c or w or t in completed:
                    states[t] = seed_from_legacy(t, c, w, t in completed)
        return states

    async def record(self, user_id: str, project_id: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply evidence in order, persist the new topic states and the events."""
        from db.client import async_db
        from utils.logger import logger

        events = [e for e in events if e.get("topic")]
        if not events:
            return {"updated": {}}
        topics = sorted({e["topic"] for e in events})
        states = await self.load_states(user_id, project_id, topics)
        now = _now()
        rows, logs = {}, []
        for e in events:
            t = e["topic"]
            before = states.get(t) or blank_state(t)
            after = apply_event(before, e, now)
            states[t] = after
            logs.append({
                "user_id": user_id, "project_id": project_id, "topic": t,
                "kind": e.get("kind") or "mcq", "correct": bool(e.get("correct")),
                "difficulty": e.get("difficulty") or "medium", "hinted": bool(e.get("hinted")),
                "source": e.get("source"), "p_known_before": after.pop("_p_before", None),
                "p_known_after": after["p_known"],
            })
            rows[t] = after

        payload = []
        for t, s in rows.items():
            payload.append({
                "user_id": user_id, "project_id": project_id, "topic": t,
                **{k: s.get(k) for k in ("p_known", "attempts", "correct", "evidence", "stability_days",
                                         "review_days", "first_seen", "last_seen", "last_day", "next_review")},
                "updated_at": now.isoformat(),
            })
        try:
            await async_db(lambda: self.client.table("topic_mastery")
                           .upsert(payload, on_conflict="user_id,project_id,topic").execute())
            await async_db(lambda: self.client.table("learning_events").insert(logs).execute())
        except Exception as e:
            logger.error(f"[LearningEngine] could not save evidence: {e}")
            raise

        return {"updated": {t: {"mastery": round(effective_mastery(s, now), 3),
                                "status": status_label(effective_mastery(s, now), s["attempts"]),
                                "confidence": confidence_label(s),
                                "next_review": s["next_review"]} for t, s in rows.items()}}

    # ---------------------------------------------------------------- graph

    async def load_edges(self, project_id: str) -> List[Dict[str, Any]]:
        from db.client import async_db
        try:
            res = await async_db(lambda: self.client.table("topic_relations")
                                 .select("from_topic, to_topic, relation_type, weight, kind, confidence")
                                 .eq("project_id", project_id).execute())
        except Exception:
            # Before the typed-relations migration
            res = await async_db(lambda: self.client.table("topic_relations")
                                 .select("from_topic, to_topic, relation_type, weight")
                                 .eq("project_id", project_id).execute())
        return res.data or []

    async def build_plan(self, user_id: str, project_id: str, goal_topics: Optional[List[str]] = None,
                         horizon: int = 12, budget_minutes: Optional[float] = None,
                         selected_documents: Optional[List[str]] = None) -> Dict[str, Any]:
        from services.knowledge_graph_service import knowledge_graph
        from services.topic_ordering import order_topics, topics_in_book_order, chapter_lookup

        documents = await knowledge_graph.load_project_documents(project_id)
        if selected_documents:
            wanted = set(selected_documents)
            documents = [d for d in documents if d["id"] in wanted] or documents
        topics = topics_in_book_order(documents)
        if not topics:
            return {"next": None, "sequence": [], "profile": [], "summary": {}, "layers": {},
                    "message": "Topics for your documents are still being extracted."}
        edges = await self.load_edges(project_id)
        path = order_topics(topics, [{**e, "relation_type": "prerequisite"} for e in edges if edge_kind(e) == "REQUIRES"])
        chapters = chapter_lookup(documents)
        for item in path:
            item["chapter"] = (chapters.get(item["topic"]) or {}).get("chapter")

        coverage: Dict[str, float] = {}
        try:
            from api.v1.endpoints.study_modes import _book_coverage
            coverage = await _book_coverage(project_id, documents, topics)
        except Exception:
            pass

        features = graph_features(path, edges, coverage)
        states = await self.load_states(user_id, project_id, topics)
        result = plan(features, states, goal_topics=goal_topics, horizon=horizon, budget_minutes=budget_minutes)
        result["graph"] = {
            "edges": len(edges),
            "typed": sum(1 for e in edges if e.get("kind")),
            "prerequisites": sum(1 for e in edges if edge_kind(e) == "REQUIRES"),
        }
        return result


_engine: Optional[LearningEngine] = None


def get_learning_engine() -> LearningEngine:
    global _engine
    if _engine is None:
        _engine = LearningEngine()
    return _engine
