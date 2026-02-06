import logging
import sys
from datetime import datetime


class EndpointFilter(logging.Filter):
    """
    Filter to reduce noisy HTTP logs.

    Filters out:
    - OPTIONS requests (CORS preflight)
    - Polling GET requests (document status checks)
    - Health check endpoints
    """

    # Patterns to filter (case-insensitive partial match)
    FILTER_PATTERNS = [
        "OPTIONS",  # CORS preflight requests
        "GET /api/v1/documents/",  # Document polling
        "GET /health",  # Health checks
        "GET / HTTP",  # Root endpoint
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()

        # Filter out noisy patterns
        for pattern in self.FILTER_PATTERNS:
            if pattern in message:
                return False

        return True


class ColoredFormatter(logging.Formatter):
    """
    Colored log formatter for better readability.

    Colors:
    - DEBUG: Cyan
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Bold Red
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"

        return super().format(record)


def setup_logger(name: str = "lumina") -> logging.Logger:
    """
    Setup application logger with filtering and coloring.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        # Use colored formatter
        formatter = ColoredFormatter(
            "%(asctime)s │ %(levelname)-8s │ %(message)s", datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def setup_uvicorn_log_filter():
    """
    Apply filter to uvicorn access logs to reduce noise.
    Call this in main.py after app initialization.
    """
    # Filter uvicorn access logs
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addFilter(EndpointFilter())

    # Also filter httpx if present
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)

    # Filter httpcore
    httpcore_logger = logging.getLogger("httpcore")
    httpcore_logger.setLevel(logging.WARNING)


# Create default logger instance
logger = setup_logger()
