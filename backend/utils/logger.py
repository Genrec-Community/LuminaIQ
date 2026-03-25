import logging
import sys
from loguru import logger
import os

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

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
                return False
        return True


def setup_logger(name: str = "lumina"):
    """
    Setup loguru logger with console and file rotation.
    """
    logger.remove()  # Remove default handler

    # Console logging
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )

    # File logging with rotation
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


# Initialize global logger
logger = setup_logger()
