import time
from typing import Dict, Optional

class PerformanceTracker:
    def __init__(self):
        self._start_time = time.perf_counter()
        self.timings: Dict[str, float] = {}
        self._active_timers: Dict[str, float] = {}

    def start(self, label: str) -> None:
        """Start a timer for a specific label."""
        self._active_timers[label] = time.perf_counter()

    def stop(self, label: str) -> None:
        """Stop the timer for a specific label and record elapsed time."""
        if label in self._active_timers:
            elapsed = time.perf_counter() - self._active_timers.pop(label)
            self.timings[label] = self.timings.get(label, 0.0) + elapsed

    def log_total(self, logger) -> None:
        """Log all timings and total request time in the exact requested format."""
        # Custom mapping for formatting exactly as requested
        label_mapping = {
            "pdf_parsing": "PDF parsing",
            "text_chunking": "Text chunking",  # Added fallback case
            "embedding": "Embedding",
            "qdrant_search": "Qdrant search",
            "llm_response": "LLM response",
            "final_formatting": "Final formatting"
        }
        
        for label, duration in self.timings.items():
            formatted_label = label_mapping.get(label, label)
            # The prompt requested: "[PERF] PDF parsing: 0.83s"
            # It only had "PDF parsing", "Embedding", "Qdrant search", "LLM response" in the example output text,
            # but also requested "final formatting" and "text chunking" in the prompt text.
            if label == "pdf_parsing":
                logger.info(f"[PERF] PDF parsing: {duration:.2f}s")
            elif label == "embedding":
                logger.info(f"[PERF] Embedding: {duration:.2f}s")
            elif label == "qdrant_search":
                logger.info(f"[PERF] Qdrant search: {duration:.2f}s")
            elif label == "llm_response":
                logger.info(f"[PERF] LLM response: {duration:.2f}s")
            else:
                # Handle everything else exactly with their mapped names
                display_label = label_mapping.get(label, label).capitalize() if label not in label_mapping else label_mapping.get(label)
                logger.info(f"[PERF] {display_label}: {duration:.2f}s")

        total_time = time.perf_counter() - self._start_time
        logger.info(f"[PERF] TOTAL: {total_time:.2f}s")
