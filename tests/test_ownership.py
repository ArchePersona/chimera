"""Tests for Assignment 008 — User Ownership Isolation."""

import pytest
import shutil
from pathlib import Path

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.identity.signing import sign_handshake, encode_handshake
from app.repositories.storage import FilesystemStorage
from app.repositories.session_repository import SessionRepository
from app.repositories.cartridge_repository import CartridgeRepository
from app.interview.engine import InterviewEngine
from app.services.authoring_workflow import AuthoringWorkflow
from app.services.cartridge_service import CartridgeService, CartridgeNotFoundError
from app.main import app


def _user_headers(user_id: str):
    """Generate a fresh auth header for the given user_id."""
    token = encode_handshake(sign_handshake("chimera-dev-secret", user_id))
    return {"X-Identity-Handshake": token}


def _minimal_draft(name: str, identifier: str):
    """Create a minimal valid PersonaDraft."""
    PersonaDraft = __import__("app.models.cartridge", fromlist=["PersonaDraft"]).PersonaDraft
    return PersonaDraft(
        name=name,
        identifier=identifier,
        summary=f"Summary of {name}",
        core_values=["v1"],
        motivations=["m1"],
        strengths=["s1"],
        limitations=["l1"],
        goals=["g1"],
        boundaries=["b1"],
    )


USER_A = "user-alice"
USER_B = "user-bob"


@pytest.fixture(autouse=True)
def _fresh_workflow(tmp_path_factory):
    """Create a fresh workflow with filesystem persistence for each test."""
    tmp = Path("D:\\CHIMERA\\.pytest_ownership")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(exist_ok=True)
    storage = FilesystemStorage(tmp)
    engine = InterviewEngine()
    session_repo = SessionRepository(storage, engine)
    cartridge_repo = CartridgeRepository(storage)
    cartridge_svc = CartridgeService(repo=cartridge_repo)
    workflow = AuthoringWorkflow(
        interview_engine=engine,
        cartridge_service=cartridge_svc,
        session_repo=session_repo,
    )
    app.state.workflow = workflow
    yield
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


REQUIRED_ANSWERS = [
    ("identity_name", "Name"),
    ("identity_identifier", "name"),
    ("identity_summary", "Summary"),
    ("character_core_values", ["value1"]),
    ("character_motivations", ["motivation1"]),
    ("character_strengths", ["strength1"]),
    ("character_limitations", ["limitation1"]),
    ("character_goals", ["goal1"]),
    ("character_boundaries", ["boundary1"]),
]


def _create_session(client, user_id):
    r = client.post("/api/sessions", headers=_user_headers(user_id))
    return r.json()["session_id"]


def _answer_all(client, session_id, user_id):
    for qid, val in REQUIRED_ANSWERS:
        client.post(
            f"/api/sessions/{session_id}/answers",
            json={"question_id": qid, "value": val},
            headers=_user_headers(user_id),
        )


def _forge_session(client, session_id, user_id):
    _answer_all(client, session_id, user_id)
    r = client.post(
        f"/api/sessions/{session_id}/forge", headers=_user_headers(user_id)
    )
    return r.status_code, r.json()


# ---------------------------------------------------------------------------
# Session isolation
# ---------------------------------------------------------------------------

class TestSessionIsolation:
    def test_two_users_separate_sessions(self, client):
        r1 = client.post("/api/sessions", headers=_user_headers(USER_A))
        r2 = client.post("/api/sessions", headers=_user_headers(USER_B))
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["session_id"] != r2.json()["session_id"]

    def test_user_cannot_access_other_session(self, client):
        sid = _create_session(client, USER_A)
        r = client.get(f"/api/sessions/{sid}", headers=_user_headers(USER_B))
        assert r.status_code == 404

    def test_user_cannot_access_other_draft(self, client):
        sid = _create_session(client, USER_A)
        r = client.get(f"/api/sessions/{sid}/draft", headers=_user_headers(USER_B))
        assert r.status_code == 404

    def test_user_cannot_answer_other_session(self, client):
        sid = _create_session(client, USER_A)
        r = client.post(
            f"/api/sessions/{sid}/answers",
            json={"question_id": "identity_name", "value": "X"},
            headers=_user_headers(USER_B),
        )
        assert r.status_code == 404

    def test_user_cannot_forge_other_session(self, client):
        sid = _create_session(client, USER_A)
        r = client.post(f"/api/sessions/{sid}/forge", headers=_user_headers(USER_B))
        assert r.status_code == 404

    def test_user_cannot_skip_other_session(self, client):
        sid = _create_session(client, USER_A)
        r = client.post(
            f"/api/sessions/{sid}/skip",
            json={"question_id": "identity_description"},
            headers=_user_headers(USER_B),
        )
        assert r.status_code == 404

    def test_user_cannot_complete_other_session(self, client):
        sid = _create_session(client, USER_A)
        r = client.post(f"/api/sessions/{sid}/complete", headers=_user_headers(USER_B))
        assert r.status_code == 404

    def test_user_cannot_get_progress_other_session(self, client):
        sid = _create_session(client, USER_A)
        r = client.get(f"/api/sessions/{sid}/progress", headers=_user_headers(USER_B))
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Cartridge isolation
# ---------------------------------------------------------------------------

