# Quality check of every AI feature, as a test student (run inside the api container by the
# "script" ops task). A throwaway test account gets copies of shared-library books (passages
# copied, nothing re-indexed); answers are written to /app/ops_out/ and the account is removed.
import asyncio, base64, io, json, os, re, sys, time, uuid
from collections import Counter

import httpx

OUT = "/app/ops_out"
LOG = open(f"{OUT}/quality.md", "w")
ONLY = set(filter(None, os.environ.get("QT_ONLY", "").split(",")))


def w(s=""):
    LOG.write(s + "\n"); LOG.flush()


from db.client import get_supabase_client
from api.deps import get_current_user
from services.usage_service import current_plan

pg = get_supabase_client().pg
USER = str(uuid.uuid4())
STATE = {"plan": "free"}


async def fake_user():
    current_plan.set(STATE["plan"])
    return {"id": USER, "email": "quality-test@example.invalid", "managed": False}


def pick_books():
    rows = pg.fetch("""
        SELECT b.title, b.document_id::text AS doc, count(c.id) AS n
        FROM books b JOIN chunks c ON c.document_id = b.document_id
        WHERE b.is_public GROUP BY 1, 2 HAVING count(c.id) > 30 ORDER BY count(c.id) DESC LIMIT 60""")
    w("## Shared-library books with passages\n")
    for r in rows:
        w(f"- {r['title']} ({r['n']} passages)")
    want = [("maths", r"math|algebra|geometry|calculus|trigon|arithmetic"),
            ("science", r"science|physics|chemis|biolog|electric|motion|force"),
            ("other", r"history|geograph|english|economic|civics|social|computer")]
    picked = []
    for label, rx in want:
        for r in rows:
            if re.search(rx, r["title"], re.I) and r["doc"] not in [p[1] for p in picked]:
                picked.append((label, r["doc"], r["title"])); break
    for r in rows:      # fill up to 3 with whatever is there
        if len(picked) >= 3:
            break
        if r["doc"] not in [p[1] for p in picked]:
            picked.append(("book", r["doc"], r["title"]))
    return picked


