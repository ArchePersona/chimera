# CHIMERA Studio Phase 1 — Release Note

**Version:** 1.0.0
**Date:** 2026-07-22
**Tag:** `v1.0.0`

---

## Summary

CHIMERA Studio Phase 1 delivers the complete deterministic Persona Cartridge authoring pipeline. Users can create a persona through a guided interview, review the assembled draft, forge it into an immutable cartridge, inspect every aspect of the forged artifact, and export it as canonical JSON.

## Deployed

| Endpoint | URL |
|----------|-----|
| ARCHEngine Landing | `https://archengine.onrender.com/` |
| CHIMERA Dashboard | `https://archengine.onrender.com/chimera/` |
| ARCHEngine Health | `https://archengine.onrender.com/health` |
| CHIMERA Health | `https://archengine.onrender.com/chimera/api/health` |

## What Was Built

### Assignment 001 — Application Shell
Base layout, header/footer, navigation, error pages, accessibility skip link, semantic landmarks, CSS design tokens, `studio.js` mobile nav and toast system.

### Assignment 002 — Persona Dashboard
Cartridge listing with empty state, search bar placeholder, status badge framework, "Create New Persona" entry point.

### Assignment 003 — Guided Interview Workspace
18 deterministic questions across 5 sections (Identity, Character, Communication, Preferences, Behavior). Session management, progress tracking, conditional question dependencies, answer validation, skip support.

### Assignment 004 — Draft Review
Session API routes, draft review API, dynamic template, forge readiness indicator, inline validation display, 43 tests.

### Assignment 005 — Versioned Forge
Confirmation dialog, forge progress/success/error states, focus trapping, Escape support, ARIA live announcements, 42 tests. Each forge creates a new immutable cartridge version with a new UUID, preserving the stable persona identifier.

### Assignment 006 — Cartridge Inspector
UUID-based lookup, version history panel, source session tracking, Inspector API routes, Inspector template with 8 tab panels (Overview, Identity, Character, Communication, Preferences, Behavior, Validation, Versions), `inspector.js`, `CartridgeForge.validate_cartridge()`, 26 tests.

### Assignment 007 — Export Experience
Export API returning canonical serialized cartridge with filename, SHA-256 checksum, size, validation, specification compliance, and runtime compatibility. Export template with metadata panel, JSON preview, download/copy actions. 34 tests.

## Production Fixes During Verification

1. **Forge 500 on Render** — `schemas/persona-cartridge-1.0.0.json` was never vendored into `backend/chimera_app/`. Fixed by copying `schemas/` into the vendored copy.

2. **API exception handlers returned HTML for mounted routes** — Path check `request.url.path.startswith("/api/")` failed when mounted at `/chimera`. Fixed by changing to `"/api/" in path` substring check.

3. **CI isolation** — Vendored Studio tests imported `fastapi` at module level, breaking ARCHEngine CI when fastapi is not installed. Fixed with `pytest.importorskip("fastapi")` in all 5 Studio test files.

## Test Totals

| Suite | Tests |
|-------|-------|
| CHIMERA Studio (all) | **883** |
| Export Experience | 34 |
| Cartridge Inspector | 26 |
| Forge Experience | 42 |
| Draft Review | 43 |
| Studio Shell | 15 |

## Green CI Commits

| Repository | Commit | Hash |
|------------|--------|------|
| CHIMERA | CI isolation: pytest.importorskip('fastapi') in all Studio test files | `c0431ea` |
| ARCHEngine | CI isolation: pytest.importorskip('fastapi') before TestClient import in vendored Studio tests | `83c96d8` |

## Verified Routes (Production)

### Static Pages
- `GET /` — ARCHEngine React landing page with "Create a Persona with CHIMERA" button
- `GET /chimera/` — CHIMERA Dashboard
- `GET /chimera/cartridges/new` — New Persona entry screen
- `GET /chimera/how-it-works` — Documentation page
- `GET /chimera/cartridges/{id}` — Inspector page
- `GET /chimera/cartridges/{id}/export` — Export page

### API Endpoints
- `GET /chimera/api/health`
- `POST /chimera/api/sessions`
- `GET /chimera/api/sessions/{id}`
- `GET /chimera/api/sessions/{id}/questions`
- `GET /chimera/api/sessions/{id}/progress`
- `POST /chimera/api/sessions/{id}/answers`
- `POST /chimera/api/sessions/{id}/skip`
- `GET /chimera/api/sessions/{id}/draft`
- `POST /chimera/api/sessions/{id}/validate`
- `POST /chimera/api/sessions/{id}/forge`
- `GET /chimera/api/cartridges/{id}`
- `GET /chimera/api/cartridges/{id}/validation`
- `GET /chimera/api/cartridges/{id}/versions`
- `GET /chimera/api/cartridges/{id}/source`
- `GET /chimera/api/cartridges/{id}/export`

## Scope Freeze

Phase 1 scope is now frozen. The following are **not included** and belong to Phase 2 or later:

- Persistent cartridge storage (cartridges lost on Render restart)
- Dashboard cartridge listing (currently static empty state)
- Version history UI expansion
- Cartridge management (Archive, Clone, Delete)
- Marketplace, sharing, templates, collaboration
- AI-assisted interview
- Filesystem or cloud persistence
- Signed or encrypted cartridges

## Known Limitations

- Sessions and cartridges are in-memory only (no persistence across server restarts)
- Dashboard shows static empty state (no list-all-cartridges API)
- No user authentication
- Single-process deployment (no horizontal scaling)
