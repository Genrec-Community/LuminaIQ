"""
Client for the LuminaIQ OCR service (ocr-service/: Indra OCR on CPU, its own
Render service). Pages are rendered here exactly as for Google Vision (greyscale
JPEG, long side capped) and sent a few at a time; the service reads them one by
one and returns markdown per page.

Set INDRA_OCR_URL (and INDRA_OCR_TOKEN, the service's OCR_TOKEN) to enable it.
"""
import time
from typing import Callable, List, Optional, Tuple

import requests as http

from utils.logger import logger

PAGES_PER_REQUEST = 4
MAX_SIDE_PX = 2400


class IndraOCRClient:
    def __init__(self, url: str, token: str = ""):
        self.url = url.rstrip("/")
        self.token = token

    def wait_ready(self, timeout: float = 240) -> bool:
        """A free Render service sleeps when idle: wake it and wait for the models."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                h = http.get(f"{self.url}/health", timeout=90).json()
                if h.get("ready"):
                    return True
                if h.get("error"):
                    logger.error(f"[IndraOCR] service failed to load its models: {h['error']}")
                    return False
            except Exception:
                pass
            time.sleep(4)
        logger.error(f"[IndraOCR] service at {self.url} not ready after {timeout:.0f} s")
        return False

    def _ocr_batch(self, images: List[bytes]) -> List[str]:
        files = [("files", (f"p{i}.jpg", img, "image/jpeg")) for i, img in enumerate(images)]
        for attempt in range(3):
            try:
                resp = http.post(f"{self.url}/ocr", files=files, timeout=900,
                                 headers={"X-OCR-Token": self.token})
                if resp.status_code == 503 and attempt < 2:  # still loading / restarted
                    self.wait_ready(120)
                    continue
                resp.raise_for_status()
                return [(p.get("markdown") or p.get("text") or "") for p in resp.json()["pages"]]
            except http.exceptions.ConnectionError:
                if attempt == 2:
                    raise
                self.wait_ready(120)
        raise RuntimeError("OCR service did not answer")

    def extract_pdf(self, file_path: str, dpi: int = 200, start: int = 0, end: Optional[int] = None,
                    on_progress: Optional[Callable[[int, int], None]] = None) -> Tuple[str, int]:
        """
        OCR pages start..end-1. Returns (text, pages_done): on an error it stops
        and reports how far it got, so another engine can read the rest.
        """
        import fitz
        from utils.google_vision_ocr import render_page

        if not self.wait_ready():
            return "", 0
        texts, done = [], 0
        with fitz.open(file_path) as doc:
            end = len(doc) if end is None else min(end, len(doc))
            total = max(0, end - start)
            logger.info(f"[IndraOCR] OCR → pages {start + 1}-{end} ({total})")
            t0 = time.time()
            for s in range(0, total, PAGES_PER_REQUEST):
                batch = range(start + s, start + min(s + PAGES_PER_REQUEST, total))
                images = []
                for i in batch:
                    pix = render_page(doc[i], dpi, MAX_SIDE_PX)
                    images.append(pix.tobytes("jpeg", jpg_quality=85))
                    del pix
                try:
                    texts.extend(self._ocr_batch(images))
                except Exception as e:
                    logger.error(f"[IndraOCR] stopped after {done} of {total} pages: {e}")
                    break
                done += len(images)
                if on_progress:
                    try:
                        on_progress(done, total)
                    except Exception:
                        pass
            logger.info(f"[IndraOCR] {done}/{total} pages in {time.time() - t0:.0f} s")
        text = "\n\n".join(t.strip() for t in texts if t and t.strip())
        return text, done


def warm_up() -> None:
    """Fire-and-forget ping so a sleeping free service is awake by the time pages arrive."""
    client = get_indra_ocr()
    if not client:
        return
    import threading

    def ping():
        try:
            http.get(f"{client.url}/health", timeout=90)
        except Exception:
            pass

    threading.Thread(target=ping, daemon=True).start()


async def keep_warm(interval: float = 600) -> None:
    """
    While this backend is running, ping the OCR service every 10 minutes so it
    doesn't fall asleep (free Render services sleep after 15 idle minutes and
    can take minutes to wake). When the backend itself sleeps, the pings stop
    and the OCR service sleeps too, so free hours aren't burned overnight.
    """
    import asyncio

    while True:
        warm_up()
        await asyncio.sleep(interval)


_instance: Optional[IndraOCRClient] = None


def get_indra_ocr() -> Optional[IndraOCRClient]:
    global _instance
    if _instance is None:
        from config.settings import settings

        if settings.INDRA_OCR_URL:
            _instance = IndraOCRClient(settings.INDRA_OCR_URL, settings.INDRA_OCR_TOKEN)
    return _instance
