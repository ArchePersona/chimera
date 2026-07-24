"""Development identity provider — verifies signed handshakes."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.identity.contract import IdentityHandshake, UserContext
from app.identity.signing import decode_handshake, verify_handshake


class _NonceStore:
    """In-memory nonce store with TTL and bounded size."""

    def __init__(self, max_size: int = 10_000, ttl_seconds: int = 300) -> None:
        self._used: dict[str, float] = {}  # nonce -> expiry timestamp
        self._max_size = max_size
        self._ttl = ttl_seconds

    def is_used(self, nonce: str) -> bool:
        self._cleanup()
        return nonce in self._used

    def mark_used(self, nonce: str) -> None:
        self._cleanup()
        if len(self._used) >= self._max_size:
            self._evict_oldest()
        self._used[nonce] = time.monotonic() + self._ttl

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired = [n for n, exp in self._used.items() if exp <= now]
        for n in expired:
            del self._used[n]

    def _evict_oldest(self) -> None:
        if not self._used:
            return
        oldest = min(self._used, key=self._used.get)  # type: ignore[arg-type]
        del self._used[oldest]


class DevIdentityProvider:
    """Identity provider for development and testing.

    Reads a signed handshake from the ``X-Identity-Handshake`` header,
    verifies the HMAC signature, checks expiration, and enforces nonce
    replay protection.

    For production, replace this with an ARCHEngine-backed provider that
    resolves identity from authenticated server context.
    """

    def __init__(
        self,
        secret: Optional[str] = None,
        *,
        nonce_ttl: int = 300,
        nonce_max_size: int = 10_000,
    ) -> None:
        if secret is None:
            secret = os.environ.get("CHIMERA_IDENTITY_SECRET")
            if secret is None:
                env = os.environ.get("CHIMERA_ENV", "development")
                if env == "production":
                    raise RuntimeError(
                        "CHIMERA_IDENTITY_SECRET must be set in production"
                    )
                secret = "chimera-dev-secret"
        self._secret = secret
        self._nonces = _NonceStore(max_size=nonce_max_size, ttl_seconds=nonce_ttl)

    async def resolve(self, request: Request) -> UserContext:
        """Extract and verify user identity from the request.

        Returns UserContext on success.
        Raises HTTPException(401) on any failure — never reveals why.
        """
        from fastapi import HTTPException

        header = request.headers.get("X-Identity-Handshake")
        if not header:
            raise HTTPException(status_code=401, detail="Missing identity handshake")

        try:
            handshake = decode_handshake(header)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid identity handshake")

        if not verify_handshake(self._secret, handshake):
            raise HTTPException(status_code=401, detail="Invalid identity handshake")

        if handshake.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Identity handshake expired")

        if self._nonces.is_used(handshake.nonce):
            raise HTTPException(status_code=401, detail="Identity handshake expired")

        self._nonces.mark_used(handshake.nonce)

        return UserContext(user_id=handshake.user_id)
