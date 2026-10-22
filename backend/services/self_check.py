"""
Startup self-check: one tiny call to each external dependency, logged as
"[SelfCheck] <name> OK|FAIL ...". Runs in the background after boot so it never
delays startup; read the results in the service logs after a deploy or a
settings change. Disable with SELF_CHECK_ON_STARTUP=false.
"""
import asyncio
import time

from config.settings import settings
from utils.logger import logger

_PROMPT = [{"role": "user", "content": "Reply with the single word: ready"}]


async def _timed(name: str, coro, timeout: float = 60.0):
    start = time.monotonic()
    try:
        detail = await asyncio.wait_for(coro, timeout=timeout)
        logger.info(f"[SelfCheck] {name} OK ({time.monotonic() - start:.1f}s){' | ' + detail if detail else ''}")
        return True
    except Exception as e:
        msg = str(e).replace("\n", " ")[:400]
        logger.error(f"[SelfCheck] {name} FAIL ({time.monotonic() - start:.1f}s) | {type(e).__name__}: {msg}")
        return False


async def _llm(light: bool = False, deep: bool = False) -> str:
    from services.llm_service import llm_service

    answer = await llm_service.chat_completion(_PROMPT, temperature=0, max_tokens=2000, light=light, deep=deep)
    if not answer.strip():
        raise RuntimeError("empty answer")
    return f"answer={answer.strip()[:40]!r}"


async def _llm_stream() -> str:
    # The chat endpoint streams with stream_usage on; exercise that exact path
    from services.llm_service import _build_client, _convert_messages

    client = _build_client(temperature=0, max_tokens=2000)
    pieces = []
    async for chunk in client.astream(_convert_messages(_PROMPT)):
        if chunk.content:
            pieces.append(chunk.content)
    text = "".join(pieces).strip()
    if not text:
        raise RuntimeError("stream produced no text")
    return f"chunks={len(pieces)} answer={text[:40]!r}"


async def _embedding() -> str:
    from services.embedding_service import embedding_service

    vec = await embedding_service.generate_embedding("photosynthesis converts light into chemical energy")
    if len(vec) != settings.EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"model returned {len(vec)} dimensions but EMBEDDING_DIMENSION={settings.EMBEDDING_DIMENSION}"
        )
    return f"model={settings.EMBEDDING_MODEL} dim={len(vec)}"


async def _qdrant() -> str:
    from services.qdrant_service import qdrant_service

    client = qdrant_service.async_client
    cols = (await client.get_collections()).collections
    detail = f"collections={len(cols)}"
    if cols:
        # Existing books must have been embedded at the size we embed queries at
        info = await client.get_collection(cols[0].name)
        params = info.config.params.vectors
        size = getattr(params, "size", None)
        if size is None and isinstance(params, dict) and params:
            size = next(iter(params.values())).size
        if size and size != settings.EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"collection {cols[0].name} stores {size}-dim vectors but EMBEDDING_DIMENSION="
                f"{settings.EMBEDDING_DIMENSION}: searches on existing books will fail"
            )
        detail += f" sample_dim={size}"
    return detail


async def _storage() -> str:
    from db.client import get_supabase_client, async_db

    client = get_supabase_client()
    buckets = await async_db(lambda: client.storage.list_buckets())
    names = {getattr(b, "name", None) or (b.get("name") if isinstance(b, dict) else None) for b in buckets}
    missing = [b for b in ("documents",) if b not in names]
    if missing:
        raise RuntimeError(f"missing storage buckets: {missing}")
    return f"buckets={sorted(n for n in names if n)}"


async def _indra() -> str:
    # Render a line of text, OCR it on the Indra service, check the words come back
    import fitz
    from utils.indra_ocr_client import get_indra_ocr

    client = get_indra_ocr()
    doc = fitz.open()
    page = doc.new_page(width=600, height=200)
    page.insert_text((40, 110), "Integrity builds trust", fontsize=32)
    image = page.get_pixmap(dpi=150, colorspace=fitz.csGRAY).tobytes("jpeg")
    loop = asyncio.get_running_loop()
    if not await loop.run_in_executor(None, client.wait_ready, 180):
        raise RuntimeError("service not ready")
    text = (await loop.run_in_executor(None, client._ocr_batch, [image]))[0]
    if "integrity" not in text.lower():
        raise RuntimeError(f"unexpected text: {text[:80]!r}")
    return f"read {text.strip()[:40]!r}"


