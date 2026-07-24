# CHIMERA Studio Phase 2 — Persistence and Cartridge Library

**Status:** Planning
**Created:** 2026-07-22
**Prerequisite:** Phase 1 Complete (v1.0.0)

---

## Problem

Phase 1 uses in-memory storage. Cartridges and sessions are lost on every Render restart. The dashboard shows a static empty state. Users cannot browse, manage, or return to previously forged personas.

## Goal

Replace in-memory storage with durable persistence so cartridges survive server restarts. The dashboard becomes a real cartridge library showing all forged personas with status, timestamps, and management actions.

## Guiding Principles

1. **Persistence first** — No new features before cartridges survive restarts.
2. **Filesystem before database** — Start with local file storage. Database comes later if needed.
3. **Existing contracts** — `CartridgeRepository` protocol already exists in `cartridge_service.py`. Implement it.
4. **No breaking changes** — Phase 1 API contracts must remain stable.
5. **Backend owns storage** — Frontend never touches the filesystem.

## Assignments

### Assignment 008 — Persistent Cartridge Storage

**Goal:** Cartridges survive Render restarts via filesystem persistence.

**Scope:**
- Implement `FilesystemRepository` following the existing `CartridgeRepository` protocol
- Store forged cartridges as JSON files in a persistent directory
- Load cartridges from disk on service startup
- Session storage remains in-memory (sessions are ephemeral)
- Add `GET /api/cartridges` list endpoint
- Update Dashboard to fetch and display real cartridges
- Add "Last Forged" and "Export Count" columns to dashboard

**API Changes:**
- `GET /api/cartridges` — List all cartridges (new)
- `GET /api/cartridges/{id}` — Unchanged
- All other endpoints — Unchanged

**Data Layout:**
```
data/
  cartridges/
    {identifier}_v{version}.json
  index.json
```

**Tests:** 20+ for repository, list endpoint, dashboard rendering with data.

### Assignment 009 — Cartridge Lifecycle Management

**Goal:** Archive, clone, and delete cartridges from the dashboard.

**Scope:**
- `POST /api/cartridges/{id}/archive` — Archive a cartridge
- `POST /api/cartridges/{id}/restore` — Restore from archive
- `POST /api/cartridges/{id}/clone` — Clone with new identifier
- `POST /api/cartridges/{id}/delete` — Logical delete
- Dashboard action buttons (Archive, Clone, Delete) with confirmation dialogs
- Lifecycle state badges on dashboard cards
- Filter by lifecycle state

**Tests:** 30+ for lifecycle API, dashboard actions, state transitions.

### Assignment 010 — Version History

**Goal:** View and compare all versions of a cartridge.

**Scope:**
- `GET /api/cartridges/identifier/{identifier}/versions` — Version list by persona identifier
- Version history page showing all forged versions
- Diff view comparing two versions (field-level changes)
- Re-forge from a previous version

**Tests:** 25+ for version API, diff engine, version history UI.

## Architecture Decisions

### Why filesystem, not database?

- Render provides persistent disk at `/opt/render/project/data/`
- JSON files are human-readable and debuggable
- No additional dependencies (no SQLAlchemy, no SQLite)
- The `CartridgeRepository` protocol makes the storage backend swappable later
- Cartridges are small (typically <10KB each)

### Why not Redis or cloud storage?

- Overkill for single-process deployment
- Adds cost and complexity
- Can be added later by implementing `CartridgeRepository` for Redis/S3

### Session storage stays in-memory

- Sessions are ephemeral (created during interview, consumed at forge)
- No user needs to "resume" a session after server restart
- Keeping sessions in-memory simplifies the persistence boundary

## Migration

No migration needed. Phase 1 has no persisted data. Phase 2 starts with empty storage.

## Risk

- **Render disk persistence** — Verify that `/opt/render/project/data/` persists across deploys and restarts. If not, fall back to environment variable for storage path.
- **File locking** — Not needed for single-process. Add later if multi-worker is required.
