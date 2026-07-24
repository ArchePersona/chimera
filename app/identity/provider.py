"""Identity provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from starlette.requests import Request

from app.identity.contract import UserContext


@runtime_checkable
class IdentityProvider(Protocol):
    """Pluggable interface for resolving user identity from a request.

    Implementations verify the caller's identity and return a trusted
    UserContext.  CHIMERA never performs authentication itself — it
    delegates to the provider supplied at startup.
    """

    async def resolve(self, request: Request) -> UserContext: ...
