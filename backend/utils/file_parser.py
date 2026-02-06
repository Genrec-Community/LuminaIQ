import os
from typing import Optional
import pymupdf4llm
from docx import Document
from bs4 import BeautifulSoup
import markdown
from utils.logger import logger

class FileParser:
    @staticmethod
    def extract_text(file_path: str) -> Optional[str]:
        """Extract text from various file formats"""
        try:
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            if ext == '.pdf':
                return FileParser._extract_pdf(file_path)
            elif ext in ['.docx', '.doc']:
                return FileParser._extract_docx(file_path)
            elif ext == '.txt':
                return FileParser._extract_txt(file_path)
            elif ext == '.html':
                return FileParser._extract_html(file_path)
            elif ext == '.md':
                return FileParser._extract_markdown(file_path)
            else:
                logger.warning(f"Unsupported file type: {ext}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return None
    
    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        """Extract text from PDF as Markdown using PyMuPDF4LLM"""
        try:
            # Convert PDF to Markdown
            # This handles tables, images (metadata), and headers much better than raw text extraction
            text = pymupdf4llm.to_markdown(file_path)
            return text.strip()
        except Exception as e:
            logger.error(f"PyMuPDF4LLM extraction failed: {str(e)}")
            # Fallback (optional, but let's fail hard or return empty for now to debug)
            raise e
    
    @staticmethod
    def _extract_docx(file_path: str) -> str:
        """Extract text from DOCX"""
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    
    @staticmethod
    def _extract_txt(file_path: str) -> str:
        """Extract text from TXT"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read().strip()
    
    @staticmethod
    def _extract_html(file_path: str) -> str:
        """Extract text from HTML"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            return soup.get_text().strip()
    
    @staticmethod
    def _extract_markdown(file_path: str) -> str:
        """Extract text from Markdown"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            md_text = f.read()
            html = markdown.markdown(md_text)
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text().strip()
