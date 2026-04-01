import logging
import sys
from loguru import logger
import os
import json
from contextvars import ContextVar
from typing import Optional, Any

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Context variable to store correlation ID for the current request
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentation.
    Intercepts standard logging messages and routes them to loguru.
    """
    def emit(self, record: logging.LogRecord):
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def json_formatter(record: dict) -> str:
    """
    Format log record as JSON with correlation ID and structured fields.
    
    Args:
        record: Loguru record dictionary
        
    Returns:
        JSON formatted log string
    """
    # Get correlation ID from context
    correlation_id = correlation_id_var.get()
    
    # Build structured log entry
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "correlation_id": correlation_id,
        "context": {
            "name": record["name"],
            "function": record["function"],
            "line": record["line"],
            "module": record["module"],
        }
    }
    
    # Add extra fields if present
    if record.get("extra"):
        log_entry["context"].update(record["extra"])
    
    # Add exception info if present
    if record.get("exception"):
        log_entry["exception"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else None,
            "value": str(record["exception"].value) if record["exception"].value else None,
        }
    
    return json.dumps(log_entry)


def console_formatter(record: dict) -> str:
    """
    Format log record for console output with correlation ID.
    
    Args:
        record: Loguru record dictionary
        
    Returns:
        Formatted log string for console
    """
    correlation_id = correlation_id_var.get()
    correlation_part = f" | <yellow>corr_id={correlation_id}</yellow>" if correlation_id else ""
    
    return (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>"
        f"{correlation_part} - "
        "<level>{message}</level>\n"
        "{exception}"
    )


def set_correlation_id(correlation_id: str) -> None:
    """
    Set correlation ID for the current context.
    
    Args:
        correlation_id: Unique identifier for request tracing
    """
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """
    Get correlation ID from the current context.
    
    Returns:
        Correlation ID if set, None otherwise
    """
    return correlation_id_var.get()


def clear_correlation_id() -> None:
    """
    Clear correlation ID from the current context.
    """
    correlation_id_var.set(None)


def log_with_context(level: str, message: str, **context: Any) -> None:
    """
    Log a message with additional context fields.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        **context: Additional context fields to include in the log
    """
    logger.bind(**context).log(level, message)


class EndpointFilter(logging.Filter):
    """
    Filter to reduce noisy HTTP logs.
    """
    FILTER_PATTERNS = [
        "OPTIONS",  # CORS preflight requests
        "GET /api/v1/documents/",  # Document polling
        "GET /health",  # Health checks
        "GET / HTTP",  # Root endpoint
        "GET /api/v1/user-data/progress",
        "GET /api/v1/progress",
        "GET /api/v1/user-data/searches",
        "GET /api/v1/learning/knowledge-graph",
        "GET /api/v1/learning/performance",
        "Unauthorized",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self.FILTER_PATTERNS:
            if pattern in message:
                return True
        return True


def setup_logger(name: str = "lumina", json_logs: bool = False):
    """
    Setup loguru logger with console and file rotation.
    Supports both human-readable and JSON structured logging.
    
    Args:
        name: Logger name
        json_logs: If True, use JSON format for file logs
    """
    logger.remove()  # Remove default handler

    # Console logging (human-readable with correlation ID)
    logger.add(
        sys.stdout,
        format=console_formatter,
        level="INFO",
        colorize=True
    )

    # File logging with rotation
    if json_logs:
        # JSON structured logging for production
        logger.add(
            "logs/lumina_{time:YYYY-MM-DD}.json",
            rotation="10 MB",
            retention="30 days",
            format=json_formatter,
            level="DEBUG",
            compression="zip",
            serialize=False  # We handle serialization in json_formatter
        )
    else:
        # Human-readable logging for development
        logger.add(
            "logs/lumina_{time:YYYY-MM-DD}.log",
            rotation="10 MB",
            retention="30 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            compression="zip"
        )

    return logger

def setup_uvicorn_log_filter():
    """
    Apply filter to uvicorn access logs and route them to loguru.
    """
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
    logging.getLogger("uvicorn.error").addFilter(EndpointFilter())
    
    # Intercept existing standard loggers
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    for log_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        logging_logger = logging.getLogger(log_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    # Quiet external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# Initialize global logger (use JSON logs in production via environment variable)
json_logs_enabled = os.getenv("JSON_LOGS", "false").lower() == "true"
logger = setup_logger(json_logs=json_logs_enabled)
