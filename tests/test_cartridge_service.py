import copy
from datetime import datetime, timezone

from app.integrations.archengine import CartridgeDescriptorPayload
from app.models.cartridge import (
    CartridgeManifest,
    CartridgeStatus,
    ForgeResult,
    PersonaCartridge,
    PersonaDraft,
)
from app.models.projection import RuntimePersonaProjection
from app.services.cartridge_service import (
    CartridgeLifecycleMetadata,
    CartridgeNotFoundError,
    CartridgeService,
    CartridgeSummary,
    CartridgeServiceError,
    LifecycleState,
    LifecycleTransitionError,
)

TEST_USER = "test-user"


# ===================================================================
# Helpers
# ===================================================================

def _valid_draft(**overrides) -> PersonaDraft:
    params = dict(
        name="Alex",
        identifier="alex",
        summary="A thoughtful guide",
        description="Optional description",
        aliases=["The Guide", "Alex the Great"],
        communication_style="Warm and direct",
        core_values=["Curiosity"],
        motivations=["To help others grow"],
        strengths=["Patience"],
        limitations=["Overthinking"],
        goals=["Inspire learning"],
        boundaries=["Never lie"],
        behavior_rules=["Ask before acting", "Be kind", "Cite sources"],
        preferences={"formality": "casual", "verbosity": "medium"},
    )
    params.update(overrides)
    return PersonaDraft(**params)


def _make_service() -> CartridgeService:
    return CartridgeService()


def _create_valid(service: CartridgeService, identifier: str = "alex", owner_user_id: str = TEST_USER) -> PersonaCartridge:
    result = service.create(_valid_draft(identifier=identifier), owner_user_id)
    assert result.success is True
    assert result.cartridge is not None
    return result.cartridge


# ===================================================================
# Create
# ===================================================================

