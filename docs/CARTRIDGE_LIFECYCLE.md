# Cartridge Lifecycle Service

## Overview

`CartridgeService` is the single canonical service responsible for managing
`PersonaCartridge` objects throughout their lifecycle within CHIMERA.

It owns orchestration only.  Forge logic, validation rules, runtime projection,
and ARCHEngine compatibility code remain in their respective components.

---

## Lifecycle stages

```
                    ┌──────────┐
                    │  Create  │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
         ┌─────────│  Active  │──────────┐
         │         └────┬─────┘          │
         │              │                │
    ┌────▼────┐   ┌────▼─────┐     ┌────▼─────┐
    │ Delete  │   │ Archive  │     │ Clone    │
    └────┬────┘   └────┬─────┘     └──────────┘
         │              │
    ┌────▼────┐   ┌────▼─────┐
    │ Deleted │   │ Archived │
    └─────────┘   └────┬─────┘
                       │
                  ┌────▼─────┐
                  │ Restore  │──► Active
                  └──────────┘
```

- **Draft** — reserved for future use (pre-forge authoring).
- **Active** — cartridge is forged, available for projection and export.
- **Archived** — cartridge is preserved but not in active use.
- **Deleted** — logical deletion; record retained for audit/admin.

Lifecycle states describe **management status only**.  They never affect
persona behavior, runtime projection content, or export payloads.

---

## Ownership boundaries

| Concern                 | Owner                     |
|------------------------|---------------------------|
| Cartridge creation      | `CartridgeForge`          |
| Validation              | `CartridgeForge.validate` |
| Runtime views           | `RuntimeProjectionBuilder`|
| ARCHEngine export       | `archengine_export`       |
| Lifecycle orchestration | `CartridgeService`        |

`CartridgeService` must **never** contain:
- Forge logic
- Validation rules
- Runtime projection logic
- ARCHEngine compatibility code

---

## Immutable fields

The service guarantees it never modifies:

| Field                  | Reason                        |
|------------------------|-------------------------------|
| `identifier`           | Persona identity is permanent |
| `cartridge_id`         | Unique forge provenance       |
| `manifest.schema_name` | Schema contract               |
| `manifest.schema_version` | Version history            |
| `manifest.created_at`  | Forge provenance              |
| Authored module data   | Persona content is sacred     |

---

## Mutable metadata

Lifecycle metadata stored separately from the cartridge:

| Field           | Type              | Mutable via            |
|-----------------|-------------------|------------------------|
| `tags`          | `list[str]`       | `update_metadata()`    |
| `notes`         | `str`             | `update_metadata()`    |
| `export_count`  | `int`             | Incremented on export  |
| `clone_source`  | `str \| None`    | Set on clone           |
| `archived_at`   | `datetime \| None`| Set on archive/restore |
| `lifecycle_state` | `LifecycleState` | archive/restore/delete |

---

## Clone semantics

Cloning a cartridge:

- Generates a new persona `identifier` (caller-supplied)
- Preserves all authored content (identity, character, communication,
  preferences, behavior)
- Preserves schema version (`0.6.0`)
- Records clone provenance: `clone_source` = source `cartridge_id`
- Resets lifecycle timestamps
- Forges a new `PersonaCartridge` through `CartridgeForge`
- Results in lifecycle state **Active**

---

## Export integration

`CartridgeService.export_archengine()` delegates to
`app.services.archengine_export.export_archengine_payload()`.

The service never:
- Constructs compatibility payloads directly
- Imports ARCHEngine shim types into lifecycle logic
- Modifies export payloads

The service **does** track export count in lifecycle metadata.

---

## Future persistence model

The current implementation is in-memory.  Explicit extension points for:

- **Local repository** (`app/repositories/`)
- **Filesystem persistence** (`app/repositories/fs_repository.py`)
- **Cloud persistence** (`app/repositories/cloud_repository.py`)
- **Cartridge marketplace** — discovery and distribution
- **Signed cartridges** — cryptographic attestation
- **Encrypted cartridges** — at-rest encryption

Each future repository would implement a `CartridgeRepository` protocol:

```
class CartridgeRepository(Protocol):
    def save(self, identifier: str, record: _CartridgeRecord) -> None: ...
    def load(self, identifier: str) -> _CartridgeRecord: ...
    def delete(self, identifier: str) -> None: ...
    def list(self) -> list[_CartridgeRecord]: ...
```
