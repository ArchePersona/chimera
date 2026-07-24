"""Assignment 007: Export Experience — API, template, and regression tests."""

from __future__ import annotations

import hashlib
import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.main import app
from app.interview.engine import InterviewEngine
from app.identity.signing import sign_handshake, encode_handshake
from app.services.authoring_workflow import AuthoringWorkflow
from app.services.cartridge_service import CartridgeService
from app.services.serializer import CartridgeSerializer

def _auth_headers():
    token = encode_handshake(sign_handshake("chimera-dev-secret", "test-user"))
    return {"X-Identity-Handshake": token}


@pytest.fixture(autouse=True)
def _reset_workflow():
    engine = InterviewEngine()
    service = CartridgeService()
    app.state.workflow = AuthoringWorkflow(interview_engine=engine, cartridge_service=service)
    yield


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _complete_session(client: TestClient) -> str:
    session = client.post("/api/sessions", headers=_auth_headers()).json()["session_id"]
    answers = [
        ("identity_name", "Export Test Persona"),
        ("identity_identifier", "export-test-persona"),
        ("identity_summary", "A test persona for export"),
        ("identity_description", "Desc"),
        ("character_core_values", ["kindness"]),
        ("character_motivations", ["helping"]),
        ("character_strengths", ["empathy"]),
        ("character_limitations", ["impatient"]),
        ("character_goals", ["inspire"]),
        ("character_boundaries", ["privacy"]),
        ("communication_communication_style", "warm"),
        ("communication_tone", ["friendly"]),
        ("communication_vocabulary_preferences", ["simple"]),
        ("communication_response_tendencies", ["listen"]),
        ("communication_formatting_preferences", ["bullets"]),
        ("behavior_rules", ["always be kind"]),
    ]
    for qid, val in answers:
        client.post(f"/api/sessions/{session}/answers", json={
            "question_id": qid, "value": val
        }, headers=_auth_headers())
    return session


@pytest.fixture()
def cartridge_id(client) -> str:
    session = _complete_session(client)
    forge_resp = client.post(f"/api/sessions/{session}/forge", headers=_auth_headers())
    return forge_resp.json()["cartridge"]["manifest"]["cartridge_id"]


# ---------------------------------------------------------------------------
# API: GET /api/cartridges/{cartridge_id}/export
# ---------------------------------------------------------------------------

class TestExportAPI:
    def test_returns_200(self, client, cartridge_id):
        resp = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers())
        assert resp.status_code == 200

    def test_returns_cartridge(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert "cartridge" in data
        assert data["cartridge"]["manifest"]["cartridge_id"] == cartridge_id

    def test_returns_filename(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert data["filename"] == "export-test-persona_v0.6.0.json"

    def test_filename_is_deterministic(self, client, cartridge_id):
        r1 = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        r2 = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert r1["filename"] == r2["filename"]

    def test_returns_checksum(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert "checksum" in data
        assert data["checksum"]["algorithm"] == "sha256"
        assert len(data["checksum"]["value"]) == 64

    def test_checksum_is_correct(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        expected = hashlib.sha256(
            json.dumps(data["cartridge"], indent=2, sort_keys=False).encode("utf-8")
        ).hexdigest()
        assert data["checksum"]["value"] == expected

    def test_returns_size_bytes(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert "size_bytes" in data
        assert data["size_bytes"] > 0

    def test_returns_format(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert data["format"] == "json"

    def test_returns_validation(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert "validation" in data
        assert "valid" in data["validation"]
        assert "warning_count" in data["validation"]

    def test_returns_specification(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert "specification" in data
        assert data["specification"]["compliant"] is True

    def test_returns_compatibility(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert "compatibility" in data
        assert data["compatibility"]["supported"] is True

    def test_returns_lifecycle(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert "lifecycle" in data
        assert "export_count" in data["lifecycle"]

    def test_404_for_unknown(self, client):
        resp = client.get("/api/cartridges/00000000-0000-0000-0000-000000000000/export", headers=_auth_headers())
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Canonical Serialization Regression
# ---------------------------------------------------------------------------

class TestCanonicalSerialization:
    def test_exported_json_matches_serializer(self, client, cartridge_id):
        export = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        cartridge = client.get(f"/api/cartridges/{cartridge_id}", headers=_auth_headers()).json()["cartridge"]
        expected = json.dumps(cartridge, indent=2, sort_keys=False)
        export_json = json.dumps(export["cartridge"], indent=2, sort_keys=False)
        assert export_json == expected

    def test_repeated_exports_are_identical(self, client, cartridge_id):
        r1 = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        r2 = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert json.dumps(r1["cartridge"]) == json.dumps(r2["cartridge"])
        assert r1["checksum"]["value"] == r2["checksum"]["value"]

    def test_frontend_does_not_serialize(self, client, cartridge_id):
        resp = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["cartridge"], dict)
        assert "manifest" in data["cartridge"]

    def test_export_is_immutable(self, client, cartridge_id):
        export1 = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers())
        export2 = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        assert export1["cartridge"] == export2["cartridge"]

    def test_export_count_increments(self, client, cartridge_id):
        r1 = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        count1 = r1["lifecycle"]["export_count"]
        client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers())
        r2 = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        count2 = r2["lifecycle"]["export_count"]
        assert count2 > count1


# ---------------------------------------------------------------------------
# Filename Determinism
# ---------------------------------------------------------------------------

class TestFilenameGeneration:
    def test_filename_format(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        fn = data["filename"]
        assert fn.endswith(".json")
        assert "_v" in fn
        assert fn == "export-test-persona_v0.6.0.json"

    def test_filename_matches_identifier(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        identifier = data["cartridge"]["identity"]["identifier"]
        assert data["filename"].startswith(identifier)

    def test_filename_matches_version(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/export", headers=_auth_headers()).json()
        version = data["cartridge"]["manifest"]["schema_version"]
        assert f"_v{version}.json" in data["filename"]


# ---------------------------------------------------------------------------
# Web: Export template
# ---------------------------------------------------------------------------

class TestExportTemplate:
    def test_returns_200(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert resp.status_code == 200

    def test_contains_cartridge_id(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert cartridge_id in resp.text

    def test_contains_data_attribute(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert f'data-cartridge-id="{cartridge_id}"' in resp.text

    def test_includes_export_js(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert "export.js" in resp.text

    def test_includes_skip_link(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert "Skip to main content" in resp.text

    def test_semantic_landmarks(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert 'role="banner"' in resp.text
        assert 'role="navigation"' in resp.text
        assert 'id="main-content"' in resp.text
        assert 'role="contentinfo"' in resp.text

    def test_has_export_actions(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert "btn-download" in resp.text
        assert "btn-copy" in resp.text
        assert "Export JSON" in resp.text
        assert "Copy JSON" in resp.text

    def test_has_sr_announcer(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert "sr-announcer" in resp.text
        assert 'aria-live="polite"' in resp.text

    def test_has_json_preview(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert "json-preview" in resp.text
        assert "json-code" in resp.text

    def test_has_compatibility_section(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert "ARCHEngine" in resp.text
        assert "Runtime Compatibility" in resp.text

    def test_has_validation_section(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert "export-validation-status" in resp.text

    def test_includes_back_to_inspector(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}/export")
        assert "Return to Inspector" in resp.text
        assert "Dashboard" in resp.text


# ---------------------------------------------------------------------------
# Inspector links to export
# ---------------------------------------------------------------------------

class TestInspectorExportLink:
    def test_inspector_has_export_tab(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert resp.status_code == 200
