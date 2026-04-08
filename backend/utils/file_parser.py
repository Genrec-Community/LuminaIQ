import asyncio
import os
from typing import Optional
from utils.logger import logger


class FileParser:
    """
    File parser with multi-stage extraction and smart OCR routing.

    PDF extraction order:
    1. PyMuPDF4LLM (best for digital/structured PDFs)
    2. PyPDF2        (solid fallback)
    3. Raw PyMuPDF   (last standard resort)
    → If < 200 chars extracted (likely scanned):
    4. Azure Computer Vision Read API   (preferred — cloud, high accuracy)
    5. Tesseract / pdf2image             (local fallback if Azure not configured)

    Image files (.jpg, .jpeg, .png, .bmp, .tiff, .gif, .webp):
    → Azure Computer Vision OCR  (primary)
    → Tesseract via PIL           (fallback if Azure not configured)
    """

    # Minimum chars to consider primary extraction successful
    MIN_TEXT_CHARS = 200
    # Minimum chars for images (images may have less dense text)
    MIN_IMAGE_CHARS = 50

    # ──────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def extract_text(file_path: str) -> Optional[str]:
        """
        Extract text from any supported file format.

        This is synchronous and safe to call from run_in_executor.
        Azure OCR (async) is invoked via asyncio.run() inside the executor thread.

        Supported: pdf, docx, txt, html, md, jpg, jpeg, png, bmp, tiff, tif, gif, webp
        """
        logger.info(f"[FileParser] Extracting from: {file_path}")

        try:
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            if ext == ".pdf":
                return FileParser._extract_pdf(file_path)
            elif ext in [".docx", ".doc"]:
                return FileParser._extract_docx(file_path)
            elif ext == ".txt":
                return FileParser._extract_txt(file_path)
            elif ext == ".html":
                return FileParser._extract_html(file_path)
            elif ext == ".md":
                return FileParser._extract_markdown(file_path)
            elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"]:
                return FileParser._extract_image(file_path)
            else:
                logger.error(f"[FileParser] Unsupported file type: {ext}")
                return None

        except ValueError:
            raise  # Re-raise so document_service marks the doc as failed
        except Exception as e:
            logger.error(f"[FileParser] Error extracting from {file_path}: {e}")
            import traceback
            logger.error(f"[FileParser] Traceback: {traceback.format_exc()}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # PDF extraction — 2-stage pipeline
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_pdf(file_path: str) -> Optional[str]:
        """
        2-stage PDF extraction:

        Stage 1 — Standard text extraction (PyMuPDF4LLM → PyPDF2 → raw PyMuPDF).
                   Fast path for digital/text-layer PDFs.

        Stage 2 — Azure Document Intelligence OCR (for scanned PDFs).
                   Triggered when Stage 1 yields < MIN_TEXT_CHARS.

        Raises ValueError if all stages fail.
        """
        # ── Stage 1: Standard text extraction ─────────────────────────────────
        text = FileParser._try_primary_extraction(file_path)

        if text and len(text.strip()) >= FileParser.MIN_TEXT_CHARS:
            logger.info(
                f"[FileParser] Digital PDF: primary extraction succeeded "
                f"({len(text)} chars). OCR not needed."
            )
            return text

        # Stage 1 yielded nothing or too little — scanned PDF
        char_count = len(text.strip()) if text else 0
        logger.warning(
            f"[FileParser] Primary extraction yielded only {char_count} chars "
            f"(< {FileParser.MIN_TEXT_CHARS}). PDF appears scanned → Azure OCR..."
        )

        # ── Stage 2: Azure Document Intelligence OCR ──────────────────────────
        azure_text = FileParser._try_azure_ocr_sync(file_path)
        if azure_text and len(azure_text.strip()) >= FileParser.MIN_TEXT_CHARS:
            return azure_text

        # ── All stages exhausted ──────────────────────────────────────────────
        best_text = azure_text or text
        final_count = len(best_text.strip()) if best_text else 0
        raise ValueError(
            f"PDF extraction failed: all methods yielded only {final_count} chars. "
            "The file may be encrypted, corrupt, or contain no readable text."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Image extraction — Azure OCR only
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_image(file_path: str) -> Optional[str]:
        """
        Extract text from image files using Azure Document Intelligence OCR.

        Supported: jpg, jpeg, png, bmp, tiff, tif, gif, webp
        """
        _, ext = os.path.splitext(file_path)
        logger.info(
            f"[FileParser] Image file ({ext.lower()}) → Azure Document Intelligence OCR"
        )

        azure_text = FileParser._try_azure_ocr_sync(file_path)
        if azure_text and len(azure_text.strip()) >= FileParser.MIN_IMAGE_CHARS:
            return azure_text

        if azure_text is None:
            raise ValueError(
                "Azure Document Intelligence OCR is not configured "
                "(AZURE_CV_ENDPOINT/AZURE_CV_KEY missing in .env). "
                "Cannot extract text from image files."
            )

        char_count = len(azure_text.strip()) if azure_text else 0
        raise ValueError(
            f"Image OCR produced insufficient text ({char_count} chars). "
            "The image may contain no readable text, or text is too small/blurry."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Azure Document Intelligence OCR
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _try_azure_ocr_sync(file_path: str) -> Optional[str]:
        """
        Call Azure Document Intelligence (prebuilt-read) for OCR.

        Uses synchronous HTTP (requests library) — safe for executor threads.

        Returns:
            Extracted text, or None if Azure is not configured or fails.
        """
        try:
            from utils.azure_ocr_service import get_azure_ocr_service

            service = get_azure_ocr_service()
            if service is None:
                logger.info("[FileParser] Azure OCR not configured — skipping")
                return None

            logger.info(f"[FileParser] Azure Document Intelligence OCR → {file_path}")
            result = service.extract_text_sync(file_path)
            if result:
                logger.info(f"[FileParser] Azure OCR → {len(result)} chars extracted")
            else:
                logger.warning("[FileParser] Azure OCR returned no text")
            return result

        except Exception as e:
            logger.error(f"[FileParser] Azure OCR failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Standard text extraction — unchanged
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _try_primary_extraction(file_path: str) -> Optional[str]:
        """
        Attempt text extraction using standard (non-OCR) methods:
        1. PyMuPDF4LLM — best for structured/digital PDFs
        2. PyPDF2      — solid fallback
        3. Raw PyMuPDF — last resort before OCR

        Returns extracted text (may be short/empty for scanned PDFs) or None.
        """
        # Method 1: PyMuPDF4LLM
        try:
            import pymupdf4llm
            logger.info("[FileParser] Trying PyMuPDF4LLM...")
            text = pymupdf4llm.to_markdown(file_path)
            if text and text.strip():
                logger.info(f"[FileParser] PyMuPDF4LLM: {len(text)} chars")
                return text.strip()
            logger.warning("[FileParser] PyMuPDF4LLM returned empty text")
        except Exception as e:
            logger.warning(f"[FileParser] PyMuPDF4LLM failed: {e}")

        # Method 2: PyPDF2
        try:
            from PyPDF2 import PdfReader
            logger.info("[FileParser] Trying PyPDF2...")
            reader = PdfReader(file_path)
            pages_text = []
            for i, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
                except Exception as page_err:
                    logger.warning(f"[FileParser] PyPDF2 page {i} failed: {page_err}")
            if pages_text:
                text = "\n\n".join(pages_text)
                logger.info(
                    f"[FileParser] PyPDF2: {len(text)} chars from {len(pages_text)} pages"
                )
                return text.strip()
            logger.warning("[FileParser] PyPDF2 extracted no text")
        except ImportError:
            logger.warning("[FileParser] PyPDF2 not installed")
        except Exception as e:
            logger.warning(f"[FileParser] PyPDF2 failed: {e}")

        # Method 3: Raw PyMuPDF/fitz
        try:
            import fitz
            logger.info("[FileParser] Trying raw PyMuPDF...")
            doc = fitz.open(file_path)
            pages_text = []
            for i, page in enumerate(doc):
                try:
                    page_text = page.get_text()
                    if page_text:
                        pages_text.append(page_text)
                except Exception as page_err:
                    logger.warning(f"[FileParser] PyMuPDF page {i} failed: {page_err}")
            doc.close()
            if pages_text:
                text = "\n\n".join(pages_text)
                logger.info(
                    f"[FileParser] Raw PyMuPDF: {len(text)} chars from {len(pages_text)} pages"
                )
                return text.strip()
            logger.warning("[FileParser] Raw PyMuPDF extracted no text")
        except Exception as e:
            logger.warning(f"[FileParser] Raw PyMuPDF failed: {e}")

        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Text-based file formats
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_docx(file_path: str) -> Optional[str]:
        """Extract text from DOCX files."""
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            logger.info(f"[FileParser] DOCX extracted: {len(text)} chars")
            return text.strip() if text.strip() else None
        except Exception as e:
            logger.error(f"[FileParser] DOCX extraction failed: {e}")
            return None

    @staticmethod
    def _extract_txt(file_path: str) -> Optional[str]:
        """Extract text from TXT files with encoding auto-detection."""
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    text = f.read().strip()
                    if text:
                        logger.info(
                            f"[FileParser] TXT extracted ({encoding}): {len(text)} chars"
                        )
                        return text
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"[FileParser] TXT extraction failed: {e}")
                return None
        logger.error("[FileParser] TXT extraction failed — all encodings tried")
        return None

    @staticmethod
    def _extract_html(file_path: str) -> Optional[str]:
        """Extract visible text from HTML files."""
        try:
            from bs4 import BeautifulSoup
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
                text = soup.get_text().strip()
                logger.info(f"[FileParser] HTML extracted: {len(text)} chars")
                return text if text else None
        except Exception as e:
            logger.error(f"[FileParser] HTML extraction failed: {e}")
            return None

    @staticmethod
    def _extract_markdown(file_path: str) -> Optional[str]:
        """Extract text from Markdown files (strips markup)."""
        try:
            import markdown
            from bs4 import BeautifulSoup
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                md_text = f.read()
                html = markdown.markdown(md_text)
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text().strip()
                logger.info(f"[FileParser] Markdown extracted: {len(text)} chars")
                return text if text else None
        except Exception as e:
            logger.error(f"[FileParser] Markdown extraction failed: {e}")
            return None
