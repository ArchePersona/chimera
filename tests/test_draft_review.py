"""Tests for Assignment 004 — Interview API, Draft Review, and Forge Pipeline."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.main import app

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
    r = client.post("/api/sessions")
    assert r.status_code == 200
    return r.json()["session_id"]


def _answer_all_required(session_id: str) -> None:
    for qid, val in REQUIRED_ANSWERS:
        r = client.post(
            f"/api/sessions/{session_id}/answers",
            json={"question_id": qid, "value": val},
        )
        assert r.status_code == 200, f"Failed to answer {qid}: {r.text}"


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------


class TestSessionCreation:
    def test_create_session_returns_200(self):
        r = client.post("/api/sessions")
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data
        assert data["state"] == "created"

    def test_create_session_returns_progress(self):
        r = client.post("/api/sessions")
        data = r.json()
        assert "progress" in data
        assert data["progress"]["total_questions"] == 18
        assert data["progress"]["answered_questions"] == 0

    def test_create_session_with_template(self):
        template = {"name": "Test Persona", "identifier": "test-persona"}
        r = client.post("/api/sessions", json={"template": template})
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "created"


class TestGetSession:
    def test_get_session_returns_200(self):
        sid = _create_session()
        r = client.get(f"/api/sessions/{sid}")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == sid
        assert data["state"] == "created"
        assert data["ready_to_forge"] is False

    def test_get_session_not_found(self):
        r = client.get("/api/sessions/nonexistent-id")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Interview Operations
# ---------------------------------------------------------------------------


class TestGetQuestions:
    def test_get_questions_returns_available(self):
        sid = _create_session()
        r = client.get(f"/api/sessions/{sid}/questions")
        assert r.status_code == 200
        data = r.json()
        assert "available" in data
        assert "current" in data
        assert len(data["available"]) > 0
        assert data["current"]["identifier"] == "identity_name"

    def test_get_questions_not_found(self):
        r = client.get("/api/sessions/nonexistent/questions")
        assert r.status_code == 404


class TestSubmitAnswer:
    def test_submit_answer_accepted(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["accepted"] is True
        assert data["question_id"] == "identity_name"

    def test_submit_answer_updates_progress(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
        )
        progress = r.json()["progress"]
        assert progress["answered_questions"] == 1

    def test_submit_answer_transitions_to_in_progress(self):
        sid = _create_session()
        client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
        )
        r = client.get(f"/api/sessions/{sid}")
        assert r.json()["state"] == "in_progress"

    def test_submit_answer_not_found(self):
        r = client.post(
            "/api/sessions/nonexistent/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
        )
        assert r.status_code == 404

    def test_submit_answer_unavailable_question(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "character_core_values", "value": ["wisdom"]},
        )
        assert r.status_code == 409

    def test_submit_answer_invalid_value(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": ""},
        )
        assert r.status_code == 422

    def test_submit_answer_wrong_type(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": 123},
        )
        assert r.status_code == 422


class TestSkipQuestion:
    def test_skip_optional_question(self):
        sid = _create_session()
        # identity_description depends on identity_name being answered first
        client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
        )
        r = client.post(
            f"/api/sessions/{sid}/skip",
            json={"question_id": "identity_description"},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] is True

    def test_skip_required_question_fails(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/skip",
            json={"question_id": "identity_name"},
        )
        assert r.status_code == 422

    def test_skip_unavailable_question(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/skip",
            json={"question_id": "identity_description"},
        )
        assert r.status_code == 409


class TestCompleteSession:
    def test_complete_session(self):
        sid = _create_session()
        r = client.post(f"/api/sessions/{sid}/complete")
        assert r.status_code == 200
        assert r.json()["completed"] is True

    def test_complete_session_not_found(self):
        r = client.post("/api/sessions/nonexistent/complete")
        assert r.status_code == 404


class TestProgress:
    def test_progress_initial(self):
        sid = _create_session()
        r = client.get(f"/api/sessions/{sid}/progress")
        assert r.status_code == 200
        data = r.json()
        assert data["answered_questions"] == 0
        assert data["all_required_answered"] is False

    def test_progress_after_answers(self):
        sid = _create_session()
        client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
        )
        r = client.get(f"/api/sessions/{sid}/progress")
        data = r.json()
        assert data["answered_questions"] == 1


# ---------------------------------------------------------------------------
# Draft Review
# ---------------------------------------------------------------------------


class TestDraftReview:
    def test_get_draft_returns_200(self):
        sid = _create_session()
        client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
        )
        r = client.get(f"/api/sessions/{sid}/draft")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == sid
        assert data["draft"]["name"] == "Atlas"
        assert data["ready_to_forge"] is False

    def test_get_draft_not_found(self):
        r = client.get("/api/sessions/nonexistent/draft")
        assert r.status_code == 404

    def test_draft_includes_all_fields(self):
        sid = _create_session()
        r = client.get(f"/api/sessions/{sid}/draft")
        draft = r.json()["draft"]
        expected_fields = [
            "name", "identifier", "summary", "description", "aliases",
            "core_values", "motivations", "strengths", "limitations",
            "goals", "boundaries", "communication_style", "tone",
            "vocabulary_preferences", "response_tendencies",
            "formatting_preferences", "preferences", "behavior_rules",
        ]
        for field in expected_fields:
            assert field in draft, f"Missing draft field: {field}"

    def test_draft_readiness_issues_present(self):
        sid = _create_session()
        r = client.get(f"/api/sessions/{sid}/draft")
        data = r.json()
        assert "readiness_issues" in data
        assert len(data["readiness_issues"]) > 0


class TestValidateSessionDraft:
    def test_validate_empty_draft(self):
        sid = _create_session()
        r = client.post(f"/api/sessions/{sid}/validate")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_complete_draft(self):
        sid = _create_session()
        _answer_all_required(sid)
        r = client.post(f"/api/sessions/{sid}/validate")
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0

    def test_validate_not_found(self):
        r = client.post("/api/sessions/nonexistent/validate")
        assert r.status_code == 404

    def test_validate_warnings_not_blocking(self):
        sid = _create_session()
        _answer_all_required(sid)
        r = client.post(f"/api/sessions/{sid}/validate")
        data = r.json()
        # Warnings should not make valid=False
        assert data["valid"] is True


# ---------------------------------------------------------------------------
# Forge Pipeline (end-to-end)
# ---------------------------------------------------------------------------


class TestForgeSession:
    def test_forge_incomplete_session_rejected(self):
        sid = _create_session()
        client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "Atlas"},
        )
        r = client.post(f"/api/sessions/{sid}/forge")
        assert r.status_code == 409

    def test_forge_complete_session_succeeds(self):
        sid = _create_session()
        _answer_all_required(sid)
        r = client.post(f"/api/sessions/{sid}/forge")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "cartridge" in data
        assert data["session_preserved"] is True

    def test_forge_not_found(self):
        r = client.post("/api/sessions/nonexistent/forge")
        assert r.status_code == 404

    def test_session_preserved_after_forge(self):
        sid = _create_session()
        _answer_all_required(sid)
        client.post(f"/api/sessions/{sid}/forge")
        r = client.get(f"/api/sessions/{sid}")
        assert r.status_code == 200
        assert r.json()["state"] == "ready_to_forge"

    def test_draft_still_accessible_after_forge(self):
        sid = _create_session()
        _answer_all_required(sid)
        client.post(f"/api/sessions/{sid}/forge")
        r = client.get(f"/api/sessions/{sid}/draft")
        assert r.status_code == 200
        assert r.json()["draft"]["name"] == "Atlas"


# ---------------------------------------------------------------------------
# Draft Review Page Rendering
# ---------------------------------------------------------------------------


class TestDraftReviewPage:
    def test_draft_review_page_renders(self):
        r = client.get("/drafts/test-session-123/review")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_draft_review_page_has_required_elements(self):
        r = client.get("/drafts/test-session-123/review")
        html = r.text
        assert 'id="draft-sections"' in html
        assert 'id="btn-validate"' in html
        assert 'id="btn-forge"' in html
        assert 'id="review-status-bar"' in html
        assert 'id="badge-status"' in html
        assert 'id="badge-readiness"' in html

    def test_draft_review_page_has_session_id(self):
        r = client.get("/drafts/my-session-456/review")
        assert "my-session-456" in r.text

    def test_draft_review_page_has_base_path(self):
        r = client.get("/drafts/test/review")
        assert "/chimera" in r.text

    def test_draft_review_page_has_script_block(self):
        r = client.get("/drafts/test/review")
        assert "<script>" in r.text
        assert "loadDraft" in r.text
        assert "handleValidate" in r.text
        assert "handleForge" in r.text


# ---------------------------------------------------------------------------
# End-to-End Flow
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    def test_create_answer_review_validate_forge(self):
        # 1. Create session
        r = client.post("/api/sessions")
        sid = r.json()["session_id"]
        assert r.json()["state"] == "created"

        # 2. Answer all required questions
        _answer_all_required(sid)

        # 3. Verify readiness
        r = client.get(f"/api/sessions/{sid}")
        assert r.json()["ready_to_forge"] is True
        assert r.json()["state"] == "ready_to_forge"

        # 4. Review draft
        r = client.get(f"/api/sessions/{sid}/draft")
        assert r.json()["draft"]["name"] == "Atlas"
        assert r.json()["draft"]["identifier"] == "atlas"

        # 5. Validate
        r = client.post(f"/api/sessions/{sid}/validate")
        assert r.json()["valid"] is True

        # 6. Forge
        r = client.post(f"/api/sessions/{sid}/forge")
        assert r.json()["success"] is True
        assert r.json()["cartridge"]["identity"]["display_name"] == "Atlas"

        # 7. Session preserved
        r = client.get(f"/api/sessions/{sid}")
        assert r.json()["state"] == "ready_to_forge"

        # 8. Draft still accessible
        r = client.get(f"/api/sessions/{sid}/draft")
        assert r.json()["draft"]["name"] == "Atlas"


# ---------------------------------------------------------------------------
# API Error Responses (JSON format)
# ---------------------------------------------------------------------------


class TestApiErrorFormat:
    def test_404_returns_json(self):
        r = client.get("/api/sessions/nonexistent")
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/json")

    def test_409_returns_json(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "character_core_values", "value": ["wisdom"]},
        )
        assert r.status_code == 409
        assert r.headers["content-type"].startswith("application/json")

    def test_422_returns_json(self):
        sid = _create_session()
        r = client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": ""},
        )
        assert r.status_code == 422
        assert r.headers["content-type"].startswith("application/json")
