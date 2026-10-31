"""Shared pools and assets for bookstore and class books (real Postgres)."""

import asyncio
import random
import uuid

import pytest

from db.client import SupabaseClient
from services import shared_content as sc
from services.telemetry import telemetry


class AppOnPg:
    def __init__(self, pg):
        self.pg = pg

    def table(self, name):
        return self.pg.table(name)


def run(c):
    return asyncio.run(c)


def q(i):
    return {"question": f"Question number {i}?", "options": [
        {"option": "A", "text": f"right {i}"}, {"option": "B", "text": "wrong 1"},
        {"option": "C", "text": "wrong 2"}, {"option": "D", "text": "wrong 3"}],
        "correct_answer": "A", "explanation": f"Because right {i}."}


@pytest.fixture
def world(pg_client, monkeypatch):
    """A bookstore original with two student imports, a class book with a copy, and a personal upload."""
    monkeypatch.setattr(SupabaseClient, "_instance", AppOnPg(pg_client))
    t = pg_client.table
    owner, s1, s2 = (str(uuid.uuid4()) for _ in range(3))

    def project(user):
        return t("projects").insert({"user_id": user, "name": "p"}).execute().data[0]["id"]

    def doc(pid, name="b.pdf"):
        return t("documents").insert({"project_id": pid, "filename": name, "upload_status": "completed"}
                                     ).execute().data[0]["id"]

    p_owner, p1, p2 = project(owner), project(s1), project(s2)
    original = doc(p_owner)
    book = t("books").insert({"user_id": owner, "document_id": original, "title": "Bio"}).execute().data[0]["id"]
    copy1, copy2 = doc(p1), doc(p2)
    for user, pid, d in [(s1, p1, copy1), (s2, p2, copy2)]:
        t("book_imports").insert({"book_id": book, "user_id": user, "project_id": pid, "document_id": d}).execute()
    personal = doc(p2, "mine.pdf")
    return {"s1": s1, "s2": s2, "p1": p1, "p2": p2, "original": original, "copy1": copy1, "copy2": copy2,
            "personal": personal, "pg": pg_client}


def test_scope_resolves_copies_to_the_original(world):
    s1 = run(sc.scope_for(world["p1"]))
    assert s1.roots == [world["original"]] and s1.by_doc == {world["copy1"]: world["original"]}
    assert s1.doc_for_root(world["original"]) == world["copy1"]
    # a project mixing a shared book with a personal upload is personal
    assert run(sc.scope_for(world["p2"])) is None
    assert run(sc.scope_for(world["p2"], [world["copy2"]])).roots == [world["original"]]
    assert run(sc.scope_for(world["p2"], [world["personal"]])) is None


def test_class_book_copies_share_a_root(world):
    t = world["pg"].table
    inst = t("institutions").insert({"name": "School", "owner_user_id": world["s1"], "teacher_code": uuid.uuid4().hex[:8]}).execute().data[0]["id"]
    cls = t("institution_classes").insert({"institution_id": inst, "name": "8A", "invite_code": uuid.uuid4().hex[:8]}).execute().data[0]["id"]
    teacher_doc = t("documents").insert({"project_id": world["p1"], "filename": "t.pdf"}).execute().data[0]["id"]
    cb = t("class_books").insert({"class_id": cls, "source_document_id": teacher_doc}).execute().data[0]["id"]
    pid = t("projects").insert({"user_id": world["s2"], "name": "class"}).execute().data[0]["id"]
    copy = t("documents").insert({"project_id": pid, "filename": "t.pdf", "upload_status": "completed"}
                                 ).execute().data[0]["id"]
    t("class_book_copies").insert({"class_book_id": cb, "user_id": world["s2"], "document_id": copy}).execute()
    assert run(sc.scope_for(pid)).roots == [teacher_doc]


def test_second_student_gets_the_pool_without_generating(world):
    calls = []

    async def make(n):
        start = len(calls) * 100
        calls.append(n)
        return [q(start + i) for i in range(n)]

    scope1 = run(sc.scope_for(world["p1"]))
    first, gen1 = run(sc.draw(world["s1"], scope1, "quiz", "Cells", "school", 5, make, variant="medium"))
    assert gen1 == 5 and len(first) == 5 and calls == [5]

    telemetry._buffer.clear()
    scope2 = run(sc.scope_for(world["p2"], [world["copy2"]]))
    second, gen2 = run(sc.draw(world["s2"], scope2, "quiz", "cells", "school", 5, make, variant="medium"))
    assert gen2 == 0 and calls == [5]          # nothing generated for the second student
    assert {x["question"] for x in second} == {x["question"] for x in first}
    assert telemetry._buffer[-1]["cache_hit"] is True
    # answers stay correct after shuffling
    for item in second:
        right = next(o["text"] for o in item["options"] if o["option"] == item["correct_answer"])
        assert right.startswith("right")


def test_pool_grows_only_when_a_student_runs_out(world):
    made = []

    async def make(n):
        made.append(n)
        base = sum(made) * 10
        return [q(base + i) for i in range(n)]

    scope = run(sc.scope_for(world["p1"]))
    a, _ = run(sc.draw(world["s1"], scope, "quiz", "Cells", "school", 5, make))
    b, gen = run(sc.draw(world["s1"], scope, "quiz", "Cells", "school", 5, make))
    assert gen == 5 and not ({x["question"] for x in a} & {x["question"] for x in b})   # no repeats
    # another level or difficulty is a different pool
    _, gen = run(sc.draw(world["s1"], scope, "quiz", "Cells", "ugpg", 5, make))
    assert gen == 5


def test_personal_books_always_generate(world):
    async def make(n):
        return [q(i) for i in range(n)]
    items, gen = run(sc.draw(world["s2"], None, "quiz", "Cells", "school", 3, make))
    assert gen == 3 and len(items) == 3


def test_flashcards_pool(world):
    async def make(n):
        return [{"front": f"Term {i}", "back": "x"} for i in range(n)]
    scope = run(sc.scope_for(world["p1"]))
    run(sc.draw(world["s1"], scope, "flashcards", "Cells", "school", 5, make))
    cards, gen = run(sc.draw(world["s2"], run(sc.scope_for(world["p2"], [world["copy2"]])),
                             "flashcards", "Cells", "school", 5, make))
    assert gen == 0 and len(cards) == 5


def test_shared_asset_is_generated_once(world):
    made = []

    async def make():
        made.append(1)
        return "# Notes on cells"

    scope = run(sc.scope_for(world["p1"]))
    a, hit_a = run(sc.asset(scope, "notes", ["Summary", "Cells", "school"], make))
    b, hit_b = run(sc.asset(run(sc.scope_for(world["p2"], [world["copy2"]])), "notes",
                            ["Summary", "cells", "school"], make))
    assert a == b == "# Notes on cells" and (hit_a, hit_b) == (False, True) and made == [1]
    c, hit_c = run(sc.asset(None, "notes", ["Summary", "Cells", "school"], make))
    assert hit_c is False and made == [1, 1]


def test_shuffle_keeps_the_right_answer():
    rng = random.Random(3)
    for _ in range(20):
        out = sc.shuffle_options(q(1), rng)
        right = next(o["text"] for o in out["options"] if o["option"] == out["correct_answer"])
        assert right == "right 1" and [o["option"] for o in out["options"]] == ["A", "B", "C", "D"]
