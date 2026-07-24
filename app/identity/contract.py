"""Identity contract — minimal user context and handshake token."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class UserContext:
    """Verified user identity for request-scoped ownership.

    CHIMERA consumes only these fields.  Authentication, credential
    management, and account lifecycle are external responsibilities.
    """

    user_id: str
    account_id: str | None = None
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentityHandshake:
    """Signed token carrying a verified user identity.

    The signature covers all other fields.  The verifier checks:
      1. HMAC-SHA256 signature matches
      2. expires_at > now
      3. nonce has not been used before (replay protection)
    """

    user_id: str
    issued_at: datetime
    expires_at: datetime
    nonce: str
    environment: str  # "dev" | "staging" | "production"
    signature: str

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "nonce": self.nonce,
            "environment": self.environment,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> IdentityHandshake:
        return cls(
            user_id=data["user_id"],
            issued_at=datetime.fromisoformat(data["issued_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            nonce=data["nonce"],
            environment=data["environment"],
            signature=data["signature"],
        )
