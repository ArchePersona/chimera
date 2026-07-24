"""Persistent cartridge repository for CHIMERA Studio."""

from __future__ import annotations

from typing import Optional

from app.models.cartridge import PersonaCartridge
from app.repositories.storage import FilesystemStorage
from app.services.cartridge_service import (
    CartridgeLifecycleMetadata,
    CartridgeNotFoundError,
    LifecycleState,
    _CartridgeRecord,
)

_HISTORY_SUB = "versions"
_UUID_INDEX = "_uuid_index"


def _serialize_record(record: _CartridgeRecord) -> dict:
    """Serialize a CartridgeRecord to a JSON-safe dict."""
    lc = record.lifecycle
    return {
        "cartridge": record.cartridge.to_dict(),
        "lifecycle": {
            "lifecycle_state": lc.lifecycle_state.value,
            "created_at": lc.created_at.isoformat(),
            "updated_at": lc.updated_at.isoformat(),
            "archived_at": lc.archived_at.isoformat() if lc.archived_at else None,
            "export_count": lc.export_count,
            "clone_source": lc.clone_source,
            "source_session_id": lc.source_session_id,
            "tags": list(lc.tags),
            "notes": lc.notes,
        },
    }


def _deserialize_record(data: dict) -> _CartridgeRecord:
    """Deserialize a JSON dict back to a CartridgeRecord."""
    from datetime import datetime, timezone

    cartridge = PersonaCartridge.from_dict(data["cartridge"])
    lc_data = data["lifecycle"]

    def _parse_dt(val: Optional[str]) -> Optional[datetime]:
        if val is None:
            return None
        return datetime.fromisoformat(val)

    lifecycle = CartridgeLifecycleMetadata(
        lifecycle_state=LifecycleState(lc_data["lifecycle_state"]),
        created_at=datetime.fromisoformat(lc_data["created_at"]),
        updated_at=datetime.fromisoformat(lc_data["updated_at"]),
        archived_at=_parse_dt(lc_data.get("archived_at")),
        export_count=lc_data.get("export_count", 0),
        clone_source=lc_data.get("clone_source"),
        source_session_id=lc_data.get("source_session_id"),
        tags=list(lc_data.get("tags", [])),
        notes=lc_data.get("notes", ""),
    )
    return _CartridgeRecord(cartridge=cartridge, lifecycle=lifecycle)


