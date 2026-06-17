"""CSRF middleware that validates Origin / Referer for state-changing requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import Request

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate Origin / Referer headers on state-changing requests.

    Relies on SameSite=Lax cookies as the primary CSRF defense; this adds
    an origin check as defense-in-depth for browsers that don't implement
    SameSite correctly.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: "Callable[[Request], Awaitable]",
    ) -> PlainTextResponse:
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        expected_host = request.base_url.hostname or ""
        if not expected_host:
            return await call_next(request)

        origin = self._parse_origin(request)
        if origin is None:
            return await call_next(request)

        if origin != expected_host:
            return PlainTextResponse("CSRF check failed", status_code=403)

        return await call_next(request)

    @staticmethod
    def _parse_origin(request: Request) -> str | None:
        origin = request.headers.get("origin")
        if origin:
            return _hostname_from_url(origin)
        referer = request.headers.get("referer")
        if referer:
            return _hostname_from_url(referer)
        return None


def _hostname_from_url(raw: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(raw)
    return parsed.hostname or ""
