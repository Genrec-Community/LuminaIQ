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
PAGES_PER_REQUEST = 4      # small batches keep memory low on a 512 MB server
PARALLEL_REQUESTS = 2
MAX_SIDE_PX = 2400         # longest side sent to Vision; plenty for text, small in memory


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

    def extract_pdf(self, file_path: str, dpi: int = 200, start: int = 0, end: Optional[int] = None,
                    on_progress: Optional[Callable[[int, int], None]] = None) -> Optional[str]:
        """OCR pages start..end-1; on_progress(done, total) counts pages in that range."""
        import fitz
        from PIL import Image

        with fitz.open(file_path) as doc:
            end = len(doc) if end is None else min(end, len(doc))
            total = max(0, end - start)
            logger.info(f"[GoogleVision] OCR → pages {start + 1}-{end} ({total})")

            def render(i: int) -> bytes:
                pix = render_page(doc[i], dpi, MAX_SIDE_PX)
                data = pix.tobytes("jpeg", jpg_quality=80)
                del pix
                return data

            texts = [""] * total
            done = 0
            batches = [list(range(s, min(s + PAGES_PER_REQUEST, total))) for s in range(0, total, PAGES_PER_REQUEST)]
            if not batches:
                return None
            # Render on this thread (PyMuPDF documents aren't thread-safe), send in parallel
            with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
                pending = []
                for batch in batches:
                    pending.append((batch, pool.submit(self._annotate, [render(start + i) for i in batch])))
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


def render_page(page, dpi: int, max_side_px: int):
    """
    Greyscale pixmap of a page at `dpi`, scaled down so its longest side is at
    most max_side_px. Scanned books often store pages at scanner size (a
    two-page spread can be 3500 pt wide), which at 200 dpi would be a ~70 MB
    image per page.
    """
    import fitz

    zoom = dpi / 72.0
    longest = max(page.rect.width, page.rect.height) * zoom
    if longest > max_side_px:
        zoom *= max_side_px / longest
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY, alpha=False)


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
