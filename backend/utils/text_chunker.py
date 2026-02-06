from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

class TextChunker:
    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
            is_separator_regex=False,
            separators=["\n\n", "\n", " ", ""]
        )

    def chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """
        Split text using LangChain's RecursiveCharacterTextSplitter.
        If chunk_size/overlap provided here, they override init values (re-initializing splitter).
        """
        if not text:
            return []
            
        # If overrides are provided and different, create a temporary splitter
        current_splitter = self.splitter
        if (chunk_size is not None and chunk_size != self.splitter._chunk_size) or \
           (overlap is not None and overlap != self.splitter._chunk_overlap):
            current_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size or self.splitter._chunk_size,
                chunk_overlap=overlap or self.splitter._chunk_overlap,
                separators=["\n\n", "\n", " ", ""]
            )
            
        return current_splitter.split_text(text)
    
    def chunk_by_tokens(self, text: str, max_tokens: int = 512, overlap_tokens: int = 50) -> List[str]:
        """
        Approximate token-based chunking using char count (1 token ~ 4 chars).
        """
        return self.chunk_text(text, chunk_size=max_tokens*4, overlap=overlap_tokens*4)