# Quality check of every AI feature, as a test student (run inside the api container by the
# "script" ops task). A throwaway test account gets copies of shared-library books (passages
# copied, nothing re-indexed); answers are written to /app/ops_out/ and the account is removed.
import asyncio, base64, io, json, os, re, sys, time, uuid
from collections import Counter

import httpx

OUT = "/app/ops_out"
LOG = open(f"{OUT}/quality.md", "w")
ONLY = set(filter(None, os.environ.get("QT_ONLY", "quiz").split(",")))


def w(s=""):
    LOG.write(s + "\n"); LOG.flush()


from db.client import get_supabase_client
from api.deps import get_current_user
from services.usage_service import current_plan

pg = get_supabase_client().pg
USER = "00000000-0000-4000-8000-00000000a1a1"     # fixed test account, never a real user
# Leftovers from a run that was cut short
pg.fetch("DELETE FROM projects WHERE (user_id = %s OR (name IN ('QT maths', 'QT science')"
         " AND created_at > '2026-11-23 05:40+00' AND created_at < '2026-11-23 06:00+00'))", (USER,))
STATE = {"plan": "free"}


from services.usage_service import usage as _usage


async def _plan_row(user_id):
    # The test account is on whichever plan the step needs, with no limits
    return {"plan": STATE["plan"], "unlimited": True}

_usage.plan_row = _plan_row


async def fake_user():
    current_plan.set(STATE["plan"])
    return {"id": USER, "email": "quality-test@example.invalid", "managed": False}