class CartridgeRepository:
    """Persists cartridge records, UUID index, and version history.

    Every public method requires an ``owner_user_id`` to enforce user
    isolation at the storage boundary.

    Storage layout::

        cartridges/
            {owner_user_id}/
                {identifier}.json          -- current active record
                _uuid_index.json           -- cartridge_id -> identifier
                {identifier}/
                    versions/
                        {cartridge_id}.json -- each historical version
    """

    def __init__(self, storage: FilesystemStorage) -> None:
        self._storage = storage
        self._cache: dict[tuple[str, str], _CartridgeRecord] = {}
        self._uuid_cache: dict[tuple[str, str], str] = {}
        self._history_cache: dict[tuple[str, str], list[_CartridgeRecord]] = {}
        self._loaded_users: set[str] = set()

    def _domain(self, owner_user_id: str) -> str:
        return f"cartridges/{owner_user_id}"

    def _ensure_loaded(self, owner_user_id: str) -> None:
        """Lazy-load all data for a user from disk into cache."""
        if owner_user_id in self._loaded_users:
            return
        self._loaded_users.add(owner_user_id)

        domain = self._domain(owner_user_id)

        # Load UUID index
        self._uuid_cache[owner_user_id] = self._storage.read_index(
            domain, _UUID_INDEX
        )

        # Load all current cartridges
        for key in self._storage.list_keys(domain):
            if key.startswith("_"):
                continue
            data = self._storage.read(domain, key)
            if data is not None:
                record = _deserialize_record(data)
                self._cache[(owner_user_id, key)] = record

        # Load version history for each identifier
        for identifier in [
            ident for (uid, ident) in self._cache
            if uid == owner_user_id
        ]:
            self._load_history(owner_user_id, identifier)

    def _load_history(
        self, owner_user_id: str, identifier: str
    ) -> list[_CartridgeRecord]:
        """Load version history for an identifier from disk."""
        cache_key = (owner_user_id, identifier)
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]
        versions_domain = f"{self._domain(owner_user_id)}/{identifier}/{_HISTORY_SUB}"
        self._storage.ensure_domain(versions_domain)
        records = []
        for vkey in self._storage.list_keys(versions_domain):
            data = self._storage.read(versions_domain, vkey)
            if data is not None:
                records.append(_deserialize_record(data))
        self._history_cache[cache_key] = records
        return records

    def _save_current(
        self, owner_user_id: str, identifier: str, record: _CartridgeRecord
    ) -> None:
        """Persist the current cartridge record to disk."""
        self._storage.write(self._domain(owner_user_id), identifier, _serialize_record(record))

    def _save_version(
        self, owner_user_id: str, identifier: str, record: _CartridgeRecord
    ) -> None:
        """Persist a version record to the history directory."""
        cartridge_id = record.cartridge.manifest.cartridge_id
        domain = f"{self._domain(owner_user_id)}/{identifier}/{_HISTORY_SUB}"
        self._storage.write(domain, cartridge_id, _serialize_record(record))

    def _save_uuid_index(self, owner_user_id: str) -> None:
        """Persist the UUID -> identifier index for a user."""
        idx = self._uuid_cache.get(owner_user_id, {})
        self._storage.write_index(self._domain(owner_user_id), idx, _UUID_INDEX)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, identifier: str, owner_user_id: str) -> _CartridgeRecord:
        """Retrieve the current cartridge record by persona identifier."""
        self._ensure_loaded(owner_user_id)
        cache_key = (owner_user_id, identifier)
        if cache_key not in self._cache:
            raise CartridgeNotFoundError(f"Cartridge '{identifier}' not found")
        return self._cache[cache_key]

    def get_by_uuid(self, cartridge_id: str, owner_user_id: str) -> _CartridgeRecord:
        """Retrieve a cartridge record by its manifest UUID."""
        self._ensure_loaded(owner_user_id)
        idx = self._uuid_cache.get(owner_user_id, {})
        if cartridge_id not in idx:
            raise CartridgeNotFoundError(
                f"Cartridge with UUID '{cartridge_id}' not found"
            )
        identifier = idx[cartridge_id]
        return self.get(identifier, owner_user_id)

    def exists(self, identifier: str, owner_user_id: str) -> bool:
        """Check if a cartridge exists."""
        self._ensure_loaded(owner_user_id)
        return (owner_user_id, identifier) in self._cache

    def save(
        self, identifier: str, record: _CartridgeRecord, owner_user_id: str
    ) -> None:
        """Save or update a cartridge as the current version."""
        self._ensure_loaded(owner_user_id)
        cache_key = (owner_user_id, identifier)
        self._cache[cache_key] = record
        cartridge_id = record.cartridge.manifest.cartridge_id
        if owner_user_id not in self._uuid_cache:
            self._uuid_cache[owner_user_id] = {}
        self._uuid_cache[owner_user_id][cartridge_id] = identifier
        self._save_current(owner_user_id, identifier, record)
        self._save_version(owner_user_id, identifier, record)
        self._save_uuid_index(owner_user_id)

    def append_version(
        self, identifier: str, record: _CartridgeRecord, owner_user_id: str
    ) -> None:
        """Append a new version to history and update current."""
        self._ensure_loaded(owner_user_id)
        cache_key = (owner_user_id, identifier)
        self._cache[cache_key] = record
        cartridge_id = record.cartridge.manifest.cartridge_id
        if owner_user_id not in self._uuid_cache:
            self._uuid_cache[owner_user_id] = {}
        self._uuid_cache[owner_user_id][cartridge_id] = identifier
        if cache_key not in self._history_cache:
            self._history_cache[cache_key] = []
        self._history_cache[cache_key].append(record)
        self._save_current(owner_user_id, identifier, record)
        self._save_version(owner_user_id, identifier, record)
        self._save_uuid_index(owner_user_id)

    def versions(
        self, identifier: str, owner_user_id: str
    ) -> list[_CartridgeRecord]:
        """Return all version records for an identifier."""
        self._ensure_loaded(owner_user_id)
        cache_key = (owner_user_id, identifier)
        if cache_key not in self._history_cache:
            self._load_history(owner_user_id, identifier)
        return list(self._history_cache.get(cache_key, []))

    def list_all(self, owner_user_id: str) -> list[tuple[str, _CartridgeRecord]]:
        """List all current cartridges as (identifier, record) pairs."""
        self._ensure_loaded(owner_user_id)
        return [
            (ident, rec)
            for (uid, ident), rec in self._cache.items()
            if uid == owner_user_id
        ]

    def persist_current(self, identifier: str, owner_user_id: str) -> None:
        """Flush the current in-memory record to disk (no new version).

        Use after metadata-only mutations (archive, restore, delete,
        update_metadata, export count).
        """
        self._ensure_loaded(owner_user_id)
        cache_key = (owner_user_id, identifier)
        if cache_key not in self._cache:
            return
        record = self._cache[cache_key]
        self._save_current(owner_user_id, identifier, record)
        self._save_uuid_index(owner_user_id)

    def delete(self, identifier: str, owner_user_id: str) -> None:
        """Remove current cartridge but keep version history."""
        self._ensure_loaded(owner_user_id)
        cache_key = (owner_user_id, identifier)
        self._cache.pop(cache_key, None)
        self._storage.delete(self._domain(owner_user_id), identifier)

    def clear_cache(self) -> None:
        """Clear all in-memory caches."""
        self._cache.clear()
        self._uuid_cache.clear()
        self._history_cache.clear()
        self._loaded_users.clear()
