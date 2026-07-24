from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from app.integrations.archengine import CartridgeDescriptorPayload
from app.models.cartridge import (
    CartridgeStatus,
    ForgeError,
    ForgeErrorCode,
    ForgeResult,
    PersonaCartridge,
    PersonaDraft,
)
from app.models.projection import RuntimePersonaProjection, RuntimeProjectionBuilder
from app.services.archengine_export import export_archengine_payload
from app.services.forge import CartridgeForge


# ---------------------------------------------------------------------------
# Lifecycle state — management status only, never affects persona behavior
# ---------------------------------------------------------------------------

class LifecycleState(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class CartridgeServiceError(Exception):
    """Base error for cartridge service operations."""


class CartridgeNotFoundError(CartridgeServiceError):
    """Raised when a cartridge is not found or is logically deleted."""


class LifecycleTransitionError(CartridgeServiceError):
    """Raised when a lifecycle transition is invalid."""


# ---------------------------------------------------------------------------
# Lifecycle metadata — clearly separated from authored persona content
# ---------------------------------------------------------------------------

@dataclass
class CartridgeLifecycleMetadata:
    """Mutable metadata owned by the service, not by the cartridge.

    This data describes management status and operational tracking.
    It is never serialized into the cartridge's authored content.
    """

    lifecycle_state: LifecycleState = LifecycleState.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    archived_at: Optional[datetime] = None
    export_count: int = 0
    clone_source: Optional[str] = None
    source_session_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Summary view — lightweight representation for listing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CartridgeSummary:
    identifier: str
    display_name: str
    summary: str
    schema_version: str
    lifecycle_state: LifecycleState
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Internal record
# ---------------------------------------------------------------------------

@dataclass
class _CartridgeRecord:
    cartridge: PersonaCartridge
    lifecycle: CartridgeLifecycleMetadata


# ---------------------------------------------------------------------------
# CartridgeService — single canonical lifecycle manager
# ---------------------------------------------------------------------------

class CartridgeService:
    """Central orchestration service for the CHIMERA cartridge lifecycle.

    Owns orchestration only.  Delegates forge logic to CartridgeForge,
    runtime views to RuntimeProjectionBuilder, and ARCHEngine export
    to the export service.  Never contains forge logic, validation rules,
    projection logic, or ARCHEngine compatibility code.
    """

    def __init__(self) -> None:
        self._store: dict[str, _CartridgeRecord] = {}
        self._by_uuid: dict[str, str] = {}
        self._history: dict[str, list[_CartridgeRecord]] = {}

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        draft: PersonaDraft,
        source_session_id: Optional[str] = None,
    ) -> ForgeResult:
        """Forge a new cartridge and register it in the lifecycle store.

        On success the cartridge is stored with lifecycle state Active.
        Returns the same ForgeResult from CartridgeForge; the caller
        inspects result.success and result.cartridge.
        """
        result = CartridgeForge.forge(draft)
        if result.success and result.cartridge is not None:
            now = datetime.now(timezone.utc)
            record = _CartridgeRecord(
                cartridge=result.cartridge,
                lifecycle=CartridgeLifecycleMetadata(
                    lifecycle_state=LifecycleState.ACTIVE,
                    created_at=now,
                    updated_at=now,
                    source_session_id=source_session_id,
                ),
            )
            identifier = result.cartridge.identity.identifier
            cartridge_id = result.cartridge.manifest.cartridge_id
            self._store[identifier] = record
            self._by_uuid[cartridge_id] = identifier
            if identifier not in self._history:
                self._history[identifier] = []
            self._history[identifier].append(record)
        return result

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    def get(self, identifier: str) -> PersonaCartridge:
        """Retrieve a cartridge by its persona identifier.

        Raises CartridgeNotFoundError if the cartridge does not exist
        or has been logically deleted.
        """
        record = self._get_record(identifier)
        if record.lifecycle.lifecycle_state == LifecycleState.DELETED:
            raise CartridgeNotFoundError(
                f"Cartridge '{identifier}' is deleted"
            )
        return record.cartridge

    def get_by_uuid(self, cartridge_id: str) -> PersonaCartridge:
        """Retrieve a cartridge by its manifest UUID.

        Raises CartridgeNotFoundError if the UUID is unknown.
        """
        if cartridge_id not in self._by_uuid:
            raise CartridgeNotFoundError(
                f"Cartridge with UUID '{cartridge_id}' not found"
            )
        identifier = self._by_uuid[cartridge_id]
        return self.get(identifier)

    def get_lifecycle_metadata(self, identifier: str) -> CartridgeLifecycleMetadata:
        """Retrieve lifecycle metadata for a cartridge (including deleted)."""
        record = self._get_record(identifier)
        return copy.deepcopy(record.lifecycle)

    def versions(self, identifier: str) -> list[dict]:
        """Return all forged versions sharing the same persona identifier.

        Each version entry includes the cartridge UUID, version info,
        forge timestamp, specification version, and lifecycle state.
        """
        if identifier not in self._history:
            return []
        records = self._history[identifier]
        current_id = self._store.get(identifier)
        current_cartridge_id = (
            current_id.cartridge.manifest.cartridge_id if current_id else None
        )
        return [
            {
                "cartridge_id": r.cartridge.manifest.cartridge_id,
                "identifier": r.cartridge.identity.identifier,
                "display_name": r.cartridge.identity.display_name,
                "schema_version": r.cartridge.manifest.schema_version,
                "specification_version": r.cartridge.manifest.specification_version,
                "forged_at": r.lifecycle.created_at.isoformat(),
                "lifecycle_state": r.lifecycle.lifecycle_state.value,
                "is_current": r.cartridge.manifest.cartridge_id == current_cartridge_id,
            }
            for r in records
        ]

    def get_source_info(self, identifier: str) -> dict:
        """Return source relationship information for a cartridge."""
        record = self._get_record(identifier)
        return {
            "cartridge_id": record.cartridge.manifest.cartridge_id,
            "identifier": identifier,
            "source_session_id": record.lifecycle.source_session_id,
            "forged_at": record.lifecycle.created_at.isoformat(),
            "has_source": record.lifecycle.source_session_id is not None,
        }

    def get_source_info_by_uuid(self, cartridge_id: str) -> dict:
        """Return source relationship information for a cartridge by UUID."""
        if cartridge_id not in self._by_uuid:
            raise CartridgeNotFoundError(
                f"Cartridge with UUID '{cartridge_id}' not found"
            )
        identifier = self._by_uuid[cartridge_id]
        return self.get_source_info(identifier)

    def list(
        self,
        lifecycle_state: Optional[LifecycleState] = None,
        tag: Optional[str] = None,
    ) -> list[CartridgeSummary]:
        """List cartridges, optionally filtered by state or tag.

        Returns lightweight CartridgeSummary objects ordered by
        creation time descending.
        """
        records = list(self._store.values())
        if lifecycle_state is not None:
            records = [r for r in records if r.lifecycle.lifecycle_state == lifecycle_state]
        if tag is not None:
            records = [r for r in records if tag in r.lifecycle.tags]
        return [
            CartridgeSummary(
                identifier=r.cartridge.identity.identifier,
                display_name=r.cartridge.identity.display_name,
                summary=r.cartridge.identity.summary,
                schema_version=r.cartridge.manifest.schema_version,
                lifecycle_state=r.lifecycle.lifecycle_state,
                created_at=r.lifecycle.created_at,
                updated_at=r.lifecycle.updated_at,
            )
            for r in sorted(records, key=lambda x: x.lifecycle.created_at, reverse=True)
        ]

    # ------------------------------------------------------------------
    # Update metadata
    # ------------------------------------------------------------------

    def update_metadata(
        self,
        identifier: str,
        tags: Optional[list[str]] = None,
        notes: Optional[str] = None,
    ) -> CartridgeLifecycleMetadata:
        """Update mutable lifecycle metadata (tags, notes).

        Never modifies authored persona content.
        Never modifies cartridge manifest (cartridge_id, schema version,
        timestamps).
        """
        record = self._get_record(identifier)
        if tags is not None:
            record.lifecycle.tags = list(tags)
        if notes is not None:
            record.lifecycle.notes = notes
        record.lifecycle.updated_at = datetime.now(timezone.utc)
        return copy.deepcopy(record.lifecycle)

    # ------------------------------------------------------------------
    # Clone
    # ------------------------------------------------------------------

    def clone(self, source_identifier: str, new_identifier: str) -> ForgeResult:
        """Clone an existing cartridge with a new persona identifier.

        The clone preserves all authored content, schema version, and
        records clone provenance.  Lifecycle timestamps are reset for
        the new cartridge.  Returns a new ForgeResult with the cloned
        cartridge.
        """
        source = self.get(source_identifier)
        draft = PersonaDraft(
            name=source.identity.display_name,
            identifier=new_identifier,
            summary=source.identity.summary,
            description=source.identity.description,
            aliases=list(source.identity.aliases),
            core_values=list(source.character.core_values),
            motivations=list(source.character.motivations),
            strengths=list(source.character.strengths),
            limitations=list(source.character.limitations),
            goals=list(source.character.goals),
            boundaries=list(source.character.boundaries),
            communication_style=source.communication.communication_style,
            tone=list(source.communication.tone),
            vocabulary_preferences=list(source.communication.vocabulary_preferences),
            response_tendencies=list(source.communication.response_tendencies),
            formatting_preferences=list(source.communication.formatting_preferences),
            preferences={e.key: e.value for e in source.preferences.entries},
            behavior_rules=[p.title for p in source.behavior.policies],
        )
        result = CartridgeForge.forge(draft)
        if result.success and result.cartridge is not None:
            now = datetime.now(timezone.utc)
            record = _CartridgeRecord(
                cartridge=result.cartridge,
                lifecycle=CartridgeLifecycleMetadata(
                    lifecycle_state=LifecycleState.ACTIVE,
                    created_at=now,
                    updated_at=now,
                    clone_source=source.manifest.cartridge_id,
                ),
            )
            new_identifier = result.cartridge.identity.identifier
            new_uuid = result.cartridge.manifest.cartridge_id
            self._store[new_identifier] = record
            self._by_uuid[new_uuid] = new_identifier
            if new_identifier not in self._history:
                self._history[new_identifier] = []
            self._history[new_identifier].append(record)
        return result

    # ------------------------------------------------------------------
    # Archive / Restore
    # ------------------------------------------------------------------

    def archive(self, identifier: str) -> None:
        """Transition a cartridge from Active to Archived."""
        record = self._get_record(identifier)
        if record.lifecycle.lifecycle_state != LifecycleState.ACTIVE:
            raise LifecycleTransitionError(
                f"Cannot archive cartridge '{identifier}': "
                f"current state is {record.lifecycle.lifecycle_state.value}"
            )
        record.lifecycle.lifecycle_state = LifecycleState.ARCHIVED
        record.lifecycle.archived_at = datetime.now(timezone.utc)
        record.lifecycle.updated_at = datetime.now(timezone.utc)

    def restore(self, identifier: str) -> None:
        """Transition a cartridge from Archived back to Active."""
        record = self._get_record(identifier)
        if record.lifecycle.lifecycle_state != LifecycleState.ARCHIVED:
            raise LifecycleTransitionError(
                f"Cannot restore cartridge '{identifier}': "
                f"current state is {record.lifecycle.lifecycle_state.value}"
            )
        record.lifecycle.lifecycle_state = LifecycleState.ACTIVE
        record.lifecycle.archived_at = None
        record.lifecycle.updated_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Logical delete
    # ------------------------------------------------------------------

    def delete(self, identifier: str) -> None:
        """Logically delete a cartridge.  The record is retained.

        Deleted cartridges cannot be retrieved via get() but remain
        in the store for administrative/audit access.
        """
        record = self._get_record(identifier)
        if record.lifecycle.lifecycle_state == LifecycleState.DELETED:
            raise LifecycleTransitionError(
                f"Cannot delete cartridge '{identifier}': already deleted"
            )
        record.lifecycle.lifecycle_state = LifecycleState.DELETED
        record.lifecycle.updated_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Runtime projection
    # ------------------------------------------------------------------

    def runtime_projection(self, identifier: str) -> RuntimePersonaProjection:
        """Produce an immutable runtime view of the cartridge.

        Delegates to RuntimeProjectionBuilder.
        The projection owns no authored data.
        """
        cartridge = self.get(identifier)
        return RuntimeProjectionBuilder.build(cartridge)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_archengine(self, identifier: str) -> CartridgeDescriptorPayload:
        """Export a cartridge to an ARCHEngine-compatible payload.

        Delegates to the existing export service.
        Never constructs compatibility payloads directly.
        Tracks export count in lifecycle metadata.
        """
        cartridge = self.get(identifier)
        payload = export_archengine_payload(cartridge)
        record = self._get_record(identifier)
        record.lifecycle.export_count += 1
        record.lifecycle.updated_at = datetime.now(timezone.utc)
        return payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_record(self, identifier: str) -> _CartridgeRecord:
        if identifier not in self._store:
            raise CartridgeNotFoundError(
                f"Cartridge '{identifier}' not found"
            )
        return self._store[identifier]
