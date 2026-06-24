"""Request-ID middleware.

Implemented as a plain ASGI middleware (not BaseHTTPMiddleware) so the
request ID is set in the contextvar synchronously, before the downstream
app runs, with no risk of contextvars being lost across a task boundary.

The request ID is exposed two ways:
- via app.core.logging's contextvar, for log records emitted by code that
  has no access to the Request object (e.g. repositories/services);
- via request.state.request_id, for exception handlers and endpoints that
  do have access to the Request object.
"""

import re
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import set_request_id

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _resolve_request_id(headers: Headers) -> str:
    incoming = headers.get(REQUEST_ID_HEADER)
    if incoming and _VALID_REQUEST_ID_RE.match(incoming):
        return incoming
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """Assigns/propagates an X-Request-ID for every HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(Headers(scope=scope))
        set_request_id(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        await self.app(scope, receive, send_with_request_id)
