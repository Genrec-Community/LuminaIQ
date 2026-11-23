# Which model builds Visual Lab pages best: time, size and whether the page passes the app's checks.
import asyncio, time
from api.v1.endpoints import study_modes as S
from services import llm_service as L

OUT = "/app/ops_out"
CTX = ("Contact forces need touch: muscular force (lifting a bucket) and friction (a rolling ball slows down). "
       "Non-contact forces act at a distance: magnetic force (a magnet pulls iron, like poles repel), "
       "electrostatic force (a comb rubbed in dry hair picks up paper), gravity (a ball thrown up comes back).")


async def main():
    cfg = L.small_config()
    client = L.openai.AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=300, max_retries=0)
    L.client_for = lambda c: client     # measure the model, not the app's 120 s timeout
    names = [m.id for m in (await client.models.list()).data]
    cands = ["moonshotai.kimi-k2.5", "deepseek.v3.2", "qwen.qwen3-235b-a22b-2507"] + \
            [n for n in names if "coder" in n][:2] + [n for n in names if "glm-4.7" in n and "flash" not in n][:1]
    print("coder/glm models:", [n for n in names if "coder" in n or "glm" in n])
    prompt = S.VISUAL_PROMPT.format(topic="contact and non-contact forces", context=CTX)
    svc = L.llm_service

    async def one(m):
        t = time.time()
        try:
            raw = await asyncio.wait_for(svc._complete(L._with_model(cfg, m), [{"role": "user", "content": prompt}],
                                                       0.4, 12000), 300)
            html = S._sanitize_html(raw)
            dt = time.time() - t
            if html:
                open(f"{OUT}/lab_{m.replace('/', '_')}.html", "w").write(html)
            return f"{m}: {dt:.0f}s, raw {len(raw)} chars, page {'OK ' + str(len(html)) if html else 'REJECTED'}"
        except Exception as e:
            return f"{m}: FAILED after {time.time() - t:.0f}s: {str(e)[:200]}"

    res = await asyncio.gather(*[one(m) for m in cands])
    open(f"{OUT}/lab.txt", "w").write("\n".join(res))
    print("\n".join(res))

asyncio.run(main())
