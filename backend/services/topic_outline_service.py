"""
Topic outline extraction — turns a whole book into a clear, chapter-grouped
list of study topics in the book's own order.

Previously topics were extracted from only the first ~14k characters of a
document, so long textbooks lost most of their chapters. Now we build a
compact "map" of the ENTIRE text and send that to the LLM in one call:

  1. The opening pages (usually the table of contents).
  2. Every line that looks like a heading ("9.3 Refraction", "CHAPTER 4",
     short ALL-CAPS lines), in order, deduplicated (running page headers
     appear once).
  3. Short snippets sampled evenly across the whole text so books without
     clear headings are still covered end to end.

The LLM returns chapters → topics (with a one-line summary each). We store
the flat ordered topic list in documents.topics (used everywhere) and the
structure in documents.topic_outline.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from db.client import get_supabase_client, async_db
from services.llm_service import llm_service
from utils.logger import logger

OPENING_CHARS = 3500
HEADINGS_BUDGET = 9000
SNIPPET_CHARS = 280
MAX_TOPICS = 80

_NUMBERED = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([A-Z][^\n]{2,90})$")
_LABELLED = re.compile(r"^(chapter|unit|part|section|lesson|module|topic)\s+([0-9IVXLC]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen)\b.{0,90}$", re.I)
_NOISE = re.compile(r"(exercise|answers?|index|bibliography|acknowledg|copyright|contents|reprint|isbn|figure|fig\.|table)\b", re.I)


def extract_headings(text: str) -> List[str]:
    """Heading-like lines in document order, deduplicated."""
    seen, out = set(), []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not (4 <= len(line) <= 100) or _NOISE.search(line):
            continue
        letters = [c for c in line if c.isalpha()]
        if len(letters) < 4:
            continue
        is_heading = bool(_NUMBERED.match(line) or _LABELLED.match(line))
        if not is_heading:
            words = line.split()
            upper_ratio = sum(c.isupper() for c in letters) / len(letters)
            is_heading = 2 <= len(words) <= 10 and upper_ratio > 0.85 and not line.endswith((".", ","))
        key = line.lower()
        if is_heading and key not in seen:
            seen.add(key)
            out.append(line)
    return out


def build_document_map(text: str) -> str:
    """Compact representation of a whole document for outline extraction."""
    text = text.replace("\r", "")
    headings = extract_headings(text)
    heading_block, used = [], 0
    for h in headings:
        if used + len(h) + 1 > HEADINGS_BUDGET:
            break
        heading_block.append(h)
        used += len(h) + 1

    n_snippets = 20 if len(heading_block) >= 15 else 45
    body = text[OPENING_CHARS:]
    snippets = []
    if body:
        step = max(1, len(body) // n_snippets)
        for i in range(n_snippets):
            start = i * step
            snippet = " ".join(body[start:start + SNIPPET_CHARS].split())
            if snippet:
                pct = int(100 * (OPENING_CHARS + start) / max(1, len(text)))
                snippets.append(f"[{pct}%] {snippet}")

    return (
        "=== OPENING PAGES ===\n" + text[:OPENING_CHARS]
        + "\n\n=== HEADINGS FOUND (in order) ===\n" + ("\n".join(heading_block) or "(none detected)")
        + "\n\n=== SAMPLES ACROSS THE WHOLE TEXT (position in book) ===\n" + "\n".join(snippets)
    )


OUTLINE_PROMPT = """You are an expert teacher building a study plan from a book.
You get a MAP of the entire book: its opening pages, the headings found in order, and samples from across the whole text.

Produce a clear outline a student can follow, covering the WHOLE book from start to end.

RULES:
1. Chapters in the book's own order, using the book's chapter titles (without numbers).
2. 3-8 topics per chapter, in the order they are taught. At most {max_topics} topics in total.
3. Topic names: specific, quiz-able, max 8 words, unique across the book, no numbering (good: "Refraction through a prism"; bad: "9.4", "Introduction").
4. Each topic gets a one-sentence summary (max 20 words) of what the student will learn.
5. Skip non-teaching material: table of contents, index, exercises, answers, appendices, acknowledgements.

