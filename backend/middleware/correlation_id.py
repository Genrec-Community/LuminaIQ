"""Correlation ID middleware for FastAPI.

**Validates: Requirements 21.1, 21.5**

This middleware ensures every HTTP request has a unique correlation ID that:
- Is sourced from the incoming ``X-Correlation-ID`` request header when present,
  allowing callers to propagate an existing trace ID across services.
- Is generated as a new UUID v4 when the header is absent.
- Is stored in ``request.state.correlation_id`` for downstream handlers and
  other middleware (e.g. TelemetryMiddleware) to read.
- Is set in the logger's ContextVar (``utils.logger.set_correlation_id``) so
  that every log line emitted during the request automatically contains the ID.
- Is cleared from the ContextVar after the response is returned to prevent
  the ID from leaking into subsequent requests on the same async worker.
- Is echoed back to the caller in the ``X-Correlation-ID`` response header.
"""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logger import clear_correlation_id, logger, set_correlation_id


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches a correlation ID to every HTTP request.

    The correlation ID is used for distributed tracing and structured logging.
    It flows through the request lifecycle and appears in all log entries, response
    headers, and telemetry properties.

    Behaviour:
    - Reads ``X-Correlation-ID`` from the incoming request header if available.
    - Falls back to generating a fresh UUID v4 if the header is absent.
    - Sets the ID in ``request.state.correlation_id``.
    - Calls ``set_correlation_id()`` to wire the ID into the logger ContextVar.
    - Adds ``X-Correlation-ID`` to the outgoing response headers.
    - Calls ``clear_correlation_id()`` in a ``finally`` block so the ContextVar
      is reset regardless of whether the handler raised an exception.

    Requirements:
    - 21.1: Generate unique correlation_id for each request.
    - 21.5: Add X-Correlation-ID response header.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request, attaching a correlation ID throughout its lifecycle.

        Args:
            request: The incoming FastAPI/Starlette request.
            call_next: The next middleware or route handler in the chain.

        Returns:
            The HTTP response with the ``X-Correlation-ID`` header set.
        """
        # Honour an incoming correlation ID from upstream callers (e.g. API gateway,
        # frontend, or another microservice), otherwise generate a fresh one.
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        # Persist in request state so route handlers and other middleware can read it
        # without needing to import the ContextVar directly.
        request.state.correlation_id = correlation_id

        # Wire into the logger ContextVar so all log lines emitted during this request
        # include the correlation ID automatically (see utils/logger.py).
        set_correlation_id(correlation_id)

        logger.debug(
            f"[CorrelationIDMiddleware] Assigned correlation_id={correlation_id} "
            f"to {request.method} {request.url.path}"
        )

        try:
            response: Response = await call_next(request)
        finally:
            # Always clear the ContextVar to prevent state leaking into the next
            # request handled by this async worker.
            clear_correlation_id()

        # Echo the correlation ID back to the caller so they can correlate their
        # client-side logs with server-side logs.
        response.headers["X-Correlation-ID"] = correlation_id

        return response
