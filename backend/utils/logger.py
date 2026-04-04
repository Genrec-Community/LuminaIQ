import logging
import sys
from loguru import logger
from config.settings import settings


class InterceptHandler(logging.Handler):
    """
    Default handler from logging to intercept standard logging messages 
    and route them to loguru.
    """
    def emit(self, record: logging.LogRecord):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def log_filter(record):
    """
    Filter to reduce noisy HTTP logs.
    """
    FILTER_PATTERNS = [
        "OPTIONS",  # CORS preflight requests
        "GET /api/v1/documents/",  # Document polling
        "GET /health",  # Health checks
        "GET / HTTP",  # Root endpoint
    ]
    message = record["message"]
    
    # Filter out noisy patterns
    for pattern in FILTER_PATTERNS:
        if pattern in message:
            return False
            
    return True


def setup_logging():
    """
    Configure loguru logging with console and file handlers, 
    and intercept standard python logging.
    """
    # Remove default loguru handler
    logger.remove()

    # Define common human-readable format
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> │ "
        "<level>{level: <8}</level> │ "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    # 1. Console Handler (Human Readable)
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=log_format,
        filter=log_filter,
        colorize=True,
        enqueue=True,
    )

    # 2. File Handler (JSON format for Production Observation)
    log_file_path = f"{settings.LOG_DIR}/lumina_backend.log"
    logger.add(
        log_file_path,
        level=settings.LOG_LEVEL,
        # serialize output to JSON. Built-in loguru serialization provides time, level, message, name, etc.
        serialize=True,
        filter=log_filter,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        enqueue=True,
    )

    # 3. Intercept standard logging from noisy third-party frameworks
    loggers_to_intercept = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "httpx",
        "httpcore"
    ]
    
    # Intercept root
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Force specific loggers to use interceptor and not propagate to root
    for logger_name in loggers_to_intercept:
        std_logger = logging.getLogger(logger_name)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False
        
        if logger_name in ["httpx", "httpcore"]:
            std_logger.setLevel(logging.WARNING)

    return logger

# Initialize logging configuration immediately upon import
logger = setup_logging()
