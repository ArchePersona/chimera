"""CHIMERA Studio identity infrastructure.

Provides pluggable user identity resolution for request-scoped ownership.
CHIMERA never implements authentication — it consumes a verified identity
from an IdentityProvider supplied at startup.
"""

from app.identity.contract import IdentityHandshake, UserContext
from app.identity.dependencies import get_current_user
from app.identity.signing import sign_handshake, verify_handshake

__all__ = [
    "IdentityHandshake",
    "UserContext",
    "get_current_user",
    "sign_handshake",
    "verify_handshake",
]
