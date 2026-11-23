# Self-check plus a real chat call and the re-index progress (run inside the api container).
import asyncio, os, psycopg
from services.self_check import run_self_check
from services.llm_service import llm_service

async def main():
    print("self-check:", await run_self_check())
    out = await llm_service.chat_completion([{"role": "user", "content": "Explain photosynthesis to a Class 6 student in two sentences."}], max_tokens=600)
    print("chat:", str(out)[:300])
    # Every feature's model, as a paid user would get it (free users stay on the small model)
    import time
    from services import llm_service as L
    for task in ("chat", "generate", "memory", "rewrite", "deep", "lab"):
        cfg = L.resolve_model(task, "pro")
        t = time.perf_counter()
        try:
            r = await llm_service._complete(cfg, [{"role": "user", "content": "Reply with one word: ready"}], 0.2, 300)
            print(f"model {task}: {cfg.model} ok {time.perf_counter()-t:.1f}s -> {r[:40]!r}")
        except Exception as e:
            print(f"model {task}: {cfg.model} FAILED {str(e)[:200]}")
    fb = L.fallback_for(L.resolve_model("chat", "free"))
    if fb:
        r = await llm_service._complete(fb, [{"role": "user", "content": "Reply with one word: ready"}], 0.2, 300)
        print(f"fallback: {fb.model} -> {r[:40]!r}")
    vis = L.vision_config("pro")
    print("vision model:", vis.model if vis else None)
asyncio.run(main())
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    print("jobs:", c.execute("SELECT kind, status, count(*) FROM jobs GROUP BY 1,2 ORDER BY 1,2").fetchall())
    print("chunks:", c.execute("SELECT count(*), count(DISTINCT document_id) FROM chunks").fetchone())
    print("recent job errors:", c.execute("SELECT left(coalesce(error,''),200) FROM jobs WHERE status='failed' ORDER BY updated_at DESC LIMIT 3").fetchall())
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    print("books:", c.execute("""SELECT count(*), count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM chunks k WHERE k.document_id = d.id)),
                                        count(DISTINCT d.project_id) FILTER (WHERE NOT EXISTS (SELECT 1 FROM chunks k WHERE k.document_id = d.id))
                                 FROM documents d""").fetchone())
