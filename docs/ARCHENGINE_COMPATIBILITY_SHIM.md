# ARCHEngine Compatibility Shim

## Why the shim exists

ARCHEngine currently consumes personas via a `CartridgeDescriptor` format that predates the CHIMERA compositional schema.

The shim provides a narrow translation layer that converts a CHIMERA `RuntimePersonaProjection` into an isolated `CartridgeDescriptorPayload` matching the existing ARCHEngine contract.

This preserves the current ARCHEngine pipeline while allowing it to consume personas forged by CHIMERA.

---

## Pipeline

```text
PersonaCartridge
        ↓
RuntimeProjectionBuilder
        ↓
RuntimePersonaProjection
        ↓
ARCHEngineCompatibilityShim.translate()
        ↓
CartridgeDescriptorPayload
        ↓
Existing ARCHEngine runtime
```

---

## Ownership boundaries

### The shim owns

- Translation logic
- Field mapping rules
- Metadata fallback
- Payload isolation

### The shim does NOT own

- Runtime execution
- Cartridge or projection validation
- Cartridge or projection mutation
- Persistence
- Runtime decisions
- Prompt assembly
- ARCHEngine runtime code
- ARCHEngine dependencies in CHIMERA core models

---

## Supported field mappings

| Projection field                       | ARCHEngine field                   |
|----------------------------------------|------------------------------------|
| `cartridge_id`                         | `id`                               |
| `display_name`                         | `name`                             |
| `cartridge_schema_version`             | `version`                          |
| always `true`                          | `active`                           |
| `communication_style`                  | `system_prompt`                    |
| `core_values`, `motivations`           | `values`                           |
| `strengths`, `limitations`, `goals`, `boundaries` | `disposition`           |
| `preferences` (key → value)            | `preferences`                      |
| enabled `policies` (as `to_dict` list) | `boundaries.policies`              |

---

## Unsupported fields

The following projection fields have no direct ARCHEngine equivalent and are preserved under `metadata.chimera`:

| Field                       | Location                   |
|-----------------------------|----------------------------|
| `identifier`                | `metadata.chimera.identifier` |
| `summary`                   | `metadata.chimera.summary` |
| `description`               | `metadata.chimera.description` |
| `aliases`                   | `metadata.chimera.aliases` |
| `tone`                      | `metadata.chimera.tone` |
| `vocabulary_preferences`    | `metadata.chimera.vocabulary_preferences` |
| `response_tendencies`       | `metadata.chimera.response_tendencies` |
| `formatting_preferences`    | `metadata.chimera.formatting_preferences` |

---

## Metadata fallback behavior

Any projection field without a safe current destination in the ARCHEngine descriptor is placed under `metadata.chimera`.

This ensures:

- No authored information is silently discarded
- Fields remain accessible when ARCHEngine adds native support
- The shim tolerates projection fields ARCHEngine does not yet understand

---

## Removal strategy

When ARCHEngine supports the CHIMERA schema natively:

1. Remove `app/integrations/archengine.py`
2. Remove `tests/test_archengine_compatibility.py`
3. Remove `docs/ARCHENGINE_COMPATIBILITY_SHIM.md`
4. Update any consumers to use `RuntimePersonaProjection` directly

The shim is designed to be removable without affecting CHIMERA's core models.

---

## Files

| File                                      | Role                                    |
|-------------------------------------------|-----------------------------------------|
| `app/integrations/archengine.py`          | `ARCHEngineCompatibilityShim`, `CartridgeDescriptorPayload` |
| `tests/test_archengine_compatibility.py`  | Compatibility tests                     |
| `docs/ARCHENGINE_COMPATIBILITY_SHIM.md`   | This document                           |
