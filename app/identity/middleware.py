"""Identity middleware — resolves user identity on every request."""

from __future__ import annotations

from typing import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.identity.provider import IdentityProvider


class IdentityMiddleware(BaseHTTPMiddleware):
    """Middleware that resolves user identity via an IdentityProvider.

    Sets ``request.state.user_context`` to a verified ``UserContext``
    for every API request that passes through.  On failure, returns 401
    without revealing the failure reason.

    Web routes (non-/api/) and exempt API routes (health, schema,
    validate, forge) pass through without identity resolution.
    """

    _EXEMPT_PREFIXES: tuple[str, ...] = (
        "/api/health",
        "/api/schema",
        "/api/validate",
        "/api/forge",
        "/static",
    )

    def __init__(self, app: ASGIApp, provider: IdentityProvider) -> None:
        super().__init__(app)
        self._provider = provider

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        for prefix in self._EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        try:
            user_context = await self._provider.resolve(request)
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "Authentication required"},
            )

        request.state.user_context = user_context
        return await call_next(request)
