"""
Split a document's text into passages for search and citations.

- Pages: PDF text marks page breaks with "\\f" (utils/file_parser.PAGE_BREAK), so
  every chunk knows the page it starts on.
- Structure: headings (Markdown, "CHAPTER 3 ...", "3.1 Title") build a path like
  "Chapter 1 › 1.2 Nutrition"; a new section starts a new chunk.
- Never split: $$ maths blocks $$, \\[ ... \\], tables, or inline $...$ formulas.
- Size: about target_tokens per chunk with overlap_tokens repeated from the
  previous chunk, so an idea that straddles a boundary is still found whole.
- Each chunk is embedded with a short context line ("Book › Chapter › Section")
  in front; content_hash covers the model and that exact text, so identical
  passages (the same book uploaded twice) are embedded only once.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

CHARS_PER_TOKEN = 4          # close enough for sizing; exact counts aren't needed
DEFAULT_TARGET_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 75


@dataclass
class Chunk:
    index: int
    page: Optional[int]
    heading: str
    content: str        # shown to the student and cited
    embed_text: str     # what gets embedded: context line + content
    content_hash: str


@dataclass
class _Block:
    text: str
    page: Optional[int]
    heading: str
    atomic: bool = False     # maths, tables: never split
    starts_section: bool = False
    overlap: bool = False    # repeated from the previous chunk


_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_CHAPTER = re.compile(r"^(chapter|unit|part|lesson)\s+[\dIVXLC]+\b.*$", re.IGNORECASE)
_NUMBERED = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+([A-Z][^\n]{1,80})$")
_BOLD_LINE = re.compile(r"^\*\*([^*]{2,80})\*\*$")
_TABLE_LINE = re.compile(r"^\s*\|")
_LIST_LINE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_INLINE_MATH = re.compile(r"\$[^$\n]+\$")


def split_pages(text: str) -> List[Tuple[Optional[int], str]]:
    """[(page, text)]: 1-based pages when the text has page marks, else [(None, text)]."""
    if "\f" not in text:
        return [(None, text)]
    return [(i + 1, part) for i, part in enumerate(text.split("\f"))]


def _heading_level(line: str) -> Optional[Tuple[int, str]]:
    s = line.strip()
    if not s or len(s) > 120:
        return None
    m = _MD_HEADING.match(s)
    if m:
        return len(m.group(1)), m.group(2).strip()
    if _CHAPTER.match(s) and len(s) <= 80:
        return 1, s
    m = _NUMBERED.match(s)
    if m and not s.endswith((".", ",", ";", ":")):
        return 1 + m.group(1).count("."), s
    m = _BOLD_LINE.match(s)
    if m:
        return 4, m.group(1).strip()
    return None


def _blocks(text: str) -> List[_Block]:
    """Headings, paragraphs, lists, tables and maths blocks, in reading order."""
    blocks: List[_Block] = []
    path: List[Tuple[int, str]] = []        # heading stack: (level, title)
    pending_section = False

    for page, page_text in split_pages(text):
        lines = page_text.split("\n")
        i, para = 0, []

        def heading() -> str:
            return " › ".join(t for _, t in path)

        def flush_para():
            nonlocal pending_section
            if para and "".join(para).strip():
                blocks.append(_Block("\n".join(para).strip(), page, heading(), starts_section=pending_section))
                pending_section = False
            para.clear()

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            # Maths blocks: $$ ... $$ or \[ ... \] (possibly over many lines)
            opener = "$$" if stripped.startswith("$$") else "\\[" if stripped.startswith("\\[") else None
            if opener:
                closer = "$$" if opener == "$$" else "\\]"
                rest = stripped[len(opener):]
                j = i
                if closer not in rest:
                    j = i + 1
                    while j < len(lines) and closer not in lines[j]:
                        j += 1
                flush_para()
                blocks.append(_Block("\n".join(lines[i:j + 1]).strip(), page, heading(), atomic=True,
                                     starts_section=pending_section))
                pending_section = False
                i = j + 1
                continue
            if _TABLE_LINE.match(line):
                j = i
                while j < len(lines) and _TABLE_LINE.match(lines[j]):
                    j += 1
                flush_para()
                blocks.append(_Block("\n".join(lines[i:j]).strip(), page, heading(), atomic=True,
                                     starts_section=pending_section))
                pending_section = False
                i = j
                continue
            h = _heading_level(line)
            if h and not para:
                level, title = h
                while path and path[-1][0] >= level:
                    path.pop()
                path.append((level, title))
                pending_section = True
                i += 1
                continue
            if not stripped:
                flush_para()
            elif _LIST_LINE.match(line) and para and not _LIST_LINE.match(para[-1]):
                flush_para()
                para.append(line)
            else:
                para.append(line)
            i += 1
        flush_para()
    return blocks


def _sentences(text: str) -> List[str]:
    """Split on sentence ends, never inside an inline $...$ formula."""
    protected = {}

    def hide(m):
        key = f"\x00{len(protected)}\x00"
        protected[key] = m.group(0)
        return key

    hidden = _INLINE_MATH.sub(hide, text)
    parts = [p for p in _SENTENCE_END.split(hidden) if p.strip()]
    out = []
    for p in parts:
        for key, val in protected.items():
            p = p.replace(key, val)
        out.append(p)
    return out


def _tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _pieces(block: _Block, target: int) -> List[_Block]:
    """A block small enough to pack, or split by sentences (atomic blocks stay whole)."""
    if block.atomic or _tokens(block.text) <= target:
        return [block]
    pieces, current = [], ""
    for s in _sentences(block.text):
        if current and _tokens(current + " " + s) > target:
            pieces.append(current)
            current = s
        else:
            current = f"{current} {s}".strip()
    if current:
        pieces.append(current)
    return [_Block(p, block.page, block.heading, starts_section=block.starts_section and k == 0)
            for k, p in enumerate(pieces)]


def _hash(model: str, embed_text: str) -> str:
    return hashlib.sha256(f"{model}\n{embed_text}".encode("utf-8")).hexdigest()


def chunk_document(text: str, title: str, target_tokens: int = DEFAULT_TARGET_TOKENS,
                   overlap_tokens: int = DEFAULT_OVERLAP_TOKENS, model: str = "") -> List[Chunk]:
    if not text or not text.strip():
        return []
    pieces: List[_Block] = []
    for b in _blocks(text):
        pieces.extend(_pieces(b, target_tokens))

    groups: List[List[_Block]] = []
    current: List[_Block] = []
    size = 0
    for p in pieces:
        t = _tokens(p.text)
        new_section = p.starts_section and current and size >= target_tokens // 4
        if current and (size + t > target_tokens or new_section):
            groups.append(current)
            # Overlap: repeat the tail of this chunk (same section only), then the new piece
            tail, tail_size = [], 0
            if not new_section:
                for q in reversed(current):
                    if q.atomic:
                        break
                    sents = _sentences(q.text)
                    for s in reversed(sents):
                        if tail_size + _tokens(s) > overlap_tokens:
                            break
                        tail.insert(0, _Block(s, q.page, q.heading, overlap=True))
                        tail_size += _tokens(s)
                    break
            current, size = tail, tail_size
        current.append(p)
        size += t
    if current:
        groups.append(current)

    chunks: List[Chunk] = []
    for g in groups:
        # Page and heading come from the chunk's own text, not the overlap repeated from before
        own = next((b for b in g if not b.overlap and b.text.strip()), g[0])
        heading = own.heading
        content = "\n\n".join(b.text for b in g).strip()
        if not content:
            continue
        context = " › ".join(x for x in (title, heading) if x)
        embed_text = f"{context}\n\n{content}" if context else content
        page = own.page
        chunks.append(Chunk(index=len(chunks), page=page, heading=heading, content=content,
                            embed_text=embed_text, content_hash=_hash(model, embed_text)))
    return chunks
