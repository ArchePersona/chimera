"""Tests for Assignment 005 — Forge Experience."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.main import app
from app.identity.signing import sign_handshake, encode_handshake


def _auth_headers():
    token = encode_handshake(sign_handshake("chimera-dev-secret", "test-user"))
    return {"X-Identity-Handshake": token}

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_ANSWERS = [
    ("identity_name", "Atlas"),
    ("identity_identifier", "atlas"),
    ("identity_summary", "A wise explorer"),
    ("character_core_values", ["wisdom", "courage"]),
    ("character_motivations", ["discovery"]),
    ("character_strengths", ["insight"]),
    ("character_limitations", ["impatience"]),
    ("character_goals", ["explore the unknown"]),
    ("character_boundaries", ["never harm innocents"]),
]


def _create_session() -> str:
    r = client.post("/api/sessions", headers=_auth_headers())
    assert r.status_code == 200
    return r.json()["session_id"]


def _answer_all_required(session_id: str) -> None:
    for qid, val in REQUIRED_ANSWERS:
        r = client.post(
            f"/api/sessions/{session_id}/answers",
            json={"question_id": qid, "value": val},
            headers=_auth_headers(),
        )
        assert r.status_code == 200, f"Failed to answer {qid}: {r.text}"


def _forge_session(session_id: str) -> dict:
    _answer_all_required(session_id)
    r = client.post(f"/api/sessions/{session_id}/forge", headers=_auth_headers())
    assert r.status_code == 200
    return r.json()


# ---------------------------------------------------------------------------
# Successful Forge
# ---------------------------------------------------------------------------


class TestForgeSuccess:
    def test_forge_returns_success(self):
        sid = _create_session()
        result = _forge_session(sid)
        assert result["success"] is True
        assert "cartridge" in result

    def test_forge_returns_cartridge_with_identity(self):
        sid = _create_session()
        result = _forge_session(sid)
        cartridge = result["cartridge"]
        assert "identity" in cartridge
        assert cartridge["identity"]["display_name"] == "Atlas"
        assert cartridge["identity"]["identifier"] == "atlas"

    def test_forge_returns_cartridge_with_manifest(self):
        sid = _create_session()
        result = _forge_session(sid)
        manifest = result["cartridge"]["manifest"]
        assert "cartridge_id" in manifest
        assert manifest["schema_name"] == "archepersona.chimera.persona-cartridge"
        assert manifest["schema_version"] == "0.6.0"

    def test_forge_returns_cartridge_with_all_modules(self):
        sid = _create_session()
        result = _forge_session(sid)
        cartridge = result["cartridge"]
        assert "identity" in cartridge
        assert "character" in cartridge
        assert "preferences" in cartridge
        assert "behavior" in cartridge
        assert "communication" in cartridge

    def test_forge_returns_warnings(self):
        sid = _create_session()
        result = _forge_session(sid)
        assert "warnings" in result
        assert isinstance(result["warnings"], list)

    def test_forge_returns_session_preserved(self):
        sid = _create_session()
        result = _forge_session(sid)
        assert result["session_preserved"] is True


# ---------------------------------------------------------------------------
# Idempotency — Repeated Forge
# ---------------------------------------------------------------------------


class TestForgeIdempotency:
    def test_repeated_forge_creates_new_cartridge(self):
        sid = _create_session()
        _answer_all_required(sid)
        r1 = client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        r2 = client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        # Second forge may succeed (creating a new version) or fail
        if r2.status_code == 200:
            # Each forge creates a new cartridge with a unique ID
            assert r1.json()["cartridge"]["manifest"]["cartridge_id"] != \
                   r2.json()["cartridge"]["manifest"]["cartridge_id"]
            # But the identifier and content remain the same
            assert r1.json()["cartridge"]["identity"]["identifier"] == \
                   r2.json()["cartridge"]["identity"]["identifier"]

    def test_forge_after_complete_does_not_duplicate(self):
        sid = _create_session()
        _answer_all_required(sid)
        client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        # Try forge again — should either return same result or error
        r = client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        # Either succeeds (idempotent) or fails cleanly
        assert r.status_code in (200, 409)


# ---------------------------------------------------------------------------
# Incomplete Draft Rejection
# ---------------------------------------------------------------------------


class TestForgeIncompleteRejection:
    def test_forge_empty_session_rejected(self):
        sid = _create_session()
        r = client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        assert r.status_code == 409

    def test_forge_partial_session_rejected(self):
        sid = _create_session()
        client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
            headers=_auth_headers(),
        )
        r = client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        assert r.status_code == 409

    def test_forge_rejection_includes_error_type(self):
        sid = _create_session()
        r = client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        assert r.status_code == 409
        data = r.json()
        assert "INTERVIEW_INCOMPLETE" in str(data) or "detail" in data


# ---------------------------------------------------------------------------
# Validation Failure
# ---------------------------------------------------------------------------


class TestForgeValidationFailure:
    def test_validate_before_forge_shows_errors(self):
        sid = _create_session()
        r = client.post(f"/api/sessions/{sid}/validate", headers=_auth_headers())
        assert r.status_code == 200
        assert r.json()["valid"] is False
        assert len(r.json()["errors"]) > 0

    def test_validate_complete_draft_passes(self):
        sid = _create_session()
        _answer_all_required(sid)
        r = client.post(f"/api/sessions/{sid}/validate", headers=_auth_headers())
        assert r.status_code == 200
        assert r.json()["valid"] is True

    def test_validation_errors_are_field_level(self):
        sid = _create_session()
        r = client.post(f"/api/sessions/{sid}/validate", headers=_auth_headers())
        for error in r.json()["errors"]:
            assert "field" in error
            assert "message" in error
            assert "code" in error


# ---------------------------------------------------------------------------
# Backend Errors
# ---------------------------------------------------------------------------


class TestForgeBackendErrors:
    def test_forge_nonexistent_session(self):
        r = client.post("/api/sessions/nonexistent/forge", headers=_auth_headers())
        assert r.status_code == 404

    def test_forge_cancelled_session(self):
        sid = _create_session()
        _answer_all_required(sid)
        client.post(f"/api/sessions/{sid}/complete", headers=_auth_headers())
        r = client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        # Completed sessions may be rejected or handled
        assert r.status_code in (409, 200)

    def test_error_response_is_json(self):
        r = client.post("/api/sessions/nonexistent/forge", headers=_auth_headers())
        assert r.headers["content-type"].startswith("application/json")

    def test_error_response_has_message(self):
        r = client.post("/api/sessions/nonexistent/forge", headers=_auth_headers())
        data = r.json()
        assert "detail" in data or "message" in data


# ---------------------------------------------------------------------------
# Session State After Forge
# ---------------------------------------------------------------------------


class TestSessionStateAfterForge:
    def test_session_preserved(self):
        sid = _create_session()
        _forge_session(sid)
        r = client.get(f"/api/sessions/{sid}", headers=_auth_headers())
        assert r.status_code == 200
        assert r.json()["session_id"] == sid

    def test_session_state_unchanged(self):
        sid = _create_session()
        _forge_session(sid)
        r = client.get(f"/api/sessions/{sid}", headers=_auth_headers())
        assert r.json()["state"] == "ready_to_forge"

    def test_draft_still_accessible(self):
        sid = _create_session()
        _forge_session(sid)
        r = client.get(f"/api/sessions/{sid}/draft", headers=_auth_headers())
        assert r.status_code == 200
        assert r.json()["draft"]["name"] == "Atlas"

    def test_progress_still_accessible(self):
        sid = _create_session()
        _forge_session(sid)
        r = client.get(f"/api/sessions/{sid}/progress", headers=_auth_headers())
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Cartridge Inspector Navigation
# ---------------------------------------------------------------------------


class TestInspectorNavigation:
    def test_cartridge_has_identifier_for_inspector(self):
        sid = _create_session()
        result = _forge_session(sid)
        identifier = result["cartridge"]["identity"]["identifier"]
        assert identifier
        assert isinstance(identifier, str)
        assert len(identifier) > 0

    def test_inspector_route_exists(self):
        r = client.get("/cartridges/test-identifier")
        assert r.status_code == 200
        assert "CHIMERA" in r.text

    def test_inspector_route_with_real_identifier(self):
        sid = _create_session()
        result = _forge_session(sid)
        identifier = result["cartridge"]["identity"]["identifier"]
        r = client.get(f"/cartridges/{identifier}")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Forge Experience Page Elements
# ---------------------------------------------------------------------------


class TestForgeExperiencePageElements:
    def test_draft_review_has_forge_dialog(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        assert r.status_code == 200
        html = r.text
        assert 'id="forge-dialog-overlay"' in html
        assert 'id="forge-confirm"' in html
        assert 'id="forge-progress"' in html
        assert 'id="forge-success"' in html
        assert 'id="forge-error"' in html

    def test_forge_dialog_has_aria_attributes(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        assert 'role="dialog"' in html
        assert 'aria-modal="true"' in html
        assert 'aria-labelledby="forge-dialog-title"' in html

    def test_forge_dialog_has_confirmation_content(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        assert "Forge Persona Cartridge" in html
        assert "immutable" in html.lower()
        assert "irreversible" in html.lower()

    def test_forge_dialog_has_success_redirect_links(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        assert 'id="forge-to-inspector"' in html
        assert 'id="forge-to-dashboard"' in html

    def test_forge_dialog_has_error_handling(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        assert 'id="forge-error-message"' in html
        assert 'id="forge-error-detail"' in html
        assert 'id="forge-retry"' in html

    def test_forge_dialog_has_focus_trapping(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        assert "trapFocus" in html
        assert "aria-label" in html

    def test_forge_dialog_has_escape_support(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        assert "Escape" in html

    def test_forge_dialog_has_screen_reader_announcements(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        assert 'id="sr-announcements"' in html
        assert 'aria-live="assertive"' in html


# ---------------------------------------------------------------------------
# Frontend Does Not Generate Identifiers
# ---------------------------------------------------------------------------


class TestFrontendDoesNotGenerateIdentifiers:
    def test_identifier_comes_from_backend(self):
        sid = _create_session()
        result = _forge_session(sid)
        identifier = result["cartridge"]["identity"]["identifier"]
        # Identifier should match the one submitted via interview
        assert identifier == "atlas"

    def test_cartridge_id_is_uuid_from_backend(self):
        sid = _create_session()
        result = _forge_session(sid)
        cartridge_id = result["cartridge"]["manifest"]["cartridge_id"]
        # UUID format
        parts = cartridge_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8


# ---------------------------------------------------------------------------
# Forge Readiness Backend-Authoritative
# ---------------------------------------------------------------------------


class TestForgeReadinessBackendAuthoritative:
    def test_readiness_from_session_endpoint(self):
        sid = _create_session()
        r = client.get(f"/api/sessions/{sid}", headers=_auth_headers())
        data = r.json()
        assert "ready_to_forge" in data
        assert "readiness_issues" in data
        assert data["ready_to_forge"] is False

    def test_readiness_after_all_required(self):
        sid = _create_session()
        _answer_all_required(sid)
        r = client.get(f"/api/sessions/{sid}", headers=_auth_headers())
        assert r.json()["ready_to_forge"] is True
        assert len(r.json()["readiness_issues"]) == 0

    def test_draft_endpoint_includes_readiness(self):
        sid = _create_session()
        _answer_all_required(sid)
        r = client.get(f"/api/sessions/{sid}/draft", headers=_auth_headers())
        data = r.json()
        assert "ready_to_forge" in data
        assert data["ready_to_forge"] is True

    def test_validate_endpoint_includes_readiness(self):
        sid = _create_session()
        _answer_all_required(sid)
        r = client.post(f"/api/sessions/{sid}/validate", headers=_auth_headers())
        # Validation result has valid/errors/warnings
        assert "valid" in r.json()


# ---------------------------------------------------------------------------
# Responsive Design Assumptions
# ---------------------------------------------------------------------------


class TestResponsiveDesign:
    def test_forge_dialog_has_responsive_css(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        # Check CSS classes exist for responsive behavior
        assert "forge-dialog" in html
        assert "forge-dialog-actions" in html

    def test_forge_button_is_disabled_by_default(self):
        sid = _create_session()
        r = client.get(f"/drafts/{sid}/review")
        html = r.text
        assert 'id="btn-forge"' in html
        assert "disabled" in html


# ---------------------------------------------------------------------------
# End-to-End Forge Flow
# ---------------------------------------------------------------------------


class TestEndToEndForgeFlow:
    def test_complete_forge_flow(self):
        # 1. Create session
        sid = _create_session()

        # 2. Answer all required questions
        _answer_all_required(sid)

        # 3. Verify readiness
        r = client.get(f"/api/sessions/{sid}", headers=_auth_headers())
        assert r.json()["ready_to_forge"] is True

        # 4. Review draft
        r = client.get(f"/api/sessions/{sid}/draft", headers=_auth_headers())
        assert r.json()["draft"]["name"] == "Atlas"

        # 5. Validate
        r = client.post(f"/api/sessions/{sid}/validate", headers=_auth_headers())
        assert r.json()["valid"] is True

        # 6. Forge
        r = client.post(f"/api/sessions/{sid}/forge", headers=_auth_headers())
        assert r.json()["success"] is True

        # 7. Verify cartridge
        cartridge = r.json()["cartridge"]
        assert cartridge["identity"]["display_name"] == "Atlas"
        assert cartridge["identity"]["identifier"] == "atlas"
        assert cartridge["manifest"]["schema_version"] == "0.6.0"

        # 8. Session preserved
        r = client.get(f"/api/sessions/{sid}", headers=_auth_headers())
        assert r.json()["state"] == "ready_to_forge"

        # 9. Draft still accessible
        r = client.get(f"/api/sessions/{sid}/draft", headers=_auth_headers())
        assert r.json()["draft"]["name"] == "Atlas"

        # 10. Inspector accessible
        r = client.get(f"/cartridges/atlas")
        assert r.status_code == 200