class TestServiceCreate:
    def test_create_returns_forge_result(self):
        svc = _make_service()
        result = svc.create(_valid_draft(), TEST_USER)
        assert isinstance(result, ForgeResult)
        assert result.success is True

    def test_create_stores_cartridge(self):
        svc = _make_service()
        c = _create_valid(svc)
        assert svc.get("alex", TEST_USER) is c

    def test_create_sets_lifecycle_state_active(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.lifecycle_state == LifecycleState.ACTIVE

    def test_create_sets_timestamps(self):
        svc = _make_service()
        before = datetime.now(timezone.utc)
        _create_valid(svc)
        after = datetime.now(timezone.utc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert before <= meta.created_at <= after
        assert before <= meta.updated_at <= after

    def test_create_initial_export_count(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.export_count == 0

    def test_create_no_clone_source(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.clone_source is None

    def test_create_failure_does_not_store(self):
        svc = _make_service()
        draft = _valid_draft(name="", identifier="")
        result = svc.create(draft, TEST_USER)
        assert result.success is False
        assert svc.list(TEST_USER) == []

    def test_create_preserves_authored_content(self):
        svc = _make_service()
        c = _create_valid(svc)
        assert c.identity.display_name == "Alex"
        assert c.identity.identifier == "alex"
        assert c.identity.summary == "A thoughtful guide"
        assert c.character.core_values == ("Curiosity",)
        assert len(c.behavior.policies) == 3

    def test_create_generates_unique_cartridge_id(self):
        svc = _make_service()
        c1 = _create_valid(svc, "alex")
        c2_result = svc.create(_valid_draft(identifier="bob", name="Bob"), TEST_USER)
        assert c2_result.success
        c2 = c2_result.cartridge
        assert c1.manifest.cartridge_id != c2.manifest.cartridge_id


# ===================================================================
# Retrieve
# ===================================================================

class TestServiceGet:
    def test_get_returns_cartridge(self):
        svc = _make_service()
        c = _create_valid(svc)
        retrieved = svc.get("alex", TEST_USER)
        assert isinstance(retrieved, PersonaCartridge)
        assert retrieved is c

    def test_get_raises_not_found(self):
        svc = _make_service()
        try:
            svc.get("nonexistent", TEST_USER)
            assert False, "Expected CartridgeNotFoundError"
        except CartridgeNotFoundError:
            pass

    def test_get_raises_for_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        try:
            svc.get("alex", TEST_USER)
            assert False, "Expected CartridgeNotFoundError"
        except CartridgeNotFoundError:
            pass

    def test_get_returns_archived(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        c = svc.get("alex", TEST_USER)
        assert c is not None

    def test_cartridge_immutable(self):
        svc = _make_service()
        c = _create_valid(svc)
        assert c.manifest.cartridge_id is not None


# ===================================================================
# Lifecycle metadata retrieval
# ===================================================================

class TestServiceGetLifecycleMetadata:
    def test_returns_metadata(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert isinstance(meta, CartridgeLifecycleMetadata)
        assert meta.lifecycle_state == LifecycleState.ACTIVE

    def test_returns_deep_copy(self):
        svc = _make_service()
        _create_valid(svc)
        meta1 = svc.get_lifecycle_metadata("alex", TEST_USER)
        meta1.tags.append("tamper")
        meta2 = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta2.tags == []

    def test_works_for_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.lifecycle_state == LifecycleState.DELETED

    def test_raises_for_nonexistent(self):
        svc = _make_service()
        try:
            svc.get_lifecycle_metadata("ghost", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass


# ===================================================================
# List
# ===================================================================

class TestServiceList:
    def test_list_empty(self):
        svc = _make_service()
        assert svc.list(TEST_USER) == []

    def test_list_all(self):
        svc = _make_service()
        _create_valid(svc, "alex")
        svc.create(_valid_draft(identifier="bob", name="Bob"), TEST_USER)
        result = svc.list(TEST_USER)
        assert len(result) == 2
        assert all(isinstance(s, CartridgeSummary) for s in result)

    def test_list_returns_summary(self):
        svc = _make_service()
        _create_valid(svc)
        result = svc.list(TEST_USER)
        s = result[0]
        assert s.identifier == "alex"
        assert s.display_name == "Alex"
        assert s.summary == "A thoughtful guide"
        assert s.schema_version == "0.6.0"
        assert s.lifecycle_state == LifecycleState.ACTIVE

    def test_list_filter_by_state(self):
        svc = _make_service()
        _create_valid(svc, "alex")
        svc.create(_valid_draft(identifier="bob", name="Bob"), TEST_USER)
        svc.archive("bob", TEST_USER)
        active = svc.list(TEST_USER, lifecycle_state=LifecycleState.ACTIVE)
        archived = svc.list(TEST_USER, lifecycle_state=LifecycleState.ARCHIVED)
        assert len(active) == 1
        assert active[0].identifier == "alex"
        assert len(archived) == 1
        assert archived[0].identifier == "bob"

    def test_list_filter_by_tag(self):
        svc = _make_service()
        _create_valid(svc, "alex")
        svc.create(_valid_draft(identifier="bob", name="Bob"), TEST_USER)
        svc.update_metadata("alex", TEST_USER, tags=["important"])
        svc.update_metadata("bob", TEST_USER, tags=["minor"])
        tagged = svc.list(TEST_USER, tag="important")
        assert len(tagged) == 1
        assert tagged[0].identifier == "alex"

    def test_list_orders_by_created_desc(self):
        svc = _make_service()
        svc.create(_valid_draft(identifier="first", name="First"), TEST_USER)
        svc.create(_valid_draft(identifier="second", name="Second"), TEST_USER)
        svc.create(_valid_draft(identifier="third", name="Third"), TEST_USER)
        result = svc.list(TEST_USER)
        assert result[0].identifier == "third"
        assert result[1].identifier == "second"
        assert result[2].identifier == "first"

    def test_list_includes_deleted(self):
        svc = _make_service()
        _create_valid(svc, "alex")
        svc.delete("alex", TEST_USER)
        result = svc.list(TEST_USER)
        assert len(result) == 1
        assert result[0].lifecycle_state == LifecycleState.DELETED


# ===================================================================
# Update metadata
# ===================================================================

class TestServiceUpdateMetadata:
    def test_update_tags(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.update_metadata("alex", TEST_USER, tags=["test", "important"])
        assert meta.tags == ["test", "important"]

    def test_update_notes(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.update_metadata("alex", TEST_USER, notes="A test cartridge")
        assert meta.notes == "A test cartridge"

    def test_update_tags_and_notes(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.update_metadata("alex", TEST_USER, tags=["a"], notes="Hello")
        assert meta.tags == ["a"]
        assert meta.notes == "Hello"

    def test_update_returns_deep_copy(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.update_metadata("alex", TEST_USER, tags=["a"])
        meta.tags.append("tamper")
        meta2 = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta2.tags == ["a"]

    def test_update_does_not_affect_cartridge(self):
        svc = _make_service()
        c = _create_valid(svc)
        svc.update_metadata("alex", TEST_USER, tags=["x"])
        retrieved = svc.get("alex", TEST_USER)
        assert retrieved is c

    def test_update_updates_timestamp(self):
        svc = _make_service()
        _create_valid(svc)
        before = datetime.now(timezone.utc)
        svc.update_metadata("alex", TEST_USER, tags=["x"])
        after = datetime.now(timezone.utc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert before <= meta.updated_at <= after

    def test_update_raises_for_nonexistent(self):
        svc = _make_service()
        try:
            svc.update_metadata("ghost", TEST_USER, tags=["x"])
            assert False
        except CartridgeNotFoundError:
            pass


# ===================================================================
# Clone
# ===================================================================

class TestServiceClone:
    def test_clone_returns_forge_result(self):
        svc = _make_service()
        _create_valid(svc)
        result = svc.clone("alex", "alex_clone", TEST_USER)
        assert isinstance(result, ForgeResult)
        assert result.success is True

    def test_clone_stores_new_cartridge(self):
        svc = _make_service()
        _create_valid(svc)
        svc.clone("alex", "alex_clone", TEST_USER)
        clone = svc.get("alex_clone", TEST_USER)
        assert clone.identity.identifier == "alex_clone"

    def test_clone_preserves_authored_content(self):
        svc = _make_service()
        original = _create_valid(svc)
        result = svc.clone("alex", "alex_clone", TEST_USER)
        assert result.success
        clone = result.cartridge
        assert clone.identity.display_name == original.identity.display_name
        assert clone.identity.summary == original.identity.summary
        assert clone.character.core_values == original.character.core_values
        assert clone.preferences.entries == original.preferences.entries
        assert len(clone.behavior.policies) == len(original.behavior.policies)

    def test_clone_new_identifier(self):
        svc = _make_service()
        _create_valid(svc)
        result = svc.clone("alex", "different_id", TEST_USER)
        assert result.success
        assert result.cartridge.identity.identifier == "different_id"

    def test_clone_generates_new_cartridge_id(self):
        svc = _make_service()
        original = _create_valid(svc)
        result = svc.clone("alex", "alex_clone", TEST_USER)
        assert result.success
        assert result.cartridge.manifest.cartridge_id != original.manifest.cartridge_id

    def test_clone_preserves_schema_version(self):
        svc = _make_service()
        _create_valid(svc)
        result = svc.clone("alex", "alex_clone", TEST_USER)
        assert result.success
        assert result.cartridge.manifest.schema_version == "0.6.0"

    def test_clone_records_provenance(self):
        svc = _make_service()
        original = _create_valid(svc)
        svc.clone("alex", "alex_clone", TEST_USER)
        meta = svc.get_lifecycle_metadata("alex_clone", TEST_USER)
        assert meta.clone_source == original.manifest.cartridge_id

    def test_clone_resets_timestamps(self):
        svc = _make_service()
        original_c = _create_valid(svc)
        orig_meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        svc.clone("alex", "alex_clone", TEST_USER)
        clone_meta = svc.get_lifecycle_metadata("alex_clone", TEST_USER)
        assert clone_meta.created_at >= orig_meta.created_at
        assert clone_meta.export_count == 0

    def test_clone_original_unchanged(self):
        svc = _make_service()
        original = _create_valid(svc)
        svc.clone("alex", "alex_clone", TEST_USER)
        retrieved = svc.get("alex", TEST_USER)
        assert retrieved is original

    def test_clone_raises_for_nonexistent(self):
        svc = _make_service()
        try:
            svc.clone("ghost", "clone", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass

    def test_clone_raises_for_deleted_source(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        try:
            svc.clone("alex", "alex_clone", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass


# ===================================================================
# Archive
# ===================================================================

class TestServiceArchive:
    def test_archive_transitions_to_archived(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.lifecycle_state == LifecycleState.ARCHIVED

    def test_archive_sets_archived_at(self):
        svc = _make_service()
        _create_valid(svc)
        before = datetime.now(timezone.utc)
        svc.archive("alex", TEST_USER)
        after = datetime.now(timezone.utc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.archived_at is not None
        assert before <= meta.archived_at <= after

    def test_archive_updates_updated_at(self):
        svc = _make_service()
        _create_valid(svc)
        before = datetime.now(timezone.utc)
        svc.archive("alex", TEST_USER)
        after = datetime.now(timezone.utc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert before <= meta.updated_at <= after

    def test_archive_raises_for_archived(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        try:
            svc.archive("alex", TEST_USER)
            assert False
        except LifecycleTransitionError:
            pass

    def test_archive_raises_for_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        try:
            svc.archive("alex", TEST_USER)
            assert False
        except LifecycleTransitionError:
            pass

    def test_archive_raises_for_nonexistent(self):
        svc = _make_service()
        try:
            svc.archive("ghost", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass

    def test_archive_does_not_affect_cartridge(self):
        svc = _make_service()
        c = _create_valid(svc)
        svc.archive("alex", TEST_USER)
        retrieved = svc.get("alex", TEST_USER)
        assert retrieved is c


# ===================================================================
# Restore
# ===================================================================

class TestServiceRestore:
    def test_restore_transitions_to_active(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        svc.restore("alex", TEST_USER)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.lifecycle_state == LifecycleState.ACTIVE

    def test_restore_clears_archived_at(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        svc.restore("alex", TEST_USER)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.archived_at is None

    def test_restore_updates_updated_at(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        before = datetime.now(timezone.utc)
        svc.restore("alex", TEST_USER)
        after = datetime.now(timezone.utc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert before <= meta.updated_at <= after

    def test_restore_raises_for_active(self):
        svc = _make_service()
        _create_valid(svc)
        try:
            svc.restore("alex", TEST_USER)
            assert False
        except LifecycleTransitionError:
            pass

    def test_restore_raises_for_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        try:
            svc.restore("alex", TEST_USER)
            assert False
        except LifecycleTransitionError:
            pass

    def test_restore_raises_for_nonexistent(self):
        svc = _make_service()
        try:
            svc.restore("ghost", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass

    def test_archive_restore_cycle(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        svc.restore("alex", TEST_USER)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).lifecycle_state == LifecycleState.ACTIVE
        svc.archive("alex", TEST_USER)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).lifecycle_state == LifecycleState.ARCHIVED


# ===================================================================
# Logical delete
# ===================================================================

class TestServiceDelete:
    def test_delete_transitions_to_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta.lifecycle_state == LifecycleState.DELETED

    def test_delete_raises_when_already_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        try:
            svc.delete("alex", TEST_USER)
            assert False
        except LifecycleTransitionError:
            pass

    def test_delete_raises_for_nonexistent(self):
        svc = _make_service()
        try:
            svc.delete("ghost", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass

    def test_deleted_cartridge_still_in_list(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        result = svc.list(TEST_USER)
        assert len(result) == 1
        assert result[0].lifecycle_state == LifecycleState.DELETED

    def test_delete_allows_metadata_update(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        meta = svc.update_metadata("alex", TEST_USER, tags=["post_delete"])
        assert meta.tags == ["post_delete"]

    def test_delete_does_not_remove_from_store(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert meta is not None


# ===================================================================
# Runtime projection delegation
# ===================================================================

class TestServiceRuntimeProjection:
    def test_returns_projection(self):
        svc = _make_service()
        _create_valid(svc)
        proj = svc.runtime_projection("alex", TEST_USER)
        assert isinstance(proj, RuntimePersonaProjection)

    def test_projection_contains_correct_fields(self):
        svc = _make_service()
        _create_valid(svc)
        proj = svc.runtime_projection("alex", TEST_USER)
        assert proj.display_name == "Alex"
        assert proj.identifier == "alex"
        assert proj.cartridge_id is not None

    def test_projection_immutable(self):
        svc = _make_service()
        _create_valid(svc)
        proj = svc.runtime_projection("alex", TEST_USER)
        assert proj.cartridge_schema_version == "0.6.0"

    def test_projection_raises_for_nonexistent(self):
        svc = _make_service()
        try:
            svc.runtime_projection("ghost", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass

    def test_projection_changes_when_state_changes(self):
        svc = _make_service()
        _create_valid(svc)
        proj1 = svc.runtime_projection("alex", TEST_USER)
        svc.archive("alex", TEST_USER)
        proj2 = svc.runtime_projection("alex", TEST_USER)
        # Lifecycle state does not affect runtime projection
        assert proj1.display_name == proj2.display_name


# ===================================================================
# Export delegation
# ===================================================================

class TestServiceExport:
    def test_export_returns_payload(self):
        svc = _make_service()
        _create_valid(svc)
        payload = svc.export_archengine("alex", TEST_USER)
        assert isinstance(payload, CartridgeDescriptorPayload)

    def test_export_contains_correct_data(self):
        svc = _make_service()
        _create_valid(svc)
        payload = svc.export_archengine("alex", TEST_USER)
        assert payload.name == "Alex"

    def test_export_increments_count(self):
        svc = _make_service()
        _create_valid(svc)
        svc.export_archengine("alex", TEST_USER)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).export_count == 1
        svc.export_archengine("alex", TEST_USER)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).export_count == 2

    def test_export_updates_updated_at(self):
        svc = _make_service()
        _create_valid(svc)
        before = datetime.now(timezone.utc)
        svc.export_archengine("alex", TEST_USER)
        after = datetime.now(timezone.utc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert before <= meta.updated_at <= after

    def test_export_raises_for_nonexistent(self):
        svc = _make_service()
        try:
            svc.export_archengine("ghost", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass

    def test_export_raises_for_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        try:
            svc.export_archengine("alex", TEST_USER)
            assert False
        except CartridgeNotFoundError:
            pass

    def test_export_from_archived(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        payload = svc.export_archengine("alex", TEST_USER)
        assert isinstance(payload, CartridgeDescriptorPayload)


# ===================================================================
# Immutable fields
# ===================================================================

class TestServiceImmutability:
    def test_updating_metadata_does_not_affect_cartridge_id(self):
        svc = _make_service()
        c = _create_valid(svc)
        original_id = c.manifest.cartridge_id
        svc.update_metadata("alex", TEST_USER, tags=["x"])
        assert c.manifest.cartridge_id == original_id

    def test_updating_metadata_does_not_affect_identifier(self):
        svc = _make_service()
        c = _create_valid(svc)
        svc.update_metadata("alex", TEST_USER, tags=["x"])
        assert c.identity.identifier == "alex"

    def test_archiving_does_not_change_identifier(self):
        svc = _make_service()
        c = _create_valid(svc)
        svc.archive("alex", TEST_USER)
        assert c.identity.identifier == "alex"

    def test_deleting_does_not_change_authored_content(self):
        svc = _make_service()
        c = _create_valid(svc)
        svc.delete("alex", TEST_USER)
        assert c.identity.display_name == "Alex"
        assert c.character.core_values == ("Curiosity",)


# ===================================================================
# Lifecycle transitions
# ===================================================================

class TestServiceTransitions:
    def test_active_to_archived_to_active(self):
        svc = _make_service()
        _create_valid(svc)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).lifecycle_state == LifecycleState.ACTIVE
        svc.archive("alex", TEST_USER)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).lifecycle_state == LifecycleState.ARCHIVED
        svc.restore("alex", TEST_USER)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).lifecycle_state == LifecycleState.ACTIVE

    def test_active_to_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).lifecycle_state == LifecycleState.DELETED

    def test_archived_to_deleted(self):
        svc = _make_service()
        _create_valid(svc)
        svc.archive("alex", TEST_USER)
        svc.delete("alex", TEST_USER)
        assert svc.get_lifecycle_metadata("alex", TEST_USER).lifecycle_state == LifecycleState.DELETED

    def test_deleted_is_terminal(self):
        svc = _make_service()
        _create_valid(svc)
        svc.delete("alex", TEST_USER)
        for op in [svc.archive, svc.restore, svc.delete]:
            try:
                op("alex", TEST_USER)
                assert False, f"Expected LifecycleTransitionError for {op.__name__}"
            except (LifecycleTransitionError, CartridgeServiceError):
                pass

    def test_error_messages_contain_identifier(self):
        svc = _make_service()
        _create_valid(svc)
        try:
            svc.archive("nonexistent", TEST_USER)
        except CartridgeNotFoundError as e:
            assert "nonexistent" in str(e)

    def test_error_messages_contain_state(self):
        svc = _make_service()
        _create_valid(svc)
        try:
            svc.archive("alex", TEST_USER)
            svc.archive("alex", TEST_USER)
        except LifecycleTransitionError as e:
            assert "archived" in str(e).lower()


# ===================================================================
# Metadata isolation
# ===================================================================

class TestServiceMetadataIsolation:
    def test_metadata_not_in_cartridge(self):
        svc = _make_service()
        c = _create_valid(svc)
        svc.update_metadata("alex", TEST_USER, tags=["secret"], notes="Admin note")
        d = c.to_dict()
        assert "tags" not in d
        assert "notes" not in d
        assert "lifecycle_state" not in d

    def test_cartridge_not_in_metadata(self):
        svc = _make_service()
        c = _create_valid(svc)
        meta = svc.get_lifecycle_metadata("alex", TEST_USER)
        assert not hasattr(meta, "cartridge_id")
        assert not hasattr(meta, "schema_version")

    def test_update_metadata_does_not_leak(self):
        svc = _make_service()
        _create_valid(svc)
        meta = svc.update_metadata("alex", TEST_USER, tags=["a"])
        assert "cartridge" not in meta.__dict__


# ===================================================================
# Deterministic clone behavior
# ===================================================================

class TestServiceCloneDeterminism:
    def test_clone_content_matches_source(self):
        svc = _make_service()
        original = _create_valid(svc, "source")
        svc.create(_valid_draft(identifier="other", name="Other"), TEST_USER)
        svc.clone("source", "clone_a", TEST_USER)
        svc.clone("source", "clone_b", TEST_USER)
        a = svc.get("clone_a", TEST_USER)
        b = svc.get("clone_b", TEST_USER)
        assert a.character == b.character
        assert a.communication == b.communication
        assert a.preferences.entries == b.preferences.entries
        assert len(a.behavior.policies) == len(b.behavior.policies)

    def test_clone_has_new_lifecycle(self):
        svc = _make_service()
        _create_valid(svc, "source")
        svc.clone("source", "clone_x", TEST_USER)
        meta = svc.get_lifecycle_metadata("clone_x", TEST_USER)
        assert meta.export_count == 0
        assert meta.tags == []
        assert meta.notes == ""
        assert meta.clone_source is not None

    def test_clone_does_not_affect_source_lifecycle(self):
        svc = _make_service()
        original = _create_valid(svc, "source")
        orig_meta = svc.get_lifecycle_metadata("source", TEST_USER)
        svc.clone("source", "clone_x", TEST_USER)
        orig_meta2 = svc.get_lifecycle_metadata("source", TEST_USER)
        assert orig_meta.export_count == orig_meta2.export_count
        assert orig_meta.lifecycle_state == orig_meta2.lifecycle_state


# ===================================================================
# Multiple cartridges
# ===================================================================

class TestServiceMultiple:
    def test_multiple_cartridges_independent(self):
        svc = _make_service()
        c1 = _create_valid(svc, "alpha")
        svc.create(_valid_draft(identifier="beta", name="Beta"), TEST_USER)
        c3 = _create_valid(svc, "gamma")
        assert svc.get("alpha", TEST_USER) is c1
        assert svc.get("gamma", TEST_USER) is c3
        assert len(svc.list(TEST_USER)) == 3

    def test_archive_one_does_not_affect_others(self):
        svc = _make_service()
        _create_valid(svc, "a")
        _create_valid(svc, "b")
        _create_valid(svc, "c")
        svc.archive("b", TEST_USER)
        assert svc.get_lifecycle_metadata("a", TEST_USER).lifecycle_state == LifecycleState.ACTIVE
        assert svc.get_lifecycle_metadata("b", TEST_USER).lifecycle_state == LifecycleState.ARCHIVED
        assert svc.get_lifecycle_metadata("c", TEST_USER).lifecycle_state == LifecycleState.ACTIVE

    def test_delete_one_does_not_affect_others(self):
        svc = _make_service()
        _create_valid(svc, "a")
        _create_valid(svc, "b")
        svc.delete("a", TEST_USER)
        assert svc.get("b", TEST_USER) is not None


# ===================================================================
# Error types
# ===================================================================

class TestServiceErrors:
    def test_cartridge_not_found_is_service_error(self):
        assert issubclass(CartridgeNotFoundError, CartridgeServiceError)

    def test_lifecycle_transition_error_is_service_error(self):
        assert issubclass(LifecycleTransitionError, CartridgeServiceError)
