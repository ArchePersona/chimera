"""Tests for Assignment 008 — Persistence Layer."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

from app.repositories.storage import FilesystemStorage
from app.repositories.session_repository import SessionRepository
from app.repositories.cartridge_repository import CartridgeRepository
from app.interview.engine import InterviewEngine
from app.services.cartridge_service import (
    CartridgeService,
    CartridgeLifecycleMetadata,
    CartridgeNotFoundError,
    LifecycleState,
    _CartridgeRecord,
)
from app.models.cartridge import PersonaDraft, PersonaCartridge, CartridgeManifest
from app.services.forge import CartridgeForge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_draft(identifier="test-persona", name="Test"):
    return PersonaDraft(
        name=name,
        identifier=identifier,
        summary="S",
        core_values=["v"],
        motivations=["m"],
        strengths=["s"],
        limitations=["l"],
        goals=["g"],
        boundaries=["b"],
    )


def _make_record(identifier="test-persona", name="Test"):
    draft = _make_draft(identifier, name)
    result = CartridgeForge.forge(draft)
    assert result.success, f"Forge failed: {result.error}"
    return _CartridgeRecord(
        cartridge=result.cartridge,
        lifecycle=CartridgeLifecycleMetadata(lifecycle_state=LifecycleState.ACTIVE),
    )


@pytest.fixture
def td():
    """Create a temporary directory inside the workspace and clean up after."""
    d = Path(tempfile.mkdtemp(dir=str(Path(__file__).resolve().parent.parent)))
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ===========================================================================
# TestFilesystemStorage
# ===========================================================================

class TestFilesystemStorage:

    def test_write_and_read(self, td):
        storage = FilesystemStorage(td / "data")
        doc = {"hello": "world", "num": 42}
        storage.write("docs", "doc1", doc)
        result = storage.read("docs", "doc1")
        assert result == doc

    def test_read_nonexistent(self, td):
        storage = FilesystemStorage(td / "data")
        assert storage.read("docs", "missing") is None

    def test_delete_existing(self, td):
        storage = FilesystemStorage(td / "data")
        storage.write("docs", "doc1", {"a": 1})
        assert storage.delete("docs", "doc1") is True
        assert storage.read("docs", "doc1") is None

    def test_delete_nonexistent(self, td):
        storage = FilesystemStorage(td / "data")
        assert storage.delete("docs", "missing") is False

    def test_list_keys(self, td):
        storage = FilesystemStorage(td / "data")
        storage.write("docs", "alpha", {"a": 1})
        storage.write("docs", "gamma", {"g": 2})
        storage.write("docs", "beta", {"b": 3})
        keys = storage.list_keys("docs")
        assert keys == ["alpha", "beta", "gamma"]

    def test_list_keys_empty_domain(self, td):
        storage = FilesystemStorage(td / "data")
        assert storage.list_keys("empty") == []

    def test_exists(self, td):
        storage = FilesystemStorage(td / "data")
        assert storage.exists("docs", "doc1") is False
        storage.write("docs", "doc1", {"a": 1})
        assert storage.exists("docs", "doc1") is True
        storage.delete("docs", "doc1")
        assert storage.exists("docs", "doc1") is False

    def test_atomic_write(self, td):
        storage = FilesystemStorage(td / "data")
        storage.write("docs", "doc1", {"a": 1})
        expected = storage.root / "docs" / "doc1.json"
        assert expected.exists()
        tmp_file = storage.root / "docs" / "doc1.tmp"
        assert not tmp_file.exists()

    def test_read_write_index(self, td):
        storage = FilesystemStorage(td / "data")
        index = {"id-1": "alpha", "id-2": "beta"}
        storage.write_index("docs", index, "_uuid_index")
        result = storage.read_index("docs", "_uuid_index")
        assert result == index

    def test_nested_domain(self, td):
        storage = FilesystemStorage(td / "data")
        storage.write("a/b", "item1", {"x": 1})
        storage.write("a/b", "item2", {"x": 2})
        keys = storage.list_keys("a/b")
        assert sorted(keys) == ["item1", "item2"]


# ===========================================================================
# TestSessionRepository
# ===========================================================================

class TestSessionRepository:

    def _make_repo(self, td):
        storage = FilesystemStorage(td / "data")
        engine = InterviewEngine()
        return SessionRepository(storage, engine), engine

    def test_save_and_load(self, td):
        repo, engine = self._make_repo(td)
        session = engine.create_session()
        repo.save(session, "user-a")
        loaded = repo.load(session.session_id, "user-a")
        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert loaded.draft.name == session.draft.name

    def test_load_nonexistent(self, td):
        repo, engine = self._make_repo(td)
        assert repo.load("no-such-id", "user-a") is None

    def test_exists(self, td):
        repo, engine = self._make_repo(td)
        session = engine.create_session()
        assert repo.exists(session.session_id, "user-a") is False
        repo.save(session, "user-a")
        assert repo.exists(session.session_id, "user-a") is True

    def test_delete(self, td):
        repo, engine = self._make_repo(td)
        session = engine.create_session()
        repo.save(session, "user-a")
        repo.delete(session.session_id, "user-a")
        assert repo.exists(session.session_id, "user-a") is False
        assert repo.load(session.session_id, "user-a") is None

    def test_list_ids(self, td):
        repo, engine = self._make_repo(td)
        s1 = engine.create_session()
        s2 = engine.create_session()
        repo.save(s1, "user-a")
        repo.save(s2, "user-a")
        ids = repo.list_ids("user-a")
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_load_all(self, td):
        repo, engine = self._make_repo(td)
        s1 = engine.create_session()
        s2 = engine.create_session()
        repo.save(s1, "user-a")
        repo.save(s2, "user-a")
        all_sessions = repo.load_all("user-a")
        assert s1.session_id in all_sessions
        assert s2.session_id in all_sessions
        assert len(all_sessions) == 2

    def test_user_isolation(self, td):
        repo, engine = self._make_repo(td)
        session = engine.create_session()
        repo.save(session, "user-a")
        assert repo.load(session.session_id, "user-b") is None

    def test_persists_across_repos(self, td):
        storage = FilesystemStorage(td / "data")
        engine = InterviewEngine()

        repo1 = SessionRepository(storage, engine)
        session = engine.create_session()
        repo1.save(session, "user-a")

        repo2 = SessionRepository(storage, engine)
        loaded = repo2.load(session.session_id, "user-a")
        assert loaded is not None
        assert loaded.session_id == session.session_id


# ===========================================================================
# TestCartridgeRepository
# ===========================================================================

class TestCartridgeRepository:

    def _make_repo(self, td):
        storage = FilesystemStorage(td / "data")
        return CartridgeRepository(storage)

    def test_save_and_get(self, td):
        repo = self._make_repo(td)
        record = _make_record("alpha-persona", "Alpha")
        repo.save("alpha-persona", record, "user-a")
        got = repo.get("alpha-persona", "user-a")
        assert got.cartridge.identity.identifier == "alpha-persona"

    def test_get_nonexistent(self, td):
        repo = self._make_repo(td)
        with pytest.raises(CartridgeNotFoundError):
            repo.get("no-such", "user-a")

    def test_get_by_uuid(self, td):
        repo = self._make_repo(td)
        record = _make_record("beta-persona", "Beta")
        repo.save("beta-persona", record, "user-a")
        cartridge_id = record.cartridge.manifest.cartridge_id
        got = repo.get_by_uuid(cartridge_id, "user-a")
        assert got.cartridge.identity.identifier == "beta-persona"

    def test_exists(self, td):
        repo = self._make_repo(td)
        record = _make_record("gamma-persona", "Gamma")
        assert repo.exists("gamma-persona", "user-a") is False
        repo.save("gamma-persona", record, "user-a")
        assert repo.exists("gamma-persona", "user-a") is True

    def test_versions(self, td):
        repo = self._make_repo(td)
        r1 = _make_record("delta-persona", "Delta v1")
        repo.save("delta-persona", r1, "user-a")
        r2 = _make_record("delta-persona", "Delta v2")
        repo.save("delta-persona", r2, "user-a")
        vers = repo.versions("delta-persona", "user-a")
        assert len(vers) >= 2

    def test_list_all(self, td):
        repo = self._make_repo(td)
        r1 = _make_record("epsilon-1", "Eps1")
        r2 = _make_record("epsilon-2", "Eps2")
        repo.save("epsilon-1", r1, "user-a")
        repo.save("epsilon-2", r2, "user-a")
        result = repo.list_all("user-a")
        ids = [ident for ident, _ in result]
        assert "epsilon-1" in ids
        assert "epsilon-2" in ids

    def test_user_isolation(self, td):
        repo = self._make_repo(td)
        record = _make_record("zeta-persona", "Zeta")
        repo.save("zeta-persona", record, "user-a")
        with pytest.raises(CartridgeNotFoundError):
            repo.get("zeta-persona", "user-b")

    def test_persist_current(self, td):
        storage = FilesystemStorage(td / "data")
        repo1 = CartridgeRepository(storage)
        record = _make_record("eta-persona", "Eta")
        repo1.save("eta-persona", record, "user-a")

        record.lifecycle.lifecycle_state = LifecycleState.ARCHIVED
        repo1.persist_current("eta-persona", "user-a")

        repo2 = CartridgeRepository(storage)
        loaded = repo2.get("eta-persona", "user-a")
        assert loaded.lifecycle.lifecycle_state == LifecycleState.ARCHIVED

    def test_delete(self, td):
        repo = self._make_repo(td)
        record = _make_record("theta-persona", "Theta")
        repo.save("theta-persona", record, "user-a")
        repo.delete("theta-persona", "user-a")
        assert repo.exists("theta-persona", "user-a") is False


# ===========================================================================
# TestCartridgeServiceWithRepo
# ===========================================================================

class TestCartridgeServiceWithRepo:

    def _make_service(self, td):
        storage = FilesystemStorage(td / "data")
        repo = CartridgeRepository(storage)
        service = CartridgeService(repo=repo)
        return service, repo

    def test_create_and_get(self, td):
        service, _ = self._make_service(td)
        draft = _make_draft("created-persona", "Created Persona")
        result = service.create(draft, "user-a")
        assert result.success
        cartridge = service.get("created-persona", "user-a")
        assert cartridge.identity.identifier == "created-persona"

    def test_list_user_scoped(self, td):
        service, _ = self._make_service(td)
        service.create(_make_draft("persona-a", "A"), "user-a")
        service.create(_make_draft("persona-b", "B"), "user-b")
        listings = service.list("user-a")
        assert len(listings) == 1
        assert listings[0].identifier == "persona-a"

    def test_archive_and_restore(self, td):
        service, _ = self._make_service(td)
        service.create(_make_draft("arch-persona", "Arch"), "user-a")
        service.archive("arch-persona", "user-a")
        meta = service.get_lifecycle_metadata("arch-persona", "user-a")
        assert meta.lifecycle_state == LifecycleState.ARCHIVED
        assert meta.archived_at is not None
        service.restore("arch-persona", "user-a")
        meta = service.get_lifecycle_metadata("arch-persona", "user-a")
        assert meta.lifecycle_state == LifecycleState.ACTIVE
        assert meta.archived_at is None

    def test_delete(self, td):
        service, _ = self._make_service(td)
        service.create(_make_draft("del-persona", "Del"), "user-a")
        service.delete("del-persona", "user-a")
        with pytest.raises(CartridgeNotFoundError):
            service.get("del-persona", "user-a")

    def test_clone_preserves_owner(self, td):
        service, _ = self._make_service(td)
        service.create(_make_draft("orig-persona", "Orig"), "user-a")
        result = service.clone("orig-persona", "cloned-persona", "user-a")
        assert result.success
        cloned = service.get("cloned-persona", "user-a")
        assert cloned.identity.identifier == "cloned-persona"

    def test_versions_persist(self, td):
        service, _ = self._make_service(td)
        service.create(_make_draft("ver-persona", "Ver"), "user-a")
        versions = service.versions("ver-persona", "user-a")
        assert len(versions) == 1

    def test_update_metadata_persists(self, td):
        storage = FilesystemStorage(td / "data")
        repo = CartridgeRepository(storage)
        service = CartridgeService(repo=repo)

        service.create(_make_draft("meta-persona", "Meta"), "user-a")

        service.update_metadata("meta-persona", "user-a", tags=["important", "draft"], notes="needs review")

        service2 = CartridgeService(repo=CartridgeRepository(storage))
        meta = service2.get_lifecycle_metadata("meta-persona", "user-a")
        assert "important" in meta.tags
        assert "draft" in meta.tags
        assert meta.notes == "needs review"
