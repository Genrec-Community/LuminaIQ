import os
from typing import Optional
from utils.logger import logger


class FileParser:
    """
    File parser with multiple fallback extraction methods.

    PDF extraction order:
    1. PyMuPDF4LLM (best for structured content)
    2. PyPDF2 (fallback for problematic PDFs)
    3. Raw PyMuPDF/fitz (last resort)
    """

    @staticmethod
    def extract_text(file_path: str) -> Optional[str]:
        """Extract text from various file formats with logging"""
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
            else:
                logger.error(f"[FileParser] Unsupported file type: {ext}")
                return None

        except ValueError:
            raise  # Re-raise extraction failures so document_service marks it failed
        except Exception as e:
            logger.error(f"[FileParser] Error extracting from {file_path}: {str(e)}")
            import traceback
            logger.error(f"[FileParser] Traceback: {traceback.format_exc()}")
            return None

    @staticmethod
    def _try_primary_extraction(file_path: str) -> Optional[str]:
        """
        Attempt text extraction using all standard (non-OCR) methods:
        1. Raw PyMuPDF — best for speed and large books
        2. PyMuPDF4LLM — fallback for structured content
        3. PyPDF2      — last resort

        Returns extracted text (may be short/empty) or None on total failure.
        """
        # Method 1: Raw PyMuPDF/fitz (Fastest)
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
                logger.info(f"[FileParser] Raw PyMuPDF: {len(text)} chars from {len(pages_text)} pages")
                return text.strip()
            logger.warning("[FileParser] Raw PyMuPDF extracted no text")
        except Exception as e:
            logger.warning(f"[FileParser] Raw PyMuPDF failed: {e}")

        # Method 2: PyMuPDF4LLM (Layout analysis - slower)
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

        # Method 3: PyPDF2 (Solid fallback)
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
                logger.info(f"[FileParser] PyPDF2: {len(text)} chars from {len(pages_text)} pages")
                return text.strip()
            logger.warning("[FileParser] PyPDF2 extracted no text")
        except ImportError:
            logger.warning("[FileParser] PyPDF2 not installed")
        except Exception as e:
            logger.warning(f"[FileParser] PyPDF2 failed: {e}")

        return None

    @staticmethod
    def _try_ocr(file_path: str) -> Optional[str]:
        """
        OCR fallback using pdf2image + pytesseract.
        Requires Poppler (pdf2image) and Tesseract (pytesseract) installed on the OS.

        Raises explicitly if OCR produces insufficient text — no silent failures.
        Returns extracted text or None if dependencies are unavailable.
        """
        try:
            from pdf2image import convert_from_path
            import pytesseract

            logger.info("[FileParser] Trying OCR fallback (pdf2image + tesseract)...")
            images = convert_from_path(file_path)
            pages_text = [pytesseract.image_to_string(img) for img in images]
            text = "\n\n".join(t for t in pages_text if t.strip())

            if not text or len(text.strip()) < 200:
                char_count = len(text.strip()) if text else 0
                raise ValueError(
                    f"OCR produced insufficient text ({char_count} chars). "
                    "The file may be a low-quality scan or an image with no readable text."
                )

            logger.info(f"[FileParser] OCR succeeded: {len(text)} chars from {len(images)} pages")
            return text.strip()

        except (ImportError, FileNotFoundError) as e:
            logger.warning(f"[FileParser] OCR unavailable (Tesseract/Poppler not installed): {e}")
            return None
        except ValueError:
            raise  # Re-raise the "insufficient text" error explicitly
        except Exception as e:
            logger.error(f"[FileParser] OCR FAILED: {e}")
            return None

    @staticmethod
    def _extract_pdf(file_path: str) -> Optional[str]:
        """
        2-stage PDF extraction pipeline:

        Stage 1 — Standard extraction (PyMuPDF4LLM → PyPDF2 → raw PyMuPDF).
        Stage 2 — OCR fallback (pdf2image + tesseract), triggered when stage 1
                  produces no text OR fewer than 200 chars (likely a scanned PDF).

        Raises ValueError if both stages fail — never silently returns garbage.
        """
        MIN_CHARS = 200

        # Stage 1: Standard extraction
        text = FileParser._try_primary_extraction(file_path)

        if text and len(text.strip()) >= MIN_CHARS:
            return text

        # Stage 1 produced nothing or too little — try OCR
        if text:
            logger.warning(
                f"[FileParser] Primary extraction yielded only {len(text.strip())} chars "
                f"(< {MIN_CHARS}). Attempting OCR fallback..."
            )
        else:
            logger.warning(
                "[FileParser] Primary extraction returned no text. Attempting OCR fallback..."
            )

        # Stage 2: OCR
        ocr_text = FileParser._try_ocr(file_path)
        if ocr_text and len(ocr_text.strip()) >= MIN_CHARS:
            return ocr_text

        # Both stages failed — raise loudly
        char_count = len(ocr_text.strip()) if ocr_text else (len(text.strip()) if text else 0)
        raise ValueError(
            f"Complete PDF extraction failure: all methods (PyMuPDF, PyPDF2, OCR) yielded "
            f"only {char_count} chars. The file may be encrypted, corrupt, or a "
            "scanned image with no readable text and Tesseract is not installed."
        )

    @staticmethod
    def _extract_docx(file_path: str) -> Optional[str]:
        """Extract text from DOCX"""
        try:
            from docx import Document

            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            logger.info(f"[FileParser] DOCX extracted: {len(text)} chars")
            return text.strip() if text.strip() else None
        except Exception as e:
            logger.error(f"[FileParser] DOCX extraction failed: {e}")
            return None

    @staticmethod
    def _extract_txt(file_path: str) -> Optional[str]:
        """Extract text from TXT with encoding fallback"""
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

        logger.error("[FileParser] TXT extraction failed - all encodings failed")
        return None

    @staticmethod
    def _extract_html(file_path: str) -> Optional[str]:
        """Extract text from HTML"""
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
        """Extract text from Markdown"""
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
