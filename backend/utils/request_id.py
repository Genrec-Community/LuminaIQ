"""Give every request an id (or keep the caller's X-Request-ID) and echo it back.

Pure ASGI rather than BaseHTTPMiddleware so streaming responses pass through untouched.
"""
import uuid

from utils.logger import request_id_var

HEADER = b"x-request-id"


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        incoming = dict(scope.get("headers") or []).get(HEADER, b"").decode("latin-1").strip()
        rid = incoming[:128] if incoming else uuid.uuid4().hex
        token = request_id_var.set(rid)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != HEADER]
                headers.append((HEADER, rid.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
