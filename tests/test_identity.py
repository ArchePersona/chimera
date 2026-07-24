"""Tests for Assignment 008 — Identity Infrastructure."""

import os
import tempfile
from pathlib import Path

import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from app.identity.contract import IdentityHandshake, UserContext
from app.identity.signing import (
    compute_signature,
    decode_handshake,
    encode_handshake,
    sign_handshake,
    verify_handshake,
)
from app.identity.dev_provider import DevIdentityProvider, _NonceStore
from app.repositories.storage import FilesystemStorage, _validate_component, _validate_domain


class MockRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


# ---------------------------------------------------------------------------
# Handshake Signing
# ---------------------------------------------------------------------------

class TestHandshakeSigning:
    def test_sign_handshake_returns_valid_handshake(self):
        hs = sign_handshake("s", "user-1")
        assert isinstance(hs, IdentityHandshake)
        assert hs.signature != ""
        assert hs.user_id == "user-1"
        assert hs.expires_at > datetime.now(timezone.utc)

    def test_verify_handshake_valid(self):
        hs = sign_handshake("s", "user-1")
        assert verify_handshake("s", hs) is True

    def test_verify_handshake_wrong_secret(self):
        hs = sign_handshake("a", "user-1")
        assert verify_handshake("b", hs) is False

    def test_verify_handshake_tampered_field(self):
        hs = sign_handshake("s", "user-1")
        tampered = IdentityHandshake(
            user_id="user-2",
            issued_at=hs.issued_at,
            expires_at=hs.expires_at,
            nonce=hs.nonce,
            environment=hs.environment,
            signature=hs.signature,
        )
        assert verify_handshake("s", tampered) is False

    def test_compute_signature_deterministic(self):
        hs = sign_handshake("s", "user-1")
        sig1 = compute_signature("s", hs)
        sig2 = compute_signature("s", hs)
        assert sig1 == sig2


# ---------------------------------------------------------------------------
# Handshake Codec
# ---------------------------------------------------------------------------

class TestHandshakeCodec:
    def test_encode_decode_round_trip(self):
        hs = sign_handshake("s", "user-1")
        token = encode_handshake(hs)
        decoded = decode_handshake(token)
        assert decoded.user_id == hs.user_id
        assert decoded.issued_at == hs.issued_at
        assert decoded.expires_at == hs.expires_at
        assert decoded.nonce == hs.nonce
        assert decoded.environment == hs.environment
        assert decoded.signature == hs.signature

    def test_decode_invalid_base64(self):
        with pytest.raises(Exception):
            decode_handshake("!!!not-base64!!!")

    def test_decode_invalid_json(self):
        import base64
        token = base64.urlsafe_b64encode(b"not json").decode("ascii")
        with pytest.raises(Exception):
            decode_handshake(token)


# ---------------------------------------------------------------------------
# Nonce Store
# ---------------------------------------------------------------------------

class TestNonceStore:
    def test_nonce_not_used_initially(self):
        store = _NonceStore()
        assert store.is_used("abc") is False

    def test_nonce_mark_used(self):
        store = _NonceStore()
        store.mark_used("abc")
        assert store.is_used("abc") is True

    def test_nonce_expiry(self):
        store = _NonceStore(ttl_seconds=0)
        store.mark_used("abc")
        # ttl_seconds=0 means expiry = monotonic_now, cleanup should evict
        import time
        time.sleep(0.01)
        assert store.is_used("abc") is False

    def test_nonce_eviction(self):
        store = _NonceStore(max_size=2)
        store.mark_used("a")
        store.mark_used("b")
        store.mark_used("c")
        assert store.is_used("a") is False
        assert store.is_used("b") is True
        assert store.is_used("c") is True


# ---------------------------------------------------------------------------
# Dev Identity Provider
# ---------------------------------------------------------------------------

class TestDevIdentityProvider:
    @pytest.mark.asyncio
    async def test_resolve_valid_handshake(self):
        secret = "test-secret"
        hs = sign_handshake(secret, "user-42")
        token = encode_handshake(hs)
        provider = DevIdentityProvider(secret=secret)
        req = MockRequest(headers={"X-Identity-Handshake": token})
        ctx = await provider.resolve(req)
        assert isinstance(ctx, UserContext)
        assert ctx.user_id == "user-42"

    @pytest.mark.asyncio
    async def test_resolve_missing_header(self):
        provider = DevIdentityProvider(secret="s")
        req = MockRequest()
        with pytest.raises(HTTPException) as exc_info:
            await provider.resolve(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_invalid_token(self):
        provider = DevIdentityProvider(secret="s")
        req = MockRequest(headers={"X-Identity-Handshake": "garbage"})
        with pytest.raises(HTTPException) as exc_info:
            await provider.resolve(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_expired_handshake(self):
        secret = "test-secret"
        hs = sign_handshake(secret, "user-42", ttl_seconds=-1)
        token = encode_handshake(hs)
        provider = DevIdentityProvider(secret=secret)
        req = MockRequest(headers={"X-Identity-Handshake": token})
        with pytest.raises(HTTPException) as exc_info:
            await provider.resolve(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_reused_nonce(self):
        secret = "test-secret"
        hs = sign_handshake(secret, "user-42")
        token = encode_handshake(hs)
        provider = DevIdentityProvider(secret=secret)
        req = MockRequest(headers={"X-Identity-Handshake": token})
        await provider.resolve(req)
        with pytest.raises(HTTPException) as exc_info:
            await provider.resolve(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_wrong_signature(self):
        hs = sign_handshake("wrong-secret", "user-42")
        token = encode_handshake(hs)
        provider = DevIdentityProvider(secret="correct-secret")
        req = MockRequest(headers={"X-Identity-Handshake": token})
        with pytest.raises(HTTPException) as exc_info:
            await provider.resolve(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_missing_secret(self):
        import os
        os.environ.pop("CHIMERA_IDENTITY_SECRET", None)
        os.environ["CHIMERA_ENV"] = "development"
        provider = DevIdentityProvider()
        hs = sign_handshake("chimera-dev-secret", "user-42")
        token = encode_handshake(hs)
        req = MockRequest(headers={"X-Identity-Handshake": token})
        ctx = await provider.resolve(req)
        assert ctx.user_id == "user-42"


# ---------------------------------------------------------------------------
# Path Traversal Prevention
# ---------------------------------------------------------------------------

class TestPathTraversalPrevention:
    def test_validate_component_valid(self):
        _validate_component("abc-123_def")

    def test_validate_component_dotdot(self):
        with pytest.raises(ValueError, match="\\'\\.\\.\\'"):
            _validate_component("..")

    def test_validate_component_slash(self):
        with pytest.raises(ValueError):
            _validate_component("a/b")

    def test_validate_component_backslash(self):
        with pytest.raises(ValueError):
            _validate_component("a\\b")

    def test_validate_component_special_chars(self):
        with pytest.raises(ValueError):
            _validate_component("a@b")

    def test_validate_domain_nested_valid(self):
        _validate_domain("sessions/user123")

    def test_validate_domain_dotdot(self):
        with pytest.raises(ValueError, match="\\.\\."):
            _validate_domain("sessions/../etc")

    def test_storage_write_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = FilesystemStorage(tmp)
            with pytest.raises(ValueError):
                storage.write("domain", "..", {"data": 1})

    def test_storage_read_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = FilesystemStorage(tmp)
            with pytest.raises(ValueError):
                storage.read("a/../b", "key")
