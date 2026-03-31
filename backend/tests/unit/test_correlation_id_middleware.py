"""Unit tests for CorrelationIDMiddleware.

Tests cover:
- Auto-generation of correlation IDs when the header is absent.
- Propagation of an incoming X-Correlation-ID header.
- Correct storage in request.state.
- Wiring of the logger ContextVar during the request.
- Cleanup of the ContextVar after the response is returned.

Requirements: 21.1, 21.5
"""

import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from middleware.correlation_id import CorrelationIDMiddleware
from utils.logger import clear_correlation_id, get_correlation_id


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def build_app() -> FastAPI:
    """Return a minimal FastAPI app with CorrelationIDMiddleware attached."""
    app = FastAPI()
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/echo")
    async def echo(request: Request):
        """Return the correlation ID stored in request.state."""
        return {"correlation_id": request.state.correlation_id}

    @app.get("/logger-context")
    async def logger_context(request: Request):
        """Return the correlation ID visible inside the logger ContextVar."""
        return {"logger_correlation_id": get_correlation_id()}

    return app


@pytest.fixture
def client() -> TestClient:
    """Synchronous TestClient wrapping the minimal app."""
    app = build_app()
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCorrelationIDGeneration:
    """Verify correlation ID is generated when not supplied by the caller."""

    def test_generates_correlation_id_if_absent(self, client: TestClient):
        """Response must include X-Correlation-ID even when not sent in request."""
        response = client.get("/echo")

        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers, (
            "X-Correlation-ID header must be present in every response"
        )

    def test_generated_correlation_id_is_valid_uuid(self, client: TestClient):
        """Auto-generated correlation ID must be a valid UUID v4."""
        response = client.get("/echo")
        header_value = response.headers["X-Correlation-ID"]

        # Must not raise ValueError
        parsed = uuid.UUID(header_value)
        assert str(parsed) == header_value

    def test_each_request_gets_unique_correlation_id(self, client: TestClient):
        """Two requests without an incoming header must receive different IDs."""
        r1 = client.get("/echo")
        r2 = client.get("/echo")

        id1 = r1.headers["X-Correlation-ID"]
        id2 = r2.headers["X-Correlation-ID"]

        assert id1 != id2, "Each request must have a unique correlation ID"


class TestCorrelationIDPropagation:
    """Verify incoming X-Correlation-ID header is honoured."""

    def test_respects_incoming_correlation_id(self, client: TestClient):
        """Response must echo the caller-supplied correlation ID unchanged."""
        incoming_id = "my-upstream-trace-id-abc123"
        response = client.get("/echo", headers={"X-Correlation-ID": incoming_id})

        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == incoming_id

    def test_incoming_id_stored_in_request_state(self, client: TestClient):
        """Correlation ID from header must be stored in request.state."""
        incoming_id = "trace-from-gateway-xyz"
        response = client.get("/echo", headers={"X-Correlation-ID": incoming_id})

        body = response.json()
        assert body["correlation_id"] == incoming_id


class TestRequestStateStorage:
    """Verify the correlation ID is accessible via request.state."""

    def test_auto_generated_id_stored_in_request_state(self, client: TestClient):
        """Auto-generated ID in response header must match what's in request.state."""
        response = client.get("/echo")

        header_id = response.headers["X-Correlation-ID"]
        state_id = response.json()["correlation_id"]

        assert header_id == state_id, (
            "The ID in X-Correlation-ID header and request.state must be identical"
        )


class TestLoggerContextVar:
    """Verify the logger ContextVar is correctly set and cleared."""

    def test_logger_context_receives_correlation_id(self, client: TestClient):
        """During request processing the logger ContextVar must hold the correlation ID."""
        incoming_id = "logger-ctx-test-id"
        response = client.get(
            "/logger-context", headers={"X-Correlation-ID": incoming_id}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["logger_correlation_id"] == incoming_id, (
            "The logger ContextVar must reflect the correlation ID during request processing"
        )

    def test_correlation_id_cleared_after_request(self, client: TestClient):
        """After the response is returned the logger ContextVar must be cleared."""
        # Ensure we are starting clean
        clear_correlation_id()

        client.get("/echo", headers={"X-Correlation-ID": "should-be-cleared"})

        # After the request completes the ContextVar should be reset
        assert get_correlation_id() is None, (
            "CorrelationIDMiddleware must clear the ContextVar in its finally block"
        )

    def test_auto_generated_id_wired_to_logger(self, client: TestClient):
        """Auto-generated correlation ID must also be wired into the logger ContextVar."""
        response = client.get("/logger-context")

        assert response.status_code == 200
        body = response.json()
        assert body["logger_correlation_id"] is not None
        # Must be a valid UUID
        uuid.UUID(body["logger_correlation_id"])