def topics_for(doc, k=3):
    heads = pg.fetch("SELECT heading FROM chunks WHERE document_id = %s AND heading IS NOT NULL AND heading <> ''",
                     (doc,))
    c = Counter()
    for h in heads:
        last = h["heading"].split("›")[-1].strip()
        if 3 < len(last) < 60 and not re.match(r"^(exercise|contents|index|chapter \d+$|page)", last, re.I):
            c[last] += 1
    tops = [t for t, _ in c.most_common(40)]
    return tops[::max(1, len(tops) // k)][:k] if tops else []


def sample_text(doc):
    r = pg.fetch("SELECT content FROM chunks WHERE document_id = %s ORDER BY chunk_index OFFSET 40 LIMIT 1", (doc,))
    return (r[0]["content"] if r else "")[:500]


def make_project(title, doc):
    pid = pg.table("projects").insert({"user_id": USER, "name": f"QT {title[:40]}"}).execute().data[0]["id"]
    did = pg.table("documents").insert({"project_id": pid, "filename": title[:200] + ".pdf",
                                        "upload_status": "completed"}).execute().data[0]["id"]
    pg.fetch("""INSERT INTO chunks (project_id, document_id, chunk_index, page, heading, content, content_hash,
                                    embedding, metadata)
                SELECT %s, %s, chunk_index, page, heading, content, content_hash, embedding, metadata
                FROM chunks WHERE document_id = %s""", (pid, did, doc))
    return pid, did


def photo_data_url():
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (900, 420), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.load_default(size=30)
    except TypeError:
        f = ImageFont.load_default()
    for i, t in enumerate(["Exercise 4.2", "Q3. A train travels 240 km in 4 hours.",
                           "(a) Find its average speed in km/h.", "(b) How long will it take to cover",
                           "     420 km at the same speed?"]):
        d.text((40, 40 + i * 65), t, fill="black", font=f)
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def calls_since(t0):
    rows = pg.fetch("""SELECT model, count(*) n, sum(input_tokens) i, sum(output_tokens) o,
                              round(avg(latency_ms)) ms, bool_and(ok) ok
                       FROM ai_calls WHERE created_at >= to_timestamp(%s) AND kind = 'llm' AND user_id = %s GROUP BY 1""", (t0, USER))
    return "; ".join(f"{r['model']} x{r['n']} in={r['i']} out={r['o']} {r['ms']}ms ok={r['ok']}" for r in rows)


async def run():
    from main import app
    app.dependency_overrides[get_current_user] = fake_user
    tr = httpx.ASGITransport(app=app)
    c = httpx.AsyncClient(transport=tr, base_url="http://t/api/v1", timeout=300)

    async def call(name, method, url, **kw):
        if ONLY and name.split(":")[0] not in ONLY:
            return None
        from services.telemetry import telemetry
        try:
            await telemetry.flush()
        except Exception:
            pass
        t0 = time.time()
        r = await c.request(method, url, **kw)
        dt = time.time() - t0
        await asyncio.sleep(1.5)
        try:
            await telemetry.flush()
        except Exception:
            pass
        w(f"\n### {name}  ({r.status_code}, {dt:.1f}s)")
        w(f"_models: {calls_since(t0 - 1)}_\n")
        try:
            body = r.json()
        except Exception:
            body = r.text
        return body

    async def level(lv):
        await c.put("/user-data/settings", json={"settings": {"studyLevel": lv, "onboarded": True}})

    books = pick_books()
    w("\n## Picked\n" + "\n".join(f"- {l}: {t}" for l, _, t in books))
    made = []
    try:
        for label, doc, title in books:
            pid, did = make_project(title, doc)
            made.append(pid)
            tops = topics_for(doc) or ["the main idea of this chapter"]
            w(f"\n\n# {label.upper()}: {title}\nTopics: {tops}\nSample passage: {sample_text(doc)[:300]!r}")
            t = tops[0]
            STATE["plan"] = "free"
            await level("school")
            # Chat: a first question, a follow-up, maths formatting, and one the book won't cover
            hist = []
            for q in [f"What is {t}? Explain simply.", "Can you explain that again with an everyday example?",
                      "Solve 2x + 7 = 19 and show each step."
                      if label == "maths" else f"Give me 3 important exam points about {t}.",
                      "Who won the 2022 FIFA World Cup?"]:
                b = await call("chat", "POST", "/chat/message", json={"project_id": pid, "message": q,
                                                                   "session_history": hist})
                if b is None:
                    break
                ans = b.get("answer") if isinstance(b, dict) else b
                w(f"**Q (Class 8):** {q}\n\n{ans}\n\n_sources: {[(s.get('page')) for s in (b.get('sources') or [])] if isinstance(b, dict) else ''}_")
                hist += [{"role": "user", "content": q}, {"role": "assistant", "content": str(ans)[:1500]}]
            b = await call("quiz", "POST", "/mcq/generate", json={"project_id": pid, "topic": t, "num_questions": 4,
                                                               "difficulty": "medium"})
            if b is not None:
                w("```json\n" + json.dumps(b.get("questions", b) if isinstance(b, dict) else b, indent=1,
                                           ensure_ascii=False)[:5000] + "\n```")
            b = await call("flashcards", "POST", f"/flashcards/{pid}/generate", json={"topic": t, "num_cards": 5})
            if b is not None:
                w("```json\n" + json.dumps(b, indent=1, ensure_ascii=False)[:3500] + "\n```")
            b = await call("notes", "POST", "/notes/generate", json={"project_id": pid, "note_type": "Summary",
                                                                  "topic": t})
            if b is not None:
                w(str(b.get("content") if isinstance(b, dict) else b)[:5000])
            b = await call("mindmap", "POST", f"/mindmaps/{pid}/generate", json={"title": t, "topic": t})
            if b is not None:
                w("```json\n" + json.dumps(b, ensure_ascii=False)[:3000] + "\n```")
            # Paid student in Class 11-12: Deep answer and Visual Lab
            STATE["plan"] = "pro"
            await level("higher_secondary")
            t2 = tops[1] if len(tops) > 1 else t
            b = await call("deep", "POST", "/chat/message", json={"project_id": pid, "deep": True,
                                                               "message": f"Explain {t2} in depth, with the reasoning behind it and a worked example."})
            if b is not None:
                w(str(b.get("answer") if isinstance(b, dict) else b)[:6000])
            b = await call("lab", "POST", "/learning/visualize", json={"project_id": pid, "topic": t2})
            if b is not None:
                html = b.get("html") if isinstance(b, dict) else None
                if html:
                    name = f"lab_{label}.html"
                    open(f"{OUT}/{name}", "w").write(html)
                    w(f"Visual Lab page saved as {name} ({len(html)} bytes)")
                else:
                    w(f"Visual Lab: {str(b)[:800]}")
            STATE["plan"] = "free"
            await level("school")
        # Photo question (free and paid)
        if made:
            for plan in ("free", "pro"):
                STATE["plan"] = plan
                b = await call(f"photo:{plan}", "POST", "/chat/message", json={
                    "project_id": made[0], "message": "Please help me with this question", "image": photo_data_url()})
                if b is not None:
                    w(str(b.get("answer") if isinstance(b, dict) else b)[:3000])
    finally:
        for pid in made:
            pg.fetch("DELETE FROM projects WHERE id = %s", (pid,))
        for tbl in ("user_settings", "usage_counters", "app_users", "user_active_days", "xp_events"):
            try:
                pg.fetch(f"DELETE FROM {tbl} WHERE user_id = %s", (USER,))
            except Exception:
                pass
        w("\n\n(test account removed)")
        await c.aclose()


asyncio.run(run())
print(open(f"{OUT}/quality.md").read()[-3000:])
