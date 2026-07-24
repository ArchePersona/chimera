"""FastAPI dependency for retrieving the current user context."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.identity.contract import UserContext


def get_current_user(request: Request) -> UserContext:
    """Return the verified UserContext set by IdentityMiddleware.

    Raises HTTPException(401) if no identity is present on the request.
    This should only happen if a route uses this dependency without the
    middleware being registered — a startup configuration error.
    """
    ctx = getattr(request.state, "user_context", None)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return ctx
