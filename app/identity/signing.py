"""HMAC-SHA256 signing and verification for identity handshakes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.identity.contract import IdentityHandshake


def _canonical_payload(handshake: IdentityHandshake) -> bytes:
    """Produce the canonical byte payload that the signature covers.

    The signature covers every field *except* the signature itself.
    Deterministic JSON encoding ensures reproducibility.
    """
    payload = {
        "user_id": handshake.user_id,
        "issued_at": handshake.issued_at.isoformat(),
        "expires_at": handshake.expires_at.isoformat(),
        "nonce": handshake.nonce,
        "environment": handshake.environment,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_signature(secret: str, handshake: IdentityHandshake) -> str:
    """Compute the HMAC-SHA256 signature for a handshake."""
    mac = hmac.new(
        secret.encode("utf-8"),
        _canonical_payload(handshake),
        hashlib.sha256,
    )
    return base64.urlsafe_b64encode(mac.digest()).decode("ascii")


def sign_handshake(
    secret: str,
    user_id: str,
    *,
    ttl_seconds: int = 3600,
    environment: str = "dev",
) -> IdentityHandshake:
    """Create a signed IdentityHandshake.

    The returned handshake's signature field is already computed and valid.
    """
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=ttl_seconds)
    nonce = secrets.token_urlsafe(16)

    unsigned = IdentityHandshake(
        user_id=user_id,
        issued_at=now,
        expires_at=expires,
        nonce=nonce,
        environment=environment,
        signature="",
    )
    sig = compute_signature(secret, unsigned)
    return IdentityHandshake(
        user_id=unsigned.user_id,
        issued_at=unsigned.issued_at,
        expires_at=unsigned.expires_at,
        nonce=unsigned.nonce,
        environment=unsigned.environment,
        signature=sig,
    )


def verify_handshake(
    secret: str,
    handshake: IdentityHandshake,
) -> bool:
    """Verify a handshake's signature.

    Returns True if the signature is valid.
    Expiration and nonce checks are the caller's responsibility
    (the provider handles those).
    """
    expected = compute_signature(secret, handshake)
    return hmac.compare_digest(handshake.signature, expected)


def encode_handshake(handshake: IdentityHandshake) -> str:
    """Encode a handshake to a base64 URL-safe string for HTTP transport."""
    raw = json.dumps(handshake.to_dict()).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_handshake(token: str) -> IdentityHandshake:
    """Decode a base64 URL-safe string back to an IdentityHandshake."""
    raw = base64.urlsafe_b64decode(token.encode("ascii"))
    data = json.loads(raw)
    return IdentityHandshake.from_dict(data)
