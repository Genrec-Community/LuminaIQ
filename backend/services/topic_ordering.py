"""
Topic ordering engine — the single source of truth for "what to learn next".

Used by the Learning Path, /mcq/topics (Power Hour, quizzes, notes...) and
suggested-topic, so every screen shows topics in the same order.

Algorithm (deterministic, O((V + E) log V)):

1. Build a prerequisite graph over the topics. Duplicate edges keep their
   highest weight; self-loops and edges to unknown topics are dropped.

2. Break cycles (LLM-generated graphs sometimes contain them). Run Kahn's
   algorithm with book position as the priority. When no topic is ready but
   some remain, release the remaining topic with the smallest weighted
   number of unmet prerequisites (ties → earlier in the book). Edges that
   point "backwards" in the resulting order are dropped, which leaves a DAG
   while discarding as little prerequisite weight as possible.

3. Score how foundational each topic is ("common topics first"):
       reach(t) = Σ over edges t→c of  w(t,c) · (1 + DAMPING · reach(c))
   i.e. the weighted, depth-damped number of topics that build on t. A topic
   many others depend on gets a high score. Computed by DP in reverse
   topological order.

4. Final order: Kahn's algorithm on the DAG with a min-heap keyed by
       FOUNDATION_WEIGHT · (1 − foundation) + BOOK_WEIGHT · book_position
   so a topic is only offered once everything it depends on has been learned,
   and among the ready ones the most widely-needed (then earliest in the
   book) comes first.

Each item also gets a `level`: the length of the longest prerequisite chain
leading to it (level 1 = no prerequisites).
"""

from __future__ import annotations

import heapq
from typing import Any, Dict, Iterable, List, Optional

DAMPING = 0.6
FOUNDATION_WEIGHT = 0.6
BOOK_WEIGHT = 0.4


def _dedupe(topics: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for t in topics:
        if isinstance(t, str):
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def order_topics(
    topics: Iterable[str],
    edges: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Order topics for learning.

    Args:
        topics: topic names in book order (earlier document/chapter first).
        edges:  dicts with from_topic, to_topic, weight and optional
                relation_type; only "prerequisite" edges affect order.

    Returns:
        [{topic, order, level, foundation, prerequisites, unlocks}] in
        learning order.
    """
    nodes = _dedupe(topics)
    index = {t: i for i, t in enumerate(nodes)}
    n = len(nodes)
    if n == 0:
        return []

    # 1. Graph with deduplicated, max-weight edges
    weight: Dict[tuple, float] = {}
    for e in edges or []:
        if (e.get("relation_type") or "prerequisite") != "prerequisite":
            continue
        u, v = e.get("from_topic"), e.get("to_topic")
        if u not in index or v not in index or u == v:
            continue
        try:
            w = float(e.get("weight", 0.5))
        except (TypeError, ValueError):
            w = 0.5
        w = min(1.0, max(0.1, w))
        key = (index[u], index[v])
        if w > weight.get(key, 0.0):
            weight[key] = w

    out_adj: List[List[int]] = [[] for _ in range(n)]
    in_adj: List[List[int]] = [[] for _ in range(n)]
    for (u, v) in weight:
        out_adj[u].append(v)
        in_adj[v].append(u)

    # 2. Cycle breaking: Kahn by book position, releasing the least-blocked
    #    node when stuck.
    unmet = [len(in_adj[v]) for v in range(n)]
    unmet_w = [sum(weight[(u, v)] for u in in_adj[v]) for v in range(n)]
    done = [False] * n
    ready = [v for v in range(n) if unmet[v] == 0]
    heapq.heapify(ready)
    stuck_heap = [(unmet_w[v], v) for v in range(n)]
    heapq.heapify(stuck_heap)
    position = [0] * n
    placed = 0
    while placed < n:
        if ready:
            v = heapq.heappop(ready)
            if done[v]:
                continue
        else:
            # Lazy-deleted heap: skip stale entries
            while True:
                w_v, v = heapq.heappop(stuck_heap)
                if not done[v] and abs(w_v - unmet_w[v]) < 1e-9:
                    break
        done[v] = True
        position[v] = placed
        placed += 1
        for c in out_adj[v]:
            if done[c]:
                continue
            unmet[c] -= 1
            unmet_w[c] -= weight[(v, c)]
            heapq.heappush(stuck_heap, (unmet_w[c], c))
            if unmet[c] == 0:
                heapq.heappush(ready, c)

    # Keep only forward edges → DAG
    dag_out: List[List[int]] = [[] for _ in range(n)]
    dag_in: List[List[int]] = [[] for _ in range(n)]
    for (u, v) in weight:
        if position[u] < position[v]:
            dag_out[u].append(v)
            dag_in[v].append(u)
    topo = sorted(range(n), key=position.__getitem__)

    # 3. Foundation score (weighted, damped downstream reach) + level
    reach = [0.0] * n
    for v in reversed(topo):
        reach[v] = sum(weight[(v, c)] * (1.0 + DAMPING * reach[c]) for c in dag_out[v])
    max_reach = max(reach) or 1.0
    foundation = [r / max_reach for r in reach]

    level = [1] * n
    for v in topo:
        for c in dag_out[v]:
            if level[v] + 1 > level[c]:
                level[c] = level[v] + 1

    # 4. Final order: weighted priority Kahn on the DAG
    denom = max(1, n - 1)
    def key(v: int):
        return (round(FOUNDATION_WEIGHT * (1.0 - foundation[v]) + BOOK_WEIGHT * (v / denom), 9), v)

    indeg = [len(dag_in[v]) for v in range(n)]
    heap = [key(v) for v in range(n) if indeg[v] == 0]
    heapq.heapify(heap)
    result: List[Dict[str, Any]] = []
    while heap:
        _, v = heapq.heappop(heap)
        result.append({
            "topic": nodes[v],
            "order": len(result) + 1,
            "level": level[v],
            "foundation": round(foundation[v], 3),
            "prerequisites": [nodes[u] for u in sorted(dag_in[v], key=lambda u: -weight[(u, v)])],
            "unlocks": [nodes[c] for c in sorted(dag_out[v], key=lambda c: -weight[(v, c)])],
        })
        for c in dag_out[v]:
            indeg[c] -= 1
            if indeg[c] == 0:
                heapq.heappush(heap, key(c))

    return result


def topics_in_book_order(documents: List[Dict[str, Any]]) -> List[str]:
    """Flatten documents' topics (documents already sorted oldest first)."""
    out: List[str] = []
    for doc in documents:
        out.extend(doc.get("topics") or [])
    return _dedupe(out)


def chapter_lookup(documents: List[Dict[str, Any]]) -> Dict[str, Dict[str, Optional[str]]]:
    """topic -> {chapter, document_id} from stored outlines (first wins)."""
    lookup: Dict[str, Dict[str, Optional[str]]] = {}
    for doc in documents:
        for ch in doc.get("topic_outline") or []:
            if not isinstance(ch, dict):
                continue
            for t in ch.get("topics") or []:
                name = t.get("name") if isinstance(t, dict) else t
                if isinstance(name, str) and name not in lookup:
                    lookup[name] = {"chapter": ch.get("title"), "document_id": doc.get("id")}
    return lookup
