"""
LuminaIQ OCR service: Indra OCR (datalab-to/indra-ocr, ONNX on CPU) behind a
tiny HTTP API, so scanned books can be read without a paid OCR provider.

  GET  /health           {"ok": true, "ready": bool}
  POST /ocr              multipart "files": page images (JPEG/PNG), at most 8;
                         header X-OCR-Token must match OCR_TOKEN.
                         -> {"pages": [{"text", "markdown", "ms"}], "ms"}

Pages are read one at a time (memory stays flat on a 512 MB instance). The
models are baked into the image at build time, so a cold start needs no download.
"""
import os
import threading
import time

import cv2
import numpy as np
from fastapi import FastAPI, File, Header, HTTPException, UploadFile

OCR_TOKEN = os.environ.get("OCR_TOKEN", "")
THREADS = int(os.environ.get("OCR_THREADS", "1"))
MAX_FILES = 8
MAX_SIDE = int(os.environ.get("OCR_MAX_SIDE", "3000"))

app = FastAPI(title="LuminaIQ OCR")
_conv = None
_load_error = None
_lock = threading.Lock()


def _load():
    global _conv, _load_error
    try:
        import indra_ocr

        _conv = indra_ocr.load(threads=THREADS, mode="ocr")
    except Exception as e:  # noqa: BLE001
        _load_error = f"{type(e).__name__}: {e}"


@app.on_event("startup")
def startup():
    # Load in the background so the port opens at once (Render's health check)
    threading.Thread(target=_load, daemon=True).start()


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"ok": _load_error is None, "ready": _conv is not None, "error": _load_error}


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"service": "luminaiq-ocr", "ready": _conv is not None}


def _decode(data: bytes) -> np.ndarray:
    gray = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise HTTPException(400, "A file is not a readable image.")
    h, w = gray.shape
    if max(h, w) > MAX_SIDE:  # keep memory bounded whatever the client sends
        k = MAX_SIDE / max(h, w)
        gray = cv2.resize(gray, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    return gray


@app.post("/ocr")
def ocr(files: list[UploadFile] = File(...), x_ocr_token: str = Header(default="")):
    if OCR_TOKEN and x_ocr_token != OCR_TOKEN:
        raise HTTPException(401, "Bad or missing X-OCR-Token.")
    if _load_error:
        raise HTTPException(503, f"OCR models failed to load: {_load_error}")
    if _conv is None:
        raise HTTPException(503, "OCR models are still loading. Try again shortly.")
    if not files or len(files) > MAX_FILES:
        raise HTTPException(400, f"Send 1 to {MAX_FILES} page images.")

    t0 = time.perf_counter()
    pages = []
    for f in files:
        gray = _decode(f.file.read())
        t = time.perf_counter()
        with _lock:  # one page at a time: flat memory
            page = _conv.ocr(gray)
        pages.append({
            "text": page.text or "",
            "markdown": page.markdown or "",
            "ms": round((time.perf_counter() - t) * 1000),
        })
        del gray
    return {"pages": pages, "ms": round((time.perf_counter() - t0) * 1000)}
