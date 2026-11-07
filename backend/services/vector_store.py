"""
Book passages and their embeddings in Postgres (pgvector), replacing Qdrant.

One `chunks` table for every book: rows carry project_id and document_id, so a
search is filtered to one book (and optionally some of its files). Dense search
uses the HNSW index (cosine); keyword search uses the generated tsvector. Vectors
are sent as pgvector text literals, so no extra client library is needed.
"""

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from db.client import async_db, get_supabase_client
from utils.logger import logger


@dataclass
class Hit:
    chunk_id: int
    document_id: str
    chunk_index: int
    page: Optional[int]
    heading: str
    content: str
    score: float

    def to_dict(self) -> Dict:
        return asdict(self)


def _pg():
    return get_supabase_client().pg


def _vec(v: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def _hits(rows) -> List[Hit]:
    return [Hit(chunk_id=r["id"], document_id=r["document_id"], chunk_index=r["chunk_index"], page=r["page"],
                heading=r["heading"] or "", content=r["content"], score=float(r["score"] or 0)) for r in rows]


def _doc_filter(document_ids: Optional[Iterable[str]]) -> tuple:
    ids = [str(d) for d in document_ids or []]
    return ("AND document_id = ANY(%s::uuid[])", [ids]) if ids else ("", [])


async def existing_vectors(hashes: Iterable[str]) -> Dict[str, str]:
    """Vectors already stored for these content hashes (as pgvector literals), from any book."""
    hashes = list(set(hashes))
    if not hashes:
        return {}
    pg = _pg()
    rows = await async_db(lambda: pg.fetch(
        """SELECT DISTINCT ON (content_hash) content_hash, embedding::text AS v
           FROM chunks WHERE content_hash = ANY(%s) AND embedding IS NOT NULL""", (hashes,)))
    return {r["content_hash"]: r["v"] for r in rows}


async def replace_document_chunks(project_id: str, document_id: str, chunks: List, vectors: List) -> int:
    """
    Store a document's chunks (replacing any it had). `vectors[i]` is a list of
    floats or a pgvector literal (reused from existing_vectors). Returns rows written.
    """
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors differ in length")
    pg = _pg()

    def write():
        with pg.pool.connection() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
                with conn.cursor() as cur:
                    cur.executemany(
                        """INSERT INTO chunks (project_id, document_id, chunk_index, page, heading, content,
                                               content_hash, embedding)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)""",
                        [(project_id, document_id, c.index, c.page, c.heading or None, c.content, c.content_hash,
                          v if isinstance(v, str) else _vec(v)) for c, v in zip(chunks, vectors)])
        return len(chunks)

    return await async_db(write)


async def search_dense(project_id: str, vector: Sequence[float], k: int = 30,
                       document_ids: Optional[Iterable[str]] = None) -> List[Hit]:
    """Closest passages by meaning (cosine similarity, 1 = identical)."""
    pg = _pg()
    extra, params = _doc_filter(document_ids)
    lit = _vec(vector)

    def run():
        with pg.pool.connection() as conn:
            with conn.transaction():
                try:
                    # pgvector >= 0.8: keep scanning the index until enough rows pass the filter.
                    # Older pgvector rejects these settings; the savepoint keeps that error from
                    # aborting the outer transaction (the search would then fail too, and callers
                    # would silently fall back to keyword-only search).
                    with conn.transaction():
                        conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
                        conn.execute("SET LOCAL hnsw.ef_search = 100")
                except Exception:
                    pass
                cur = conn.execute(
                    f"""SELECT id, document_id::text, chunk_index, page, heading, content,
                               1 - (embedding <=> %s::vector) AS score
                        FROM chunks WHERE project_id = %s AND embedding IS NOT NULL {extra}
                        ORDER BY embedding <=> %s::vector LIMIT %s""",
                    [lit, project_id, *params, lit, k])
                return cur.fetchall()

    try:
        return _hits(await async_db(run))
    except Exception as e:
        if "iterative_scan" in str(e) or "ef_search" in str(e):
            logger.debug(f"[VectorStore] {e}")
        raise


async def search_keyword(project_id: str, query: str, k: int = 30,
                         document_ids: Optional[Iterable[str]] = None) -> List[Hit]:
    """Passages matching the query's words (Postgres full-text search, English stemming)."""
    if not query or not query.strip():
        return []
    pg = _pg()
    extra, params = _doc_filter(document_ids)
    rows = await async_db(lambda: pg.fetch(
        f"""WITH q AS (SELECT websearch_to_tsquery('english', %s) AS w,
                              replace(plainto_tsquery('english', %s)::text, '&', '|')::tsquery AS any_word)
            SELECT id, document_id::text, chunk_index, page, heading, content,
                   ts_rank_cd(tsv, q.any_word) + 2 * ts_rank_cd(tsv, q.w) AS score
            FROM chunks, q
            WHERE project_id = %s AND tsv @@ q.any_word {extra}
            ORDER BY score DESC LIMIT %s""",
        [query, query, project_id, *params, k]))
    return _hits(rows)


async def neighbours(document_id: str, chunk_indexes: Iterable[int]) -> List[Hit]:
    idx = sorted(set(int(i) for i in chunk_indexes))
    if not idx:
        return []
    pg = _pg()
    rows = await async_db(lambda: pg.fetch(
        """SELECT id, document_id::text, chunk_index, page, heading, content, 0 AS score
           FROM chunks WHERE document_id = %s AND chunk_index = ANY(%s) ORDER BY chunk_index""",
        (document_id, idx)))
    return _hits(rows)


async def first_chunks(document_id: str, n: int = 3) -> List[str]:
    pg = _pg()
    rows = await async_db(lambda: pg.fetch(
        "SELECT content FROM chunks WHERE document_id = %s ORDER BY chunk_index LIMIT %s", (document_id, n)))
    return [r["content"] for r in rows]


async def count(document_id: str) -> int:
    pg = _pg()
    rows = await async_db(lambda: pg.fetch(
        "SELECT count(*) AS n FROM chunks WHERE document_id = %s AND embedding IS NOT NULL", (document_id,)))
    return int(rows[0]["n"]) if rows else 0


async def delete_document(document_id: str) -> None:
    pg = _pg()
    await async_db(lambda: pg.fetch("DELETE FROM chunks WHERE document_id = %s", (document_id,)))


async def copy_document(source_document_id: str, project_id: str, document_id: str) -> int:
    """Give another book's copy of a document the same passages and vectors (no re-embedding)."""
    pg = _pg()

    def run():
        with pg.pool.connection() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
                cur = conn.execute(
                    """INSERT INTO chunks (project_id, document_id, chunk_index, page, heading, content,
                                           content_hash, embedding, metadata)
                       SELECT %s, %s, chunk_index, page, heading, content, content_hash, embedding, metadata
                       FROM chunks WHERE document_id = %s""",
                    (project_id, document_id, source_document_id))
                return cur.rowcount or 0

    return await async_db(run)
