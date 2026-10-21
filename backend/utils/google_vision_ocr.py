"""
Google Cloud Vision OCR for scanned PDFs.

Each page is rendered to a JPEG (greyscale, 200 dpi) and sent to
images:annotate with DOCUMENT_TEXT_DETECTION, several pages per request and a
few requests at a time. Auth is a service account (GOOGLE_VISION_CREDENTIALS:
the JSON key, raw or base64); the access token is signed here with python-jose
so no extra Google library is needed.
"""
import base64
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import requests as http

from utils.logger import logger

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_ANNOTATE_URL = "https://vision.googleapis.com/v1/images:annotate"
_SCOPE = "https://www.googleapis.com/auth/cloud-vision"
PAGES_PER_REQUEST = 8      # Vision allows 16; 8 keeps each request well under 10 MB
PARALLEL_REQUESTS = 3


class GoogleVisionOCR:
    def __init__(self, credentials: dict):
        self.creds = credentials
        self._token = None
        self._token_expiry = 0.0

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 120:
            return self._token
        from jose import jwt

        now = int(time.time())
        assertion = jwt.encode(
            {"iss": self.creds["client_email"], "scope": _SCOPE, "aud": self.creds.get("token_uri", _TOKEN_URL),
             "iat": now, "exp": now + 3600},
            self.creds["private_key"],
            algorithm="RS256",
            headers={"kid": self.creds.get("private_key_id", "")},
        )
        resp = http.post(self.creds.get("token_uri", _TOKEN_URL), data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion,
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 3600))
        return self._token

    def _annotate(self, images: list) -> list:
        body = {"requests": [
            {"image": {"content": base64.b64encode(img).decode()},
             "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
             "imageContext": {"languageHints": ["en"]}}
            for img in images
        ]}
        for attempt in range(3):
            resp = http.post(_ANNOTATE_URL, json=body, timeout=120,
                             headers={"Authorization": f"Bearer {self._access_token()}"})
            if resp.status_code in (429, 500, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Vision API {resp.status_code}: {resp.text[:300]}")
            out = []
            for r in resp.json().get("responses", []):
                if r.get("error"):
                    logger.warning(f"[GoogleVision] page error: {r['error'].get('message')}")
                out.append((r.get("fullTextAnnotation") or {}).get("text", ""))
            return out
        return [""] * len(images)

    def extract_pdf(self, file_path: str, dpi: int = 200, max_pages: int = 600,
                    on_progress: Optional[Callable[[int, int], None]] = None) -> Optional[str]:
        import fitz
        from PIL import Image

        with fitz.open(file_path) as doc:
            total = min(len(doc), max_pages)
            logger.info(f"[GoogleVision] OCR → {total} pages")

            def render(i: int) -> bytes:
                pix = doc[i].get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
                img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=80, optimize=True)
                img.close()
                return buf.getvalue()

            texts = [""] * total
            done = 0
            batches = [list(range(s, min(s + PAGES_PER_REQUEST, total))) for s in range(0, total, PAGES_PER_REQUEST)]
            # Render on this thread (PyMuPDF documents aren't thread-safe), send in parallel
            with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
                pending = []
                for batch in batches:
                    pending.append((batch, pool.submit(self._annotate, [render(i) for i in batch])))
                    while len(pending) >= PARALLEL_REQUESTS or (pending and batch is batches[-1]):
                        b, fut = pending.pop(0)
                        for i, t in zip(b, fut.result()):
                            texts[i] = t
                        done += len(b)
                        if on_progress:
                            try:
                                on_progress(done, total)
                            except Exception:
                                pass

        text = "\n\n".join(t.strip() for t in texts if t and t.strip())
        logger.info(f"[GoogleVision] OCR → {len(text)} chars from {sum(1 for t in texts if t.strip())} pages")
        return text or None


def load_credentials(raw: str) -> Optional[dict]:
    """GOOGLE_VISION_CREDENTIALS as raw JSON or base64-encoded JSON."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        if not raw.startswith("{"):
            raw = base64.b64decode(raw).decode()
        creds = json.loads(raw)
        return creds if creds.get("private_key") and creds.get("client_email") else None
    except Exception as e:
        logger.error(f"[GoogleVision] Could not read GOOGLE_VISION_CREDENTIALS: {e}")
        return None


_instance: Optional[GoogleVisionOCR] = None


def get_google_vision() -> Optional[GoogleVisionOCR]:
    global _instance
    if _instance is None:
        from config.settings import settings

        creds = load_credentials(settings.GOOGLE_VISION_CREDENTIALS)
        if creds:
            _instance = GoogleVisionOCR(creds)
    return _instance
