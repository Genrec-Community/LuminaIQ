# Self-check plus a real chat call and the re-index progress (run inside the api container).
import asyncio, os, psycopg
from services.self_check import run_self_check
from services.llm_service import llm_service

async def main():
    print("self-check:", await run_self_check())
    out = await llm_service.chat_completion([{"role": "user", "content": "Explain photosynthesis to a Class 6 student in two sentences."}], max_tokens=600)
    print("chat:", str(out)[:300])
asyncio.run(main())
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    print("jobs:", c.execute("SELECT kind, status, count(*) FROM jobs GROUP BY 1,2 ORDER BY 1,2").fetchall())
    print("chunks:", c.execute("SELECT count(*), count(DISTINCT document_id) FROM chunks").fetchone())
    print("recent job errors:", c.execute("SELECT left(coalesce(error,''),200) FROM jobs WHERE status='failed' ORDER BY updated_at DESC LIMIT 3").fetchall())