BOOKS = json.loads('{"maths": {"title": "Class 8 Maths - Linear Equations", "text": "# Chapter 2 Linear Equations in One Variable\\n\\n## 2.1 Introduction\\nIn earlier classes you met algebraic expressions such as $x + 3$, $2y - 5$ and $3p + 7$. An equation is a statement that two expressions are equal, for example $2x + 3 = 11$. The expression on the left of the equals sign is called the left hand side (LHS) and the one on the right is the right hand side (RHS). An equation in which the highest power of the variable is 1 is called a linear equation. In this chapter we study linear equations in one variable, such as $5x - 4 = 21$ or $\\frac{y}{3} + 2 = 7$.\\n\\n## 2.2 Solving Equations with the Variable on One Side\\nThe value of the variable that makes LHS equal to RHS is called the solution of the equation. We can add, subtract, multiply or divide both sides of an equation by the same number (not zero for division) and the equation stays balanced, like a weighing balance with equal weights on both pans.\\n\\nExample 1: Solve $2x - 3 = 7$.\\nAdd 3 to both sides: $2x = 10$. Divide both sides by 2: $x = 5$.\\nCheck: LHS $= 2(5) - 3 = 7 =$ RHS.\\n\\nTransposing: moving a term from one side to the other changes its sign. In $x + 5 = 12$, transposing 5 gives $x = 12 - 5 = 7$.\\n\\f\\n## 2.3 Some Applications\\nExample 2: The sum of two numbers is 74. One of the numbers is 10 more than the other. What are the numbers?\\nLet the smaller number be $x$. The other number is $x + 10$. So $x + (x + 10) = 74$, which gives $2x + 10 = 74$, so $2x = 64$ and $x = 32$. The numbers are 32 and 42.\\n\\nExample 3: Sanya\'s mother is three times as old as Sanya. In 12 years the sum of their ages will be 72. Let Sanya\'s age be $x$; her mother\'s age is $3x$. Then $(x + 12) + (3x + 12) = 72$, so $4x + 24 = 72$, $4x = 48$, $x = 12$. Sanya is 12 and her mother is 36.\\n\\n## 2.4 Solving Equations with the Variable on Both Sides\\nIn $2x - 3 = x + 2$ the variable appears on both sides. Transpose $x$ to the LHS and $-3$ to the RHS: $2x - x = 2 + 3$, so $x = 5$.\\n\\nExample 4: Solve $5x + \\frac{7}{2} = \\frac{3}{2}x - 14$.\\nMultiply both sides by 2 to clear fractions: $10x + 7 = 3x - 28$. Then $7x = -35$, so $x = -5$.\\n\\f\\n## 2.5 Reducing Equations to Simpler Form\\nExample 5: Solve $\\frac{6x + 1}{3} + 1 = \\frac{x - 3}{6}$.\\nMultiply both sides by 6 (the LCM of the denominators): $2(6x + 1) + 6 = x - 3$. So $12x + 2 + 6 = x - 3$, giving $11x = -11$ and $x = -1$.\\n\\nCommon mistakes:\\n- Forgetting to multiply every term by the LCM, including whole numbers.\\n- Changing the sign of only one term inside brackets after transposing.\\n- Dividing by a variable that could be zero.\\n\\n## 2.6 Equations Reducible to the Linear Form\\nSome equations look non-linear but become linear after cross-multiplying. For $\\frac{x + 1}{2x + 3} = \\frac{3}{8}$, cross-multiplying gives $8(x + 1) = 3(2x + 3)$, so $8x + 8 = 6x + 9$, $2x = 1$, and $x = \\frac{1}{2}$.\\n\\nSummary\\n1. An equation is a statement of equality between two expressions containing a variable.\\n2. A linear equation in one variable has the variable with highest power 1.\\n3. We can transpose terms, changing their sign, to solve equations.\\n4. Equations with fractions are simplified by multiplying both sides by the LCM of the denominators.\\n", "topic": "solving linear equations with the variable on both sides", "topic2": "equations with fractions (using the LCM)", "qs": ["What is a linear equation? Explain simply.", "I don\'t get it, can you explain with an everyday example?", "Solve 3x - 5 = x + 9 and show each step.", "Who won the 2022 FIFA World Cup?"]}, "science": {"title": "Class 8 Science - Force and Pressure", "text": "# Chapter 8 Force and Pressure\\n\\n## 8.1 Force: A Push or a Pull\\nOpening a door, kicking a football and lifting a school bag all involve a push or a pull. In science, a push or a pull on an object is called a force. A force arises from the interaction between at least two objects. The SI unit of force is the newton (N).\\n\\n## 8.2 Forces Due to an Interaction\\nForces applied in the same direction add up. If two friends push a heavy box in the same direction, the net force is the sum of their forces. Forces applied in opposite directions subtract: in a tug of war, if both teams pull equally hard the rope does not move. The net force is zero when balanced.\\n\\n## 8.3 Exploring Forces\\nA force has both a size (magnitude) and a direction. If the direction or the magnitude changes, its effect also changes.\\n\\n## 8.4 A Force Can Change the State of Motion\\nA force can make a stationary object move, stop a moving object, change its speed or change its direction of motion. When a goalkeeper stops a ball, the force he applies brings the ball to rest. A cyclist pedalling harder increases the speed of the bicycle.\\n\\f\\n## 8.5 Force Can Change the Shape of an Object\\nPressing a ball of dough, squeezing a rubber ball or stretching a rubber band changes its shape. Some objects regain their shape when the force is removed (a rubber band), others do not (a lump of clay).\\n\\n## 8.6 Contact Forces\\nMuscular force is the force produced by the action of our muscles, such as when we lift a bucket. Friction is the force that opposes motion between two surfaces in contact; it is why a ball rolling on the ground slowly comes to rest. Both need contact with the object.\\n\\n## 8.7 Non-contact Forces\\nMagnetic force: a magnet attracts iron without touching it, and like poles repel. Electrostatic force: a plastic comb rubbed in dry hair attracts small bits of paper; the force exerted by a charged body is electrostatic force. Gravitational force: every object in the universe attracts every other object. The force with which the Earth pulls objects towards itself is called gravity. That is why a ball thrown up comes back down.\\n\\f\\n## 8.8 Pressure\\nThe force acting on a unit area of a surface is called pressure.\\n$$\\\\text{Pressure} = \\frac{\\\\text{Force}}{\\\\text{Area on which it acts}}$$\\nThe SI unit of pressure is the pascal (Pa), where $1\\\\ \\\\text{Pa} = 1\\\\ \\\\text{N/m}^2$. For the same force, a smaller area gives a larger pressure. This is why the cutting edge of a knife is sharp, nails have pointed tips, and porters place a round cloth on their heads to spread the load over a larger area.\\n\\nExample: A box weighing 600 N rests on a floor on a face of area $2\\\\ \\\\text{m}^2$. Pressure $= \\frac{600}{2} = 300$ Pa. If it is turned onto a face of area $0.5\\\\ \\\\text{m}^2$, pressure $= 1200$ Pa.\\n\\n## 8.9 Pressure Exerted by Liquids and Gases\\nLiquids exert pressure on the walls of their container, and the pressure increases with depth. That is why the wall of a dam is made thicker at the bottom. Water spurts farther from a hole low in a bottle than from a hole near the top. Gases also exert pressure on the walls of their container, which is why a balloon stays inflated.\\n\\n## 8.10 Atmospheric Pressure\\nThe envelope of air around the Earth is called the atmosphere, and the pressure it exerts is atmospheric pressure. A rubber sucker sticks to a smooth surface because the air pressure outside is greater than the pressure inside. We are not crushed by this pressure because the pressure inside our bodies is equal to it and cancels it.\\n\\nKeywords: force, net force, friction, gravity, magnetic force, electrostatic force, pressure, pascal, atmospheric pressure.\\n", "topic": "pressure", "topic2": "contact and non-contact forces", "qs": ["Why is a knife sharp but a school bag strap wide?", "Can you explain that again more simply?", "A box of 600 N sits on an area of 3 square metres. What pressure does it put on the floor?", "What is the capital of Australia?"]}}')


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

    from services.indexing import index_text
    made = []
    try:
        for label, bk in BOOKS.items():
            pid = pg.table("projects").insert({"user_id": USER, "name": f"QT {label}"}).execute().data[0]["id"]
            did = pg.table("documents").insert({"project_id": pid, "filename": bk["title"] + ".pdf",
                                                "upload_status": "completed"}).execute().data[0]["id"]
            made.append(pid)
            n = await index_text(pid, did, bk["title"], bk["text"])
            w(f"\n\n# {label.upper()}: {bk['title']} ({n} passages)")
            t, t2 = bk["topic"], bk["topic2"]
            STATE["plan"] = "free"
            await level("school")
            hist = []
            for q in bk["qs"]:
                b = await call("chat", "POST", "/chat/message", json={"project_id": pid, "message": q,
                                                                   "session_history": hist})
                if b is None:
                    break
                ans = b.get("answer") if isinstance(b, dict) else b
                w(f"**Q (Class 8):** {q}\n\n{ans}\n\n_pages cited: {[(s.get('page')) for s in (b.get('sources') or [])] if isinstance(b, dict) else ''}_")
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
            STATE["plan"] = "topper"
            await level("higher_secondary")
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
            for plan in ("free", "topper"):
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
