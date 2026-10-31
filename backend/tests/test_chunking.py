"""Structure-aware, page-aware, maths-safe chunking."""

from services.chunking import chunk_document, split_pages

PARA = ("Plants make their own food. They use sunlight, water and carbon dioxide. "
        "This process is called photosynthesis. It happens in the leaves. ")


def test_empty_text_gives_no_chunks():
    assert chunk_document("", "Book") == []
    assert chunk_document("  \f \n ", "Book") == []


def test_pages_counted_with_blank_pages():
    pages = split_pages("page one\n\f\n\n\f\npage three")
    assert [p for p, _ in pages] == [1, 2, 3]
    chunks = chunk_document("Intro on page one.\n\f\n\n\f\nAll about leaves on page three.", "Bio", target_tokens=5)
    assert chunks[0].page == 1 and chunks[0].content == "Intro on page one."
    # The page-three chunk may repeat the previous sentence (overlap) but still belongs to page 3
    third = next(c for c in chunks if "All about leaves" in c.content)
    assert third.page == 3


def test_no_page_marks_means_no_page():
    assert chunk_document("Just text.", "Notes")[0].page is None


def test_headings_become_the_heading_path():
    text = "# Chapter 1 Life Processes\n\n## 1.2 Nutrition in Plants\n\n" + PARA
    chunk = chunk_document(text, "Science")[-1]
    assert chunk.heading == "Chapter 1 Life Processes › 1.2 Nutrition in Plants"
    assert chunk.embed_text.startswith("Science › Chapter 1 Life Processes › 1.2 Nutrition in Plants")
    assert "Plants make their own food." in chunk.content


def test_numbered_and_chapter_headings_without_markdown():
    text = "CHAPTER 3 Motion\n\n3.1 Speed and Velocity\n\nSpeed is distance over time."
    chunk = chunk_document(text, "Physics")[-1]
    assert chunk.heading == "CHAPTER 3 Motion › 3.1 Speed and Velocity"


def test_new_section_starts_new_chunk():
    text = "## A\n\n" + PARA * 3 + "\n\n## B\n\n" + PARA * 3
    chunks = chunk_document(text, "T", target_tokens=400)
    assert {c.heading for c in chunks} == {"A", "B"}
    assert all(("## B" not in c.content) for c in chunks if c.heading == "A")


def test_math_block_not_split():
    formula = "$$\n" + "\n".join(f"x_{i} = a_{i} + b_{i}" for i in range(80)) + "\n$$"
    text = PARA + "\n\n" + formula + "\n\n" + PARA
    chunks = chunk_document(text, "Maths", target_tokens=60)
    holding = [c for c in chunks if "x_0 = " in c.content or "x_79 = " in c.content]
    assert len(holding) == 1 and holding[0].content.count("$$") == 2


def test_table_not_split():
    table = "| a | b |\n|---|---|\n" + "\n".join(f"| {i} | {i * i} |" for i in range(60))
    chunks = chunk_document(PARA + "\n\n" + table, "T", target_tokens=50)
    holding = [c for c in chunks if "| 0 | 0 |" in c.content]
    assert len(holding) == 1 and "| 59 | 3481 |" in holding[0].content


def test_inline_math_never_cut():
    sentence = "The energy is $E = mc^2$. Next the force is $F = ma$. "
    chunks = chunk_document(sentence * 40, "Physics", target_tokens=30)
    for c in chunks:
        assert c.content.count("$") % 2 == 0, c.content


def test_long_text_splits_with_overlap():
    chunks = chunk_document(PARA * 40, "Bio", target_tokens=100, overlap_tokens=20)
    assert len(chunks) > 3
    for a, b in zip(chunks, chunks[1:]):
        tail = a.content.split(". ")[-2]
        assert tail in b.content          # the next chunk repeats the end of the previous one
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_content_hash_depends_on_text_and_model():
    a = chunk_document(PARA, "Bio", model="m1")[0]
    b = chunk_document(PARA, "Bio", model="m1")[0]
    c = chunk_document(PARA, "Bio", model="m2")[0]
    assert a.content_hash == b.content_hash != c.content_hash