class TestCartridgeIsolation:
    def test_user_cannot_inspect_other_cartridge(self, client):
        h_b = _user_headers(USER_B)
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        uuid = data["cartridge"]["manifest"]["cartridge_id"]
        r = client.get(f"/api/cartridges/{uuid}", headers=h_b)
        assert r.status_code == 404

    def test_user_cannot_export_other_cartridge(self, client):
        h_b = _user_headers(USER_B)
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        uuid = data["cartridge"]["manifest"]["cartridge_id"]
        r = client.get(f"/api/cartridges/{uuid}/export", headers=h_b)
        assert r.status_code == 404

    def test_user_cannot_view_other_versions(self, client):
        h_b = _user_headers(USER_B)
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        uuid = data["cartridge"]["manifest"]["cartridge_id"]
        r = client.get(f"/api/cartridges/{uuid}/versions", headers=h_b)
        assert r.status_code == 404

    def test_user_cannot_view_other_source(self, client):
        h_b = _user_headers(USER_B)
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        uuid = data["cartridge"]["manifest"]["cartridge_id"]
        r = client.get(f"/api/cartridges/{uuid}/source", headers=h_b)
        assert r.status_code == 404

    def test_user_cannot_validate_other_cartridge(self, client):
        h_b = _user_headers(USER_B)
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        uuid = data["cartridge"]["manifest"]["cartridge_id"]
        r = client.get(f"/api/cartridges/{uuid}/validation", headers=h_b)
        assert r.status_code == 404

    def test_user_can_access_own_cartridge(self, client):
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        uuid = data["cartridge"]["manifest"]["cartridge_id"]
        r = client.get(f"/api/cartridges/{uuid}", headers=_user_headers(USER_A))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Ownership preservation through forge
# ---------------------------------------------------------------------------

class TestForgePreservesOwnership:
    def test_forge_cartridge_accessible_by_owner(self, client):
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        assert data["success"] is True
        uuid = data["cartridge"]["manifest"]["cartridge_id"]
        r = client.get(f"/api/cartridges/{uuid}", headers=_user_headers(USER_A))
        assert r.status_code == 200

    def test_forge_cartridge_inaccessible_by_other(self, client):
        h_b = _user_headers(USER_B)
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        uuid = data["cartridge"]["manifest"]["cartridge_id"]
        r = client.get(f"/api/cartridges/{uuid}", headers=h_b)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Clone preserves ownership
# ---------------------------------------------------------------------------

class TestClonePreservesOwnership:
    def test_clone_stays_under_owner(self):
        svc = app.state.workflow._cartridge_service
        draft = _minimal_draft("Clone Test", "clone-test")
        svc.create(draft, owner_user_id=USER_A)
        svc.clone("clone-test", "clone-test-2", owner_user_id=USER_A)
        assert svc.get("clone-test-2", USER_A) is not None
        with pytest.raises(CartridgeNotFoundError):
            svc.get("clone-test-2", USER_B)

    def test_clone_source_accessible_by_owner(self):
        svc = app.state.workflow._cartridge_service
        draft = _minimal_draft("Src Test", "src-test")
        svc.create(draft, owner_user_id=USER_A)
        svc.clone("src-test", "src-test-clone", owner_user_id=USER_A)
        assert svc.get("src-test", USER_A) is not None


# ---------------------------------------------------------------------------
# Ownership survives restart (cache clear)
# ---------------------------------------------------------------------------

class TestOwnershipSurvival:
    def test_ownership_survives_cache_clear(self, client):
        h_b = _user_headers(USER_B)
        sid = _create_session(client, USER_A)
        status, data = _forge_session(client, sid, USER_A)
        assert status == 200, f"Forge failed: {data}"
        uuid = data["cartridge"]["manifest"]["cartridge_id"]

        app.state.workflow._session_repo.clear_cache()
        app.state.workflow._cartridge_service._repo.clear_cache()

        r = client.get(f"/api/cartridges/{uuid}", headers=_user_headers(USER_A))
        assert r.status_code == 200
        r = client.get(f"/api/cartridges/{uuid}", headers=h_b)
        assert r.status_code == 404

    def test_sessions_survive_cache_clear(self, client):
        sid = _create_session(client, USER_A)

        app.state.workflow._session_repo.clear_cache()

        r = client.get(f"/api/sessions/{sid}", headers=_user_headers(USER_A))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Dashboard isolation
# ---------------------------------------------------------------------------

class TestDashboardIsolation:
    def test_list_only_own_cartridges(self):
        svc = app.state.workflow._cartridge_service
        for i in range(2):
            draft = _minimal_draft(f"A-{i}", f"a-{i}")
            svc.create(draft, owner_user_id=USER_A)
        draft = _minimal_draft("B-0", "b-0")
        svc.create(draft, owner_user_id=USER_B)

        list_a = svc.list(owner_user_id=USER_A)
        list_b = svc.list(owner_user_id=USER_B)
        assert len(list_a) == 2
        assert len(list_b) == 1
        assert all(s.identifier.startswith("a-") for s in list_a)
        assert list_b[0].identifier == "b-0"