Return ONLY valid JSON:
{{"chapters": [{{"title": "Chapter title", "topics": [{{"name": "Topic", "summary": "..."}}]}}]}}"""


ORGANIZE_PROMPT = """You are an expert teacher. Group these existing study topics into the chapters of the book they come from, in the order a student should study them (the book's order).

RULES:
1. Use every topic EXACTLY as written (copy verbatim), each exactly once.
2. Chapter titles should be short and clear.
3. Order chapters, and topics inside chapters, from first-taught to last-taught.

TOPICS:
{topics}

Return ONLY valid JSON:
{{"chapters": [{{"title": "Chapter title", "topics": ["Topic exactly as written"]}}]}}"""


def _parse_json_object(response: str) -> Optional[Dict[str, Any]]:
    if not response:
        return None
    start, end = response.find("{"), response.rfind("}") + 1
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(response[start:end])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def normalise_outline(data: Optional[Dict[str, Any]], allowed: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Clean LLM output into [{title, topics: [{name, summary}]}].
    With `allowed`, only those exact topic names are kept and any that the
    LLM forgot are appended (so nothing is ever lost).
    """
    allowed_map = {t.lower(): t for t in allowed} if allowed else None
    seen, chapters = set(), []
    for ch in (data or {}).get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        topics = []
        for t in ch.get("topics") or []:
            name = t.get("name") if isinstance(t, dict) else t
            summary = t.get("summary", "") if isinstance(t, dict) else ""
            if not isinstance(name, str):
                continue
            name = " ".join(name.split()).strip(" .")
            if allowed_map is not None:
                name = allowed_map.get(name.lower())
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            topics.append({"name": name, "summary": (summary or "").strip()[:200]})
        if topics:
            title = " ".join(str(ch.get("title") or "Topics").split())[:120]
            chapters.append({"title": title, "topics": topics})

    if allowed:
        missing = [t for t in allowed if t.lower() not in seen]
        if missing:
            chapters.append({"title": "More topics", "topics": [{"name": t, "summary": ""} for t in missing]})

    # Cap total topics, keeping chapter structure
    total, capped = 0, []
    for ch in chapters:
        room = MAX_TOPICS - total
        if room <= 0 and not allowed:
            break
        keep = ch["topics"] if allowed else ch["topics"][:room]
        capped.append({"title": ch["title"], "topics": keep})
        total += len(keep)
    return capped


def flatten(outline: List[Dict[str, Any]]) -> List[str]:
    return [t["name"] for ch in outline for t in ch["topics"]]


class TopicOutlineService:
    def __init__(self):
        self.client = get_supabase_client()
        self._organizing: set = set()

    async def _save(self, document_id: str, topics: List[str], outline: List[Dict[str, Any]]):
        try:
            await async_db(lambda: self.client.table("documents")
                           .update({"topics": topics, "topic_outline": outline})
                           .eq("id", document_id).execute())
        except Exception as e:
            if "topic_outline" not in str(e):
                raise
            logger.warning("documents.topic_outline column missing — run migrations/004_topic_outline.sql")
            await async_db(lambda: self.client.table("documents")
                           .update({"topics": topics})
                           .eq("id", document_id).execute())

    async def _document_text(self, project_id: str, document_id: str) -> str:
        from services.document_service import document_service

        try:
            res = await async_db(lambda: self.client.table("documents")
                                 .select("id, project_id, text_storage_path")
                                 .eq("id", document_id).execute())
            if res.data:
                text = await document_service.load_stored_text(res.data[0])
                if text:
                    return text
        except Exception as e:
            logger.warning(f"Stored text unavailable for {document_id}: {e}")

        # Fallback: first chunks from the vector store
        from services.qdrant_service import qdrant_service
        chunks = await qdrant_service.get_initial_chunks(f"project_{project_id}", document_id, limit=60)
        return "\n".join(chunks)

    async def generate_outline(self, project_id: str, document_id: str) -> List[str]:
        """Extract a chapter outline from the whole document; returns flat topics."""
        text = await self._document_text(project_id, document_id)
        if not text.strip():
            logger.warning(f"No text found for document {document_id}")
            return []

        messages = [
            {"role": "system", "content": OUTLINE_PROMPT.format(max_topics=MAX_TOPICS)},
            {"role": "user", "content": build_document_map(text)},
        ]
        response = await llm_service.chat_completion(messages, temperature=0.2, max_tokens=6000)
        outline = normalise_outline(_parse_json_object(response))
        topics = flatten(outline)
        if topics:
            await self._save(document_id, topics, outline)
            logger.info(f"Outline for {document_id}: {len(outline)} chapters, {len(topics)} topics")
        else:
            logger.warning(f"Outline extraction returned nothing for {document_id}")
        return topics

    async def organize_existing(self, document: Dict[str, Any]) -> None:
        """
        Group an older document's existing topics into chapters without
        renaming them (progress, graph edges and summaries are keyed by name).
        """
        doc_id = document["id"]
        topics = document.get("topics") or []
        if doc_id in self._organizing or len(topics) < 2:
            return
        self._organizing.add(doc_id)
        try:
            messages = [{"role": "user", "content": ORGANIZE_PROMPT.format(
                topics="\n".join(f"- {t}" for t in topics))}]
            response = await llm_service.chat_completion(messages, temperature=0.1, max_tokens=4000)
            outline = normalise_outline(_parse_json_object(response), allowed=topics)
            if outline:
                await self._save(doc_id, flatten(outline), outline)
                logger.info(f"Organized {len(topics)} existing topics into {len(outline)} chapters for {doc_id}")
        except Exception as e:
            logger.warning(f"Could not organize topics for {doc_id}: {e}")
        finally:
            self._organizing.discard(doc_id)


topic_outline_service = TopicOutlineService()
