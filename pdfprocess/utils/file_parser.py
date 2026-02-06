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

        except Exception as e:
            logger.error(f"[FileParser] Error extracting from {file_path}: {str(e)}")
            import traceback

            logger.error(f"[FileParser] Traceback: {traceback.format_exc()}")
            return None

    @staticmethod
    def _extract_pdf(file_path: str) -> Optional[str]:
        """
        Extract text from PDF with multiple fallback methods.

        Order of attempts:
        1. PyMuPDF4LLM - best quality for structured content
        2. PyPDF2 - good fallback for various PDFs
        3. Raw PyMuPDF (fitz) - last resort
        """
        text = None

        # Method 1: PyMuPDF4LLM (best for structured PDFs)
        try:
            import pymupdf4llm

            logger.info(f"[FileParser] Trying PyMuPDF4LLM...")
            text = pymupdf4llm.to_markdown(file_path)
            if text and text.strip():
                logger.info(f"[FileParser] PyMuPDF4LLM succeeded: {len(text)} chars")
                return text.strip()
            else:
                logger.warning(f"[FileParser] PyMuPDF4LLM returned empty text")
        except Exception as e:
            logger.warning(f"[FileParser] PyMuPDF4LLM failed: {e}")

        # Method 2: PyPDF2 (good fallback)
        try:
            from PyPDF2 import PdfReader

            logger.info(f"[FileParser] Trying PyPDF2...")
            reader = PdfReader(file_path)
            pages_text = []

            for i, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
                except Exception as page_err:
                    logger.warning(f"[FileParser] PyPDF2 page {i} failed: {page_err}")
                    continue

            if pages_text:
                text = "\n\n".join(pages_text)
                logger.info(
                    f"[FileParser] PyPDF2 succeeded: {len(text)} chars from {len(pages_text)} pages"
                )
                return text.strip()
            else:
                logger.warning(f"[FileParser] PyPDF2 extracted no text")
        except ImportError:
            logger.warning(f"[FileParser] PyPDF2 not installed")
        except Exception as e:
            logger.warning(f"[FileParser] PyPDF2 failed: {e}")

        # Method 3: Raw PyMuPDF/fitz (last resort)
        try:
            import fitz  # PyMuPDF

            logger.info(f"[FileParser] Trying raw PyMuPDF...")
            doc = fitz.open(file_path)
            pages_text = []

            for i, page in enumerate(doc):
                try:
                    page_text = page.get_text()
                    if page_text:
                        pages_text.append(page_text)
                except Exception as page_err:
                    logger.warning(f"[FileParser] PyMuPDF page {i} failed: {page_err}")
                    continue

            doc.close()

            if pages_text:
                text = "\n\n".join(pages_text)
                logger.info(
                    f"[FileParser] Raw PyMuPDF succeeded: {len(text)} chars from {len(pages_text)} pages"
                )
                return text.strip()
            else:
                logger.warning(f"[FileParser] Raw PyMuPDF extracted no text")
        except Exception as e:
            logger.warning(f"[FileParser] Raw PyMuPDF failed: {e}")

        # All methods failed
        logger.error(f"[FileParser] All PDF extraction methods failed for {file_path}")
        return None

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

        logger.error(f"[FileParser] TXT extraction failed - all encodings failed")
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
