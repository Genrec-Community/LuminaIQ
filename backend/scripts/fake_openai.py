"""
A tiny stand-in for an OpenAI-compatible API, for local development and tests
without real keys. Not for production.

    uv run uvicorn scripts.fake_openai:app --port 9999
    SMALL_LLM_BASE_URL=http://localhost:9999/v1  SMALL_LLM_API_KEY=x  SMALL_LLM_MODEL=fake
    EMBEDDING_BASE_URL=http://localhost:9999/v1  EMBEDDING_DIMENSION=256  EMBEDDING_MODEL=fake-embed
    RERANK_BASE_URL=http://localhost:9999/v1     RERANK_API_KEY=x

- /v1/embeddings: hashed bag-of-words vectors (texts sharing words are similar),
  sized by the FAKE_EMBED_DIM env var (default 256).
- /v1/chat/completions: answers by quoting the first excerpt in the system prompt
  with a [1](1) citation; for query-rewrite prompts it returns the latest message.
  Supports stream=true.
  Quiz, flashcard and mindmap prompts get valid JSON with fresh, numbered items. Messages with
  an image part get a transcript of a fixed physics question; answers include LaTeX.
- /v1/rerank: scores documents by word overlap with the query.
"""
import hashlib
import json
import math
import os
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
DIM = int(os.environ.get("FAKE_EMBED_DIM", "256"))
_WORD = re.compile(r"[a-z]{3,}")


def _words(text: str):
    return _WORD.findall(text.lower())


def _vector(text: str):
    v = [0.0] * DIM
    for w in _words(text):
        v[int(hashlib.md5(w[:6].encode()).hexdigest(), 16) % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


@app.post("/v1/embeddings")
async def embeddings(req: Request):
    body = await req.json()
    inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
    return {"object": "list", "model": body.get("model", "fake"),
            "data": [{"object": "embedding", "index": i, "embedding": _vector(t)} for i, t in enumerate(inputs)],
            "usage": {"prompt_tokens": 1, "total_tokens": 1}}


def _study_json(last: str):
    """JSON for the study-tool generators, or None for other prompts."""
    tag = uuid.uuid4().hex[:6]
    m = re.search(r"generate (\d+) multiple-choice", last)
    if m:
        return json.dumps([{"question": f"Question {tag}-{i}?", "options": [
            {"option": "A", "text": f"Right {tag}-{i}"}, {"option": "B", "text": "Wrong one"},
            {"option": "C", "text": "Wrong two"}, {"option": "D", "text": "Wrong three"}],
            "correct_answer": "A", "explanation": f"Because of Right {tag}-{i}."} for i in range(int(m.group(1)))])
    m = re.search(r"Generate exactly (\d+) flashcards", last)
    if m:
        return json.dumps([{"front": f"Term {tag}-{i}", "back": "Meaning."} for i in range(int(m.group(1)))])
    if "knowledge mapping expert" in last:
        return json.dumps({"nodes": [{"id": "1", "label": "Topic", "level": 0},
                                     {"id": "2", "label": f"Idea {tag}", "level": 1, "parent": "1"}],
                           "edges": [{"from": "1", "to": "2"}]})
    return None


def _answer(messages):
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    last = messages[-1]["content"] if messages else ""
    if isinstance(last, list):   # a photo question (OpenAI-style content parts)
        return ("QUESTION: A $2\\,kg$ block is pushed with a force of $10\\,N$. What is its acceleration?\n"
                "DIAGRAM: A block on a flat surface with an arrow labelled 10 N pointing right.")
    study = _study_json(last)
    if study:
        return study
    if system.startswith("Rewrite the student's latest message"):
        return last.split("Latest message:")[-1].strip()
    if system.startswith("Break the student's question"):
        return f"1. {last}"
    m = re.search(r"\[Excerpt 1[^\]]*\]\n(.+?)(?:\n\[Excerpt|\Z)", system, re.S)
    if m:
        return (f"From your book: {m.group(1).strip()[:200]} [1](1)\n\n"
                "Formula: $v = u + at$, and kinetic energy is\n\n$$E_k = \\frac{1}{2}mv^2$$")
    return "I couldn't find this in your book."


@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    text = _answer(body.get("messages", []))
    usage = {"prompt_tokens": 50, "completion_tokens": len(text) // 4, "total_tokens": 50 + len(text) // 4}
    if body.get("stream"):
        def gen():
            for i in range(0, len(text), 12):
                chunk = {"id": "f", "object": "chat.completion.chunk", "created": int(time.time()), "model": body["model"],
                         "choices": [{"index": 0, "delta": {"content": text[i:i + 12]}, "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
            yield ("data: " + json.dumps({"id": "f", "object": "chat.completion.chunk", "created": 0,
                                          "model": body["model"], "choices": [], "usage": usage}) + "\n\n")
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    return JSONResponse({"id": "f", "object": "chat.completion", "created": int(time.time()), "model": body["model"],
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                      "finish_reason": "stop"}], "usage": usage})


@app.post("/v1/rerank")
async def rerank(req: Request):
    body = await req.json()
    q = set(_words(body["query"]))
    scored = [{"index": i, "relevance_score": len(q & set(_words(d))) / (len(q) or 1)}
              for i, d in enumerate(body["documents"])]
    scored.sort(key=lambda r: -r["relevance_score"])
    return {"results": scored[: body.get("top_n", len(scored))]}
