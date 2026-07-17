# CHIMERA Persona Cartridge — Schema v0.1

**Schema identity:** `archepersona.chimera.persona-cartridge` / `0.1.0`

## Overview

The CHIMERA Persona Cartridge is the canonical output of the Persona Creation Engine. It encodes a complete, structured, portable personality definition that ARCHEngine can consume and execute.

The cartridge is the boundary between CHIMERA (identity creation) and ARCHEngine (identity execution).

## Status Lifecycle

```
DRAFT -> VALIDATED -> FORGED
```

- `draft`: Being authored. Mutable. Not yet fit for consumption.
- `validated`: Passed structural validation. Ready to forge.
- `forged`: Immutable. Ready for ARCHEngine consumption.

## Fields

### Identity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | The persona's name |
| `summary` | `string` | Yes | Brief description of the persona |

### Character Material

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `core_values` | `list[string]` | Yes (>=1) | Fundamental principles |
| `motivations` | `list[string]` | Yes (>=1) | What drives the persona |
| `strengths` | `list[string]` | Yes (>=1) | Areas of capability |
| `limitations` | `list[string]` | Yes (>=1) | Boundaries of capability |
| `goals` | `list[string]` | Yes (>=1) | What the persona pursues |
| `boundaries` | `list[string]` | Yes (>=1) | Rules the persona operates within |
| `preferences` | `dict[string, string]` | No | Expressed preferences |

### Communication

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `communication_style` | `string` | Yes | Voice, tone, posture description |

### Behavioral Material

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `behavior_rules` | `list[string]` | No (0 allowed) | Behavioral guardrails |

### Metadata

| Field | Type | Description |
|-------|------|-------------|
| `cartridge_id` | `uuid` | Unique cartridge identifier |
| `schema_name` | `string` | `archepersona.chimera.persona-cartridge` |
| `schema_version` | `string` | `0.1.0` |
| `status` | `string` | Current status: `draft`, `validated`, or `forged` |
| `created_at` | `datetime` | RFC 3339 timestamp of creation |
| `updated_at` | `datetime` | RFC 3339 timestamp of last update |

## Validation

Validation is performed by `CartridgeForge.validate()` and returns:

- `valid`: boolean
- `errors[]`: blocking issues — each with `code`, `field`, `message`
- `warnings[]`: non-blocking advisories — each with `code`, `field`, `message`

### Error Codes

| Code | Meaning |
|------|---------|
| `REQUIRED_FIELD_EMPTY` | A required text field is empty |
| `REQUIRED_LIST_EMPTY` | A required list field has no items |
| `INVALID_TYPE` | A field has the wrong type |

### Warning Codes

| Code | Meaning |
|------|---------|
| `NO_BEHAVIOR_RULES` | `behavior_rules` is empty (non-blocking) |

## Forging

`CartridgeForge.forge()` performs validation, then constructs an immutable `PersonaCartridge`. On failure, it returns a structured `ForgeResult` with an error code and detail, rather than raising an exception.

### Forge Error Codes

| Code | Meaning |
|------|---------|
| `VALIDATION_FAILED` | Validation errors prevent forging |
| `INVALID_STATE` | Cartridge is in an invalid state for forging |

## Normalization

Before validation, `PersonaDraft.normalize()` strips whitespace from all string fields, prunes empty entries from list fields, and coerces types.

## Serialization

`PersonaCartridge.to_dict()` produces a JSON-serializable dictionary with:
- All persona fields preserved
- Status as string
- Timestamps as ISO 8601 strings
- Preferences as a flat dict

## Consumption Paths

The cartridge fields are consumed by ARCHEngine via two paths:
1. **Prompt injection**: Selected fields may influence system prompt assembly
2. **Structured packet**: Fields are also delivered as structured data

Each field's consumption path is determined by ARCHEngine, not CHIMERA. CHIMERA's responsibility ends at producing the structured cartridge.