async def _signed_uploads() -> str:
    """Browser upload paths with a signed token: resumable (TUS) and single PUT."""
    import base64
    import httpx
    from api.v1.endpoints.documents import UPLOADS_BUCKET, create_signed_upload

    base = settings.SUPABASE_URL.rstrip("/")
    anon = settings.SUPABASE_KEY
    data = b"self-check upload"
    results = {}
    async with httpx.AsyncClient(timeout=30) as client:
        # Resumable with a signed token
        path = "selfcheck/tus-probe.txt"
        token = await create_signed_upload(path)
        b64 = lambda v: base64.b64encode(v.encode()).decode()
        meta = f"bucketName {b64(UPLOADS_BUCKET)},objectName {b64(path)},contentType {b64('text/plain')}"
        r = await client.post(f"{base}/storage/v1/upload/resumable/sign", headers={
            "Tus-Resumable": "1.0.0", "Upload-Length": str(len(data)), "Upload-Metadata": meta,
            "x-signature": token, "x-upsert": "true", "apikey": anon,
        })
        loc = r.headers.get("location")
        if r.status_code == 201 and loc:
            r2 = await client.patch(loc, content=data, headers={
                "Tus-Resumable": "1.0.0", "Upload-Offset": "0", "Content-Type": "application/offset+octet-stream",
                "x-signature": token, "apikey": anon,
            })
            results["tus"] = r2.status_code
        else:
            results["tus"] = f"{r.status_code} {r.text[:120]}"
        # Single PUT with a signed token
        path2 = "selfcheck/put-probe.txt"
        token2 = await create_signed_upload(path2)
        r3 = await client.put(f"{base}/storage/v1/object/upload/sign/{UPLOADS_BUCKET}/{path2}?token={token2}",
                              content=data, headers={"Content-Type": "text/plain", "x-upsert": "true", "apikey": anon})
        results["put"] = r3.status_code
        await client.request("DELETE", f"{base}/storage/v1/object/{UPLOADS_BUCKET}", json={"prefixes": [path, path2]},
                             headers={"Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}", "apikey": settings.SUPABASE_SERVICE_KEY})
    ok = results.get("tus") == 204 or results.get("put") in (200, 201)
    if not ok:
        raise RuntimeError(f"browser uploads would fail: {results}")
    return f"resumable={results['tus']} put={results['put']}"


async def run_self_check():
    await asyncio.sleep(2)  # let the server finish binding first
    checks = [
        ("llm.main", _llm()),
        ("llm.stream", _llm_stream()),
        ("embedding", _embedding()),
        ("qdrant", _qdrant()),
        ("storage", _storage()),
        ("storage.signed_upload", _signed_uploads()),
    ]
    if settings.INDRA_OCR_URL:
        checks.append(("ocr.indra", _indra()))
    if settings.LLM_LIGHT_MODEL and settings.LLM_LIGHT_MODEL != settings.LLM_MODEL:
        checks.append((f"llm.light ({settings.LLM_LIGHT_MODEL})", _llm(light=True)))
    if settings.LLM_DEEP_MODEL or settings.LLM_DEEP_BASE_URL:
        checks.append((f"llm.deep ({settings.LLM_DEEP_MODEL or settings.LLM_MODEL})", _llm(deep=True)))
    results = await asyncio.gather(*(_timed(n, c, 240 if n == "ocr.indra" else 60) for n, c in checks))
    failed = [n for (n, _), ok in zip(checks, results) if not ok]
    if failed:
        logger.error(f"[SelfCheck] done: {len(failed)} failed: {', '.join(failed)}")
    else:
        logger.info(f"[SelfCheck] done: all {len(checks)} checks passed")
