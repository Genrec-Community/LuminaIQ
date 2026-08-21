from typing import List

from llama_index.core.node_parser import SentenceSplitter


class TextChunker:
    """LlamaIndex sentence-aware token chunking for document ingestion."""

    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.splitter = self._build_splitter(chunk_size, overlap)

    @staticmethod
    def _build_splitter(chunk_size: int, overlap: int) -> SentenceSplitter:
        return SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=min(overlap, max(0, chunk_size - 1)),
            paragraph_separator="\n\n",
        )

    def chunk_text(
        self,
        text: str,
        chunk_size: int = None,
        overlap: int = None,
    ) -> List[str]:
        if not text:
            return []
        size = chunk_size or self.chunk_size
        chunk_overlap = self.overlap if overlap is None else overlap
        splitter = (
            self.splitter
            if size == self.chunk_size and chunk_overlap == self.overlap
            else self._build_splitter(size, chunk_overlap)
        )
        return splitter.split_text(text)

    def chunk_by_tokens(
        self,
        text: str,
        max_tokens: int = 512,
        overlap_tokens: int = 50,
    ) -> List[str]:
        return self.chunk_text(text, max_tokens, overlap_tokens)
