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

try:
    from app.repositories.cartridge_repository import CartridgeRepository
except ImportError:
    CartridgeRepository = None  # type: ignore[assignment,misc]


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

    Every public method requires an ``owner_user_id`` to enforce
    user isolation.  When a CartridgeRepository is provided, all
    persistence is delegated to it.  Otherwise, in-memory dicts
    (keyed by owner_user_id + identifier) are used.
    """

    def __init__(self, repo: "CartridgeRepository | None" = None) -> None:
        self._repo = repo
        # In-memory fallback (used when no repo is provided)
        self._store: dict[tuple[str, str], _CartridgeRecord] = {}
        self._by_uuid: dict[tuple[str, str], str] = {}
        self._history: dict[tuple[str, str], list[_CartridgeRecord]] = {}

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        draft: PersonaDraft,
        owner_user_id: str,
        source_session_id: Optional[str] = None,
    ) -> ForgeResult:
        """Forge a new cartridge and register it in the lifecycle store.

        On success the cartridge is stored with lifecycle state Active.
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
            if self._repo is not None:
                self._repo.save(identifier, record, owner_user_id)
            else:
                self._store[(owner_user_id, identifier)] = record
                self._by_uuid[(owner_user_id, cartridge_id)] = identifier
                key = (owner_user_id, identifier)
                if key not in self._history:
                    self._history[key] = []
                self._history[key].append(record)
        return result

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    def get(self, identifier: str, owner_user_id: str) -> PersonaCartridge:
        """Retrieve a cartridge by its persona identifier.

        Raises CartridgeNotFoundError if the cartridge does not exist
        or has been logically deleted.
        """
        record = self._get_record(identifier, owner_user_id)
        if record.lifecycle.lifecycle_state == LifecycleState.DELETED:
            raise CartridgeNotFoundError(
                f"Cartridge '{identifier}' is deleted"
            )
        return record.cartridge

    def get_by_uuid(self, cartridge_id: str, owner_user_id: str) -> PersonaCartridge:
        """Retrieve a cartridge by its manifest UUID."""
        if self._repo is not None:
            record = self._repo.get_by_uuid(cartridge_id, owner_user_id)
        else:
            identifier = self._by_uuid.get((owner_user_id, cartridge_id))
            if identifier is None:
                raise CartridgeNotFoundError(
                    f"Cartridge with UUID '{cartridge_id}' not found"
                )
            record = self._get_record(identifier, owner_user_id)
        if record.lifecycle.lifecycle_state == LifecycleState.DELETED:
            raise CartridgeNotFoundError(
                f"Cartridge with UUID '{cartridge_id}' is deleted"
            )
        return record.cartridge

    def get_lifecycle_metadata(
        self, identifier: str, owner_user_id: str
    ) -> CartridgeLifecycleMetadata:
        """Retrieve lifecycle metadata for a cartridge (including deleted)."""
        record = self._get_record(identifier, owner_user_id)
        return copy.deepcopy(record.lifecycle)

    def versions(self, identifier: str, owner_user_id: str) -> list[dict]:
        """Return all forged versions sharing the same persona identifier."""
        if self._repo is not None:
            records = self._repo.versions(identifier, owner_user_id)
        else:
            key = (owner_user_id, identifier)
            records = self._history.get(key, [])

        current_key = (owner_user_id, identifier)
        current_rec = self._store.get(current_key) if self._repo is None else None
        if self._repo is not None:
            try:
                current_rec = self._repo.get(identifier, owner_user_id)
            except CartridgeNotFoundError:
                current_rec = None
        current_cartridge_id = (
            current_rec.cartridge.manifest.cartridge_id if current_rec else None
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

    def get_source_info(self, identifier: str, owner_user_id: str) -> dict:
        """Return source relationship information for a cartridge."""
        record = self._get_record(identifier, owner_user_id)
        return {
            "cartridge_id": record.cartridge.manifest.cartridge_id,
            "identifier": identifier,
            "source_session_id": record.lifecycle.source_session_id,
            "forged_at": record.lifecycle.created_at.isoformat(),
            "has_source": record.lifecycle.source_session_id is not None,
        }

    def get_source_info_by_uuid(self, cartridge_id: str, owner_user_id: str) -> dict:
        """Return source relationship information for a cartridge by UUID."""
        if self._repo is not None:
            record = self._repo.get_by_uuid(cartridge_id, owner_user_id)
        else:
            identifier = self._by_uuid.get((owner_user_id, cartridge_id))
            if identifier is None:
                raise CartridgeNotFoundError(
                    f"Cartridge with UUID '{cartridge_id}' not found"
                )
            record = self._get_record(identifier, owner_user_id)
        return {
            "cartridge_id": record.cartridge.manifest.cartridge_id,
            "identifier": record.cartridge.identity.identifier,
            "source_session_id": record.lifecycle.source_session_id,
            "forged_at": record.lifecycle.created_at.isoformat(),
            "has_source": record.lifecycle.source_session_id is not None,
        }

    def list(
        self,
        owner_user_id: str,
        lifecycle_state: Optional[LifecycleState] = None,
        tag: Optional[str] = None,
    ) -> list[CartridgeSummary]:
        """List cartridges for a user, optionally filtered by state or tag."""
        if self._repo is not None:
            pairs = self._repo.list_all(owner_user_id)
            records = [r for _, r in pairs]
        else:
            records = [
                r for (uid, _), r in self._store.items()
                if uid == owner_user_id
            ]
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
        owner_user_id: str,
        tags: Optional[list[str]] = None,
        notes: Optional[str] = None,
    ) -> CartridgeLifecycleMetadata:
        """Update mutable lifecycle metadata (tags, notes)."""
        record = self._get_record(identifier, owner_user_id)
        if tags is not None:
            record.lifecycle.tags = list(tags)
        if notes is not None:
            record.lifecycle.notes = notes
        record.lifecycle.updated_at = datetime.now(timezone.utc)
        if self._repo is not None:
            self._repo.persist_current(identifier, owner_user_id)
        return copy.deepcopy(record.lifecycle)

    # ------------------------------------------------------------------
    # Clone
    # ------------------------------------------------------------------

    def clone(
        self, source_identifier: str, new_identifier: str, owner_user_id: str
    ) -> ForgeResult:
        """Clone an existing cartridge with a new persona identifier."""
        source = self.get(source_identifier, owner_user_id)
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
            new_id = result.cartridge.identity.identifier
            new_uuid = result.cartridge.manifest.cartridge_id
            if self._repo is not None:
                self._repo.save(new_id, record, owner_user_id)
            else:
                self._store[(owner_user_id, new_id)] = record
                self._by_uuid[(owner_user_id, new_uuid)] = new_id
                key = (owner_user_id, new_id)
                if key not in self._history:
                    self._history[key] = []
                self._history[key].append(record)
        return result

    # ------------------------------------------------------------------
    # Archive / Restore
    # ------------------------------------------------------------------

    def archive(self, identifier: str, owner_user_id: str) -> None:
        """Transition a cartridge from Active to Archived."""
        record = self._get_record(identifier, owner_user_id)
        if record.lifecycle.lifecycle_state != LifecycleState.ACTIVE:
            raise LifecycleTransitionError(
                f"Cannot archive cartridge '{identifier}': "
                f"current state is {record.lifecycle.lifecycle_state.value}"
            )
        record.lifecycle.lifecycle_state = LifecycleState.ARCHIVED
        record.lifecycle.archived_at = datetime.now(timezone.utc)
        record.lifecycle.updated_at = datetime.now(timezone.utc)
        if self._repo is not None:
            self._repo.persist_current(identifier, owner_user_id)

    def restore(self, identifier: str, owner_user_id: str) -> None:
        """Transition a cartridge from Archived back to Active."""
        record = self._get_record(identifier, owner_user_id)
        if record.lifecycle.lifecycle_state != LifecycleState.ARCHIVED:
            raise LifecycleTransitionError(
                f"Cannot restore cartridge '{identifier}': "
                f"current state is {record.lifecycle.lifecycle_state.value}"
            )
        record.lifecycle.lifecycle_state = LifecycleState.ACTIVE
        record.lifecycle.archived_at = None
        record.lifecycle.updated_at = datetime.now(timezone.utc)
        if self._repo is not None:
            self._repo.persist_current(identifier, owner_user_id)

    # ------------------------------------------------------------------
    # Logical delete
    # ------------------------------------------------------------------

    def delete(self, identifier: str, owner_user_id: str) -> None:
        """Logically delete a cartridge."""
        record = self._get_record(identifier, owner_user_id)
        if record.lifecycle.lifecycle_state == LifecycleState.DELETED:
            raise LifecycleTransitionError(
                f"Cannot delete cartridge '{identifier}': already deleted"
            )
        record.lifecycle.lifecycle_state = LifecycleState.DELETED
        record.lifecycle.updated_at = datetime.now(timezone.utc)
        if self._repo is not None:
            self._repo.persist_current(identifier, owner_user_id)

    # ------------------------------------------------------------------
    # Runtime projection
    # ------------------------------------------------------------------

    def runtime_projection(
        self, identifier: str, owner_user_id: str
    ) -> RuntimePersonaProjection:
        """Produce an immutable runtime view of the cartridge."""
        cartridge = self.get(identifier, owner_user_id)
        return RuntimeProjectionBuilder.build(cartridge)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_archengine(
        self, identifier: str, owner_user_id: str
    ) -> CartridgeDescriptorPayload:
        """Export a cartridge to an ARCHEngine-compatible payload."""
        cartridge = self.get(identifier, owner_user_id)
        payload = export_archengine_payload(cartridge)
        record = self._get_record(identifier, owner_user_id)
        record.lifecycle.export_count += 1
        record.lifecycle.updated_at = datetime.now(timezone.utc)
        if self._repo is not None:
            self._repo.persist_current(identifier, owner_user_id)
        return payload

    def export_canonical(self, identifier: str, owner_user_id: str) -> dict:
        """Export the canonical serialized cartridge and track the export."""
        from app.services.serializer import CartridgeSerializer
        cartridge = self.get(identifier, owner_user_id)
        serialized = CartridgeSerializer.serialize(cartridge)
        record = self._get_record(identifier, owner_user_id)
        record.lifecycle.export_count += 1
        record.lifecycle.updated_at = datetime.now(timezone.utc)
        if self._repo is not None:
            self._repo.persist_current(identifier, owner_user_id)
        return serialized

    def export_canonical_by_uuid(self, cartridge_id: str, owner_user_id: str) -> dict:
        """Export the canonical serialized cartridge by UUID."""
        if self._repo is not None:
            identifier = self._repo.get_by_uuid(cartridge_id, owner_user_id).identity.identifier
        else:
            identifier = self._by_uuid.get((owner_user_id, cartridge_id))
            if identifier is None:
                raise CartridgeNotFoundError(
                    f"Cartridge with UUID '{cartridge_id}' not found"
                )
        return self.export_canonical(identifier, owner_user_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_record(self, identifier: str, owner_user_id: str) -> _CartridgeRecord:
        if self._repo is not None:
            return self._repo.get(identifier, owner_user_id)
        key = (owner_user_id, identifier)
        if key not in self._store:
            raise CartridgeNotFoundError(
                f"Cartridge '{identifier}' not found"
            )
        return self._store[key]
