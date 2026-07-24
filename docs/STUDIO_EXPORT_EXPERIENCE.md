# Studio Export Experience

## Overview

The Export Experience completes the CHIMERA Studio authoring lifecycle. It provides a professional interface for exporting forged Persona Cartridges as canonical JSON artifacts.

## Philosophy

Export is delivery, not deployment. The export process never modifies a cartridge. It only serializes and delivers the existing immutable artifact.

## Architecture

```
Persona Cartridge (immutable, in-memory)
        ↓
CartridgeSerializer.serialize()
        ↓
Canonical JSON (deterministic, byte-identical)
        ↓
Export Package (JSON + metadata)
        ↓
Download / Copy
```

## Routes

### Web

```
GET /cartridges/{cartridge_id}/export
```

Renders the export experience page.

### API

```
GET /api/cartridges/{cartridge_id}/export
```

Returns the canonical serialized cartridge with export metadata.

## API Response

```json
{
    "cartridge": { ... },
    "filename": "identifier_v0.6.0.json",
    "checksum": { "algorithm": "sha256", "value": "..." },
    "size_bytes": 1234,
    "format": "json",
    "validation": { "valid": true, "warning_count": 0, "errors": [] },
    "specification": { "compliant": true, ... },
    "compatibility": { "supported": true, ... },
    "lifecycle": { "export_count": 1 }
}
```

## Supported Formats

| Format | Status |
|--------|--------|
| JSON | Implemented |
| ZIP package | Reserved |
| Signed package | Reserved |
| QR handoff | Reserved |
| Marketplace package | Reserved |

## Serialization Contract

- The backend owns all serialization.
- `CartridgeSerializer.serialize()` produces the canonical output.
- The frontend never generates, modifies, or reconstructs cartridge JSON.
- All export endpoints return the exact same serialized bytes.
- Repeated exports of the same cartridge produce byte-identical JSON.

## Download Behavior

- Filename format: `{identifier}_v{version}.json`
- Example: `brunel_v3.json`
- Filename is deterministic based on cartridge identity and schema version.
- Download uses the Blob API with `application/json` content type.

## Copy JSON

- Uses `navigator.clipboard.writeText()` when available.
- Falls back to `document.execCommand('copy')` for older browsers.
- Copied content matches the downloaded file exactly.
- Provides toast notification and screen-reader announcement.

## Runtime Compatibility

Compatibility information comes from the backend specification module. CHIMERA does not infer compatibility. The following runtimes are displayed:

- **ARCHEngine**: Compatible with Persona Cartridge Specification v1.0.0

## Validation

The export page displays the final validation status without rerunning validation separately. Validation results come from `CartridgeForge.validate_cartridge()` included in the export API response.

## Error Handling

| Error | Response |
|-------|----------|
| Cartridge not found | 404 |
| Serialization failure | 500 (no implementation details) |
| Network interruption | Client-side error display |

## Accessibility

- Skip link to main content
- Screen-reader announcements for copy/download
- Semantic landmarks (banner, navigation, main, contentinfo)
- Keyboard-accessible buttons
- Visible focus indicators
- `aria-live` regions for dynamic updates

## Responsive Design

| Breakpoint | Layout |
|------------|--------|
| Desktop (>900px) | Two-column: sidebar metadata + preview panel |
| Tablet (≤900px) | Stacked: preview first, metadata second |
| Mobile (≤480px) | Full-width buttons, smaller preview font |
