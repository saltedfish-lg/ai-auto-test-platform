"""ASGI correlation ID middleware without adding a public route."""

from __future__ import annotations

import re
from uuid import uuid4

from platform_observability import correlation_context
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_HEADER = b"x-correlation-id"
STANDARD_UUID = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)
STANDARD_ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
W3C_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")


def canonicalize_correlation_id(supplied: str) -> str:
    """Accept only canonical UUID/ULID/W3C trace IDs; replace every other external value."""
    if STANDARD_UUID.fullmatch(supplied) or STANDARD_ULID.fullmatch(supplied):
        return supplied
    if W3C_TRACE_ID.fullmatch(supplied) and supplied != "0" * 32:
        return supplied
    return str(uuid4())


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied_bytes = next(
            (
                value
                for name, value in scope.get("headers", [])
                if name.lower() == CORRELATION_HEADER
            ),
            b"",
        )
        try:
            supplied = supplied_bytes.decode("ascii")
        except UnicodeDecodeError:
            supplied = ""
        correlation_id = canonicalize_correlation_id(supplied)
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        async def send_with_correlation(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((CORRELATION_HEADER, correlation_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        with correlation_context(correlation_id):
            await self.app(scope, receive, send_with_correlation)
