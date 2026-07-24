"""Assignment 006: Cartridge Inspector — API and template tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.interview.engine import InterviewEngine
from app.services.authoring_workflow import AuthoringWorkflow
from app.services.cartridge_service import CartridgeService, CartridgeNotFoundError


@pytest.fixture(autouse=True)
def _reset_workflow():
    engine = InterviewEngine()
    service = CartridgeService()
    app.state.workflow = AuthoringWorkflow(interview_engine=engine, cartridge_service=service)
    yield


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def cartridge_id(client) -> str:
    session = client.post("/api/sessions").json()["session_id"]
    answers = [
        ("identity_name", "Inspector Test Persona"),
        ("identity_identifier", "inspector-test-persona"),
        ("identity_summary", "A test persona for inspector"),
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
        })
    forge_resp = client.post(f"/api/sessions/{session}/forge")
    return forge_resp.json()["cartridge"]["manifest"]["cartridge_id"]


# ---------------------------------------------------------------------------
# API: GET /api/cartridges/{cartridge_id}
# ---------------------------------------------------------------------------

class TestGetCartridgeAPI:
    def test_returns_200(self, client, cartridge_id):
        resp = client.get(f"/api/cartridges/{cartridge_id}")
        assert resp.status_code == 200

    def test_returns_cartridge_dict(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}").json()
        assert "cartridge" in data
        assert data["cartridge"]["manifest"]["cartridge_id"] == cartridge_id

    def test_returns_lifecycle(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}").json()
        assert "lifecycle" in data
        assert data["lifecycle"]["state"] == "active"

    def test_returns_source(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}").json()
        assert "source" in data
        assert "has_source" in data["source"]

    def test_404_for_unknown_uuid(self, client):
        resp = client.get("/api/cartridges/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API: GET /api/cartridges/{cartridge_id}/validation
# ---------------------------------------------------------------------------

class TestGetCartridgeValidationAPI:
    def test_returns_200(self, client, cartridge_id):
        resp = client.get(f"/api/cartridges/{cartridge_id}/validation")
        assert resp.status_code == 200

    def test_valid_cartridge(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/validation").json()
        assert "valid" in data
        assert "errors" in data
        assert "specification" in data

    def test_specification_compliance(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/validation").json()
        assert data["specification"]["compliant"] is True

    def test_404_for_unknown(self, client):
        resp = client.get("/api/cartridges/00000000-0000-0000-0000-000000000000/validation")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API: GET /api/cartridges/{cartridge_id}/versions
# ---------------------------------------------------------------------------

class TestGetCartridgeVersionsAPI:
    def test_returns_200(self, client, cartridge_id):
        resp = client.get(f"/api/cartridges/{cartridge_id}/versions")
        assert resp.status_code == 200

    def test_single_version(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/versions").json()
        assert data["total_versions"] == 1
        assert data["versions"][0]["is_current"] is True

    def test_version_identifier(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/versions").json()
        assert data["identifier"] == "inspector-test-persona"

    def test_404_for_unknown(self, client):
        resp = client.get("/api/cartridges/00000000-0000-0000-0000-000000000000/versions")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API: GET /api/cartridges/{cartridge_id}/source
# ---------------------------------------------------------------------------

class TestGetCartridgeSourceAPI:
    def test_returns_200(self, client, cartridge_id):
        resp = client.get(f"/api/cartridges/{cartridge_id}/source")
        assert resp.status_code == 200

    def test_source_has_fields(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/source").json()
        assert "cartridge_id" in data
        assert "identifier" in data
        assert "source_session_id" in data
        assert "forged_at" in data
        assert "has_source" in data

    def test_source_session_id_present(self, client, cartridge_id):
        data = client.get(f"/api/cartridges/{cartridge_id}/source").json()
        assert data["has_source"] is True
        assert data["source_session_id"] is not None

    def test_404_for_unknown(self, client):
        resp = client.get("/api/cartridges/00000000-0000-0000-0000-000000000000/source")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Web: Inspector template
# ---------------------------------------------------------------------------

class TestInspectorTemplate:
    def test_returns_200(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert resp.status_code == 200

    def test_contains_cartridge_id(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert cartridge_id in resp.text

    def test_contains_data_attribute(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert f'data-cartridge-id="{cartridge_id}"' in resp.text

    def test_includes_tabs(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert 'role="tablist"' in resp.text
        assert 'data-tab="identity"' in resp.text
        assert 'data-tab="validation"' in resp.text
        assert 'data-tab="versions"' in resp.text
        assert 'data-tab="raw"' in resp.text

    def test_includes_inspector_js(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert "inspector.js" in resp.text

    def test_includes_skip_link(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert "Skip to main content" in resp.text

    def test_semantic_landmarks(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert 'role="banner"' in resp.text
        assert 'role="navigation"' in resp.text
        assert 'id="main-content"' in resp.text
        assert 'role="contentinfo"' in resp.text

    def test_panel_aria_controls(self, client, cartridge_id):
        resp = client.get(f"/cartridges/{cartridge_id}")
        assert 'aria-controls="panel-identity"' in resp.text
        assert 'aria-controls="panel-raw"' in resp.text


# ---------------------------------------------------------------------------
# Version history after second forge
# ---------------------------------------------------------------------------

class TestVersionHistory:
    def test_two_forges_two_versions(self, client):
        session = client.post("/api/sessions").json()["session_id"]
        answers = [
            ("identity_name", "Versioned Persona"),
            ("identity_identifier", "versioned-persona"),
            ("identity_summary", "Summary"),
            ("identity_description", "Desc"),
            ("character_core_values", ["loyalty"]),
            ("character_motivations", ["duty"]),
            ("character_strengths", ["bravery"]),
            ("character_limitations", ["stubborn"]),
            ("character_goals", ["serve"]),
            ("character_boundaries", ["honor"]),
            ("communication_communication_style", "formal"),
            ("communication_tone", ["serious"]),
            ("communication_vocabulary_preferences", ["precise"]),
            ("communication_response_tendencies", ["analyze"]),
            ("communication_formatting_preferences", ["paragraphs"]),
            ("behavior_rules", ["always be honorable"]),
        ]
        for qid, val in answers:
            client.post(f"/api/sessions/{session}/answers", json={
                "question_id": qid, "value": val
            })
        r1 = client.post(f"/api/sessions/{session}/forge")
        assert r1.status_code == 200
        uuid1 = r1.json()["cartridge"]["manifest"]["cartridge_id"]

        r2 = client.post(f"/api/sessions/{session}/forge")
        assert r2.status_code == 200
        uuid2 = r2.json()["cartridge"]["manifest"]["cartridge_id"]

        assert uuid1 != uuid2

        versions = client.get(f"/api/cartridges/{uuid1}/versions").json()
        assert versions["total_versions"] == 2
        assert versions["versions"][0]["cartridge_id"] == uuid1
        assert versions["versions"][0]["is_current"] is False
        assert versions["versions"][1]["cartridge_id"] == uuid2
        assert versions["versions"][1]["is_current"] is True

        v2 = client.get(f"/api/cartridges/{uuid2}/versions").json()
        assert v2["versions"][1]["is_current"] is True
