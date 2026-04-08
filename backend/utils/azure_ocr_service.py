"""
Azure Document Intelligence — prebuilt-read OCR Service

Uses Azure Document Intelligence (formerly Form Recognizer) REST API
to extract text from:
  - Scanned PDFs (triggered when PyMuPDF extracts < 200 chars)
  - Image files (.jpg, .png, .bmp, .tiff, .gif, .webp)
  - Handwritten text and mixed-language documents

API Flow:
  1. POST {endpoint}/formrecognizer/documentModels/prebuilt-read:analyze?api-version=2023-07-31
     Content-Type: application/octet-stream
     → 202 Accepted, Operation-Location header
  2. GET {operation_location}  (poll every 2s until status = "succeeded" | "failed")
  3. Parse analyzeResult.content → plain text

Supported formats: PDF, JPEG, PNG, BMP, TIFF, DOCX, XLSX, PPTX, HTML
"""

import time
import requests as http
from typing import Optional
from utils.logger import logger


class AzureOCRService:
    """
    Azure Document Intelligence REST API client (sync only).

    Uses the prebuilt-read model for general OCR text extraction.
    All HTTP calls are synchronous (requests library) — safe to call
    from ThreadPoolExecutor threads without asyncio issues.

    Usage:
        text = service.extract_text_sync(file_path)
    """

    API_VERSION = "2023-07-31"
    POLL_INTERVAL_S = 2.0    # seconds between status polls
    MAX_POLL_TIME_S = 300.0  # max wait (5 min — large PDFs can take a while)
    SUBMIT_TIMEOUT_S = 60    # timeout for the initial POST
    POLL_TIMEOUT_S = 30      # timeout per GET poll request

    def __init__(self, endpoint: str, key: str):
        self.endpoint = endpoint.rstrip("/")
        self.key = key
        self.analyze_url = (
            f"{self.endpoint}/formrecognizer/documentModels/prebuilt-read:analyze"
            f"?api-version={self.API_VERSION}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def extract_text_sync(self, file_path: str) -> Optional[str]:
        """
        Full OCR pipeline: submit file → poll → return extracted text.

        Args:
            file_path: Path to the file to OCR (PDF, image, etc.)

        Returns:
            Extracted text as a plain string, or None on failure.
        """
        try:
            with open(file_path, "rb") as fh:
                file_bytes = fh.read()

            file_size_mb = len(file_bytes) / (1024 * 1024)
            logger.info(
                f"[AzureOCR] Submitting {file_size_mb:.2f} MB to Document Intelligence "
                f"({self.analyze_url})"
            )

            # Step 1 — Submit
            operation_location = self._submit(file_bytes)
            if not operation_location:
                return None

            # Step 2 — Poll until done
            return self._poll(operation_location)

        except FileNotFoundError:
            logger.error(f"[AzureOCR] File not found: {file_path}")
            return None
        except PermissionError:
            logger.error(f"[AzureOCR] Permission denied: {file_path}")
            return None
        except Exception as e:
            logger.error(f"[AzureOCR] Unexpected error for {file_path}: {e}")
            import traceback
            logger.error(f"[AzureOCR] {traceback.format_exc()}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Submit
    # ──────────────────────────────────────────────────────────────────────────

    def _submit(self, file_bytes: bytes) -> Optional[str]:
        """POST file bytes → return Operation-Location URL."""
        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Content-Type": "application/octet-stream",
        }

        try:
            resp = http.post(
                self.analyze_url,
                headers=headers,
                data=file_bytes,
                timeout=self.SUBMIT_TIMEOUT_S,
            )

            if resp.status_code == 202:
                op_url = resp.headers.get("Operation-Location", "")
                if op_url:
                    logger.info(f"[AzureOCR] Job accepted → {op_url}")
                    return op_url
                logger.error("[AzureOCR] 202 but missing Operation-Location header")
                return None

            logger.error(
                f"[AzureOCR] Submit failed [{resp.status_code}]: {resp.text[:500]}"
            )
            return None

        except http.exceptions.Timeout:
            logger.error(f"[AzureOCR] Submit timed out ({self.SUBMIT_TIMEOUT_S}s)")
            return None
        except http.exceptions.ConnectionError as e:
            logger.error(f"[AzureOCR] Connection error: {e}")
            return None
        except Exception as e:
            logger.error(f"[AzureOCR] Submit error: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Poll
    # ──────────────────────────────────────────────────────────────────────────

    def _poll(self, operation_url: str) -> Optional[str]:
        """Poll until succeeded/failed, then parse the result."""
        headers = {"Ocp-Apim-Subscription-Key": self.key}
        elapsed = 0.0

        logger.info(
            f"[AzureOCR] Polling (max {self.MAX_POLL_TIME_S:.0f}s, "
            f"every {self.POLL_INTERVAL_S:.0f}s)..."
        )

        while elapsed < self.MAX_POLL_TIME_S:
            time.sleep(self.POLL_INTERVAL_S)
            elapsed += self.POLL_INTERVAL_S

            try:
                resp = http.get(
                    operation_url, headers=headers, timeout=self.POLL_TIMEOUT_S
                )

                if resp.status_code != 200:
                    logger.warning(
                        f"[AzureOCR] Poll [{resp.status_code}] — retrying"
                    )
                    continue

                data = resp.json()
                status = data.get("status", "unknown")

                if status == "succeeded":
                    logger.info(f"[AzureOCR] Succeeded after ~{elapsed:.0f}s")
                    return self._parse(data)

                elif status == "failed":
                    error = data.get("error", {})
                    logger.error(f"[AzureOCR] Job failed: {error}")
                    return None

                elif status in ("running", "notStarted"):
                    logger.info(f"[AzureOCR] {status} ({elapsed:.0f}s elapsed)")

                else:
                    logger.warning(f"[AzureOCR] Unknown status: {status!r}")

            except http.exceptions.Timeout:
                logger.warning(f"[AzureOCR] Poll timeout at {elapsed:.0f}s — retrying")
            except http.exceptions.ConnectionError as e:
                logger.warning(f"[AzureOCR] Poll connection error: {e} — retrying")
            except Exception as e:
                logger.warning(f"[AzureOCR] Poll error: {e} — retrying")

        logger.error(f"[AzureOCR] Timed out after {self.MAX_POLL_TIME_S:.0f}s")
        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Parse
    # ──────────────────────────────────────────────────────────────────────────

    def _parse(self, data: dict) -> Optional[str]:
        """
        Extract plain text from Document Intelligence response.

        The prebuilt-read model puts the full document text in
        analyzeResult.content — no manual line joining needed.
        """
        try:
            result = data.get("analyzeResult", {})

            # Primary: analyzeResult.content (full text, preferred)
            content = result.get("content", "")
            if content and content.strip():
                pages = result.get("pages", [])
                logger.info(
                    f"[AzureOCR] Extracted {len(content)} chars "
                    f"from {len(pages)} page(s)"
                )
                return content.strip()

            # Fallback: join lines from pages (shouldn't be needed, but safe)
            pages = result.get("pages", [])
            if not pages:
                logger.warning("[AzureOCR] No pages in response")
                return None

            all_text = []
            for page in pages:
                lines = page.get("lines", [])
                page_text = "\n".join(
                    line.get("content", "") for line in lines
                    if line.get("content", "").strip()
                )
                if page_text:
                    all_text.append(page_text)

            if not all_text:
                logger.warning("[AzureOCR] No text found in any page")
                return None

            full = "\n\n".join(all_text)
            logger.info(f"[AzureOCR] Extracted {len(full)} chars (line fallback)")
            return full

        except Exception as e:
            logger.error(f"[AzureOCR] Parse error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None


# ──────────────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────────────

def get_azure_ocr_service() -> Optional[AzureOCRService]:
    """
    Return a configured AzureOCRService if credentials exist in settings.
    Returns None if AZURE_CV_ENDPOINT or AZURE_CV_KEY is not set.
    """
    try:
        from config.settings import settings
        endpoint = settings.AZURE_CV_ENDPOINT
        key = settings.AZURE_CV_KEY

        if endpoint and key:
            logger.info(f"[AzureOCR] Configured → {endpoint}")
            return AzureOCRService(endpoint=endpoint, key=key)

        logger.info("[AzureOCR] Not configured (AZURE_CV_ENDPOINT/KEY missing)")
        return None
    except Exception as e:
        logger.error(f"[AzureOCR] Init failed: {e}")
        return None
