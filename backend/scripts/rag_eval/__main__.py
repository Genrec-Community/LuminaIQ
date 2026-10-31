"""
Measure RAG quality on a real book (AGENTS.md Phase 3 §6). Uses the app's own settings and database.

    # 1. Build a question set from a processed book (the small model writes one question per passage)
    uv run python -m scripts.rag_eval make --project <project_id> --n 40 --out eval.json
    # 2. Score retrieval (and, with --judge, answers) and print a report
    uv run python -m scripts.rag_eval run --project <project_id> --data eval.json [--judge]

Metrics
- recall@5: the passage a question was written from is among the 5 passages retrieved
- MRR: 1 / rank of that passage (0 when missing), averaged
- grounded rate: share of in-book questions retrieval treats as covered by the book
- off-book precision: share of the built-in off-topic questions treated as NOT covered
- faithfulness / citation correctness (--judge): the small model checks each answer against
  its excerpts ("is every claim supported?", "do the [n] citations point at supporting excerpts?")
Record results in AGENTS.md §8 with the date, commit and model names.
"""
import argparse
import asyncio
import json
import random
import statistics
import sys
from datetime import date

from config.settings import settings

OFF_BOOK = [
    "Who won the FIFA World Cup in 2018?",
    "What is the capital of Australia?",
    "How do I bake a chocolate cake?",
    "What year did the first iPhone come out?",
    "Recommend a good sci-fi movie.",
]

QUESTION_PROMPT = ("Write ONE question a student could ask that is answered by this textbook passage. "
                   "Use the student's natural wording, not the passage's exact sentence. Reply with the question only.")

JUDGE_PROMPT = ("You check a tutor's answer against the excerpts it was given.\n"
                "Reply with JSON only: {\"faithful\": true|false, \"citations_ok\": true|false}.\n"
                "faithful: every factual claim is supported by the excerpts or clearly labelled as not from the book.\n"
                "citations_ok: every [n](n) citation points at an excerpt that supports the sentence it follows.")


async def _chunks(project_id: str, min_chars: int):
    from db.client import async_db, get_supabase_client
    pg = get_supabase_client().pg
    return await async_db(lambda: pg.fetch(
        "SELECT id, document_id::text, page, heading, content FROM chunks WHERE project_id = %s "
        "AND length(content) >= %s ORDER BY id", (project_id, min_chars)))


async def make(args):
    from services.llm_service import llm_service
    rows = await _chunks(args.project, args.min_chars)
    if not rows:
        sys.exit("No passages in that project. Upload and process a book first.")
    random.seed(7)
    sample = random.sample(rows, min(args.n, len(rows)))
    items = []
    for r in sample:
        q = await llm_service.chat_completion(
            [{"role": "system", "content": QUESTION_PROMPT}, {"role": "user", "content": r["content"][:3000]}],
            temperature=0.3, max_tokens=120, task="generate")
        if q and q.strip():
            items.append({"question": q.strip(), "chunk_id": r["id"], "page": r["page"], "heading": r["heading"]})
    json.dump({"project_id": args.project, "made": str(date.today()), "items": items}, open(args.out, "w"), indent=2)
    print(f"Wrote {len(items)} questions to {args.out}")


async def run(args):
    from services import retrieval
    from services.rag_service import build_messages
    from services.llm_service import llm_service
    data = json.load(open(args.data))
    ranks, grounded, faithful, cites = [], [], [], []
    for item in data["items"]:
        res = await retrieval.retrieve(args.project, item["question"], top_n=5)
        rank = next((i + 1 for i, p in enumerate(res.passages) if item["chunk_id"] in p.chunk_ids), None)
        ranks.append(rank)
        grounded.append(res.grounded)
        if args.judge:
            answer = await llm_service.chat_completion(
                build_messages(item["question"], res.passages, res.grounded, [], None), temperature=0, max_tokens=800)
            excerpts = "\n\n".join(f"[{i + 1}] {p.text[:1500]}" for i, p in enumerate(res.passages))
            verdict = await llm_service.chat_completion(
                [{"role": "system", "content": JUDGE_PROMPT},
                 {"role": "user", "content": f"EXCERPTS:\n{excerpts}\n\nQUESTION: {item['question']}\n\nANSWER:\n{answer}"}],
                temperature=0, max_tokens=60, task="generate")
            try:
                v = json.loads(verdict[verdict.find("{"): verdict.rfind("}") + 1])
                faithful.append(bool(v.get("faithful")))
                cites.append(bool(v.get("citations_ok")))
            except Exception:
                pass
    off = [not (await retrieval.retrieve(args.project, q, top_n=5)).grounded for q in OFF_BOOK]

    n = len(ranks) or 1
    pct = lambda xs: f"{100 * sum(xs) / len(xs):.0f}%" if xs else "n/a"
    report = {
        "questions": len(ranks),
        "recall@5": pct([r is not None for r in ranks]),
        "MRR": round(sum(1 / r for r in ranks if r) / n, 3),
        "grounded rate (in-book)": pct(grounded),
        "off-book precision": pct(off),
        "faithfulness": pct(faithful) if args.judge else "not judged",
        "citation correctness": pct(cites) if args.judge else "not judged",
        "models": f"small={settings.SMALL_LLM_MODEL or settings.LLM_MODEL} embed={settings.EMBEDDING_MODEL} "
                  f"rerank={'on' if settings.RERANK_API_KEY else 'off'}",
    }
    print("| Metric | Value |\n| --- | --- |")
    for k, v in report.items():
        print(f"| {k} | {v} |")


def main():
    ap = argparse.ArgumentParser(prog="rag_eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--project", required=True)
    m.add_argument("--n", type=int, default=40)
    m.add_argument("--out", default="eval.json")
    m.add_argument("--min-chars", type=int, default=200, help="skip passages shorter than this")
    r = sub.add_parser("run")
    r.add_argument("--project", required=True)
    r.add_argument("--data", required=True)
    r.add_argument("--judge", action="store_true")
    args = ap.parse_args()
    asyncio.run(make(args) if args.cmd == "make" else run(args))


if __name__ == "__main__":
    main()
