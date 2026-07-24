# Runtime Persona Projection

## Philosophy

The cartridge defines **what the persona is**.

The runtime projection defines **what the runtime is allowed to see**.

Execution will eventually determine **what the runtime does with that information**.

These responsibilities must remain separate.

---

## Cartridge Boundary

The cartridge is the source of truth:

- Immutable
- Versioned
- Compositional
- Declarative
- Backward compatible

The runtime **never** consumes the cartridge directly.

---

## Runtime Boundary

The runtime consumes a deterministic projection:

- Read-only
- Deterministic
- Immutable
- One-way (projection cannot be serialized back into a cartridge)

The projection owns no authored data.

The cartridge remains unchanged.

---

## Projection Contents

### Identity

| Field             | Source                      |
|-------------------|-----------------------------|
| `identifier`      | `identity.identifier`       |
| `display_name`    | `identity.display_name`     |
| `summary`         | `identity.summary`          |
| `description`     | `identity.description`      |
| `aliases`         | `identity.aliases`          |

### Character

| Field             | Source                      |
|-------------------|-----------------------------|
| `core_values`     | `character.core_values`     |
| `motivations`     | `character.motivations`     |
| `strengths`       | `character.strengths`       |
| `limitations`     | `character.limitations`     |
| `goals`           | `character.goals`           |
| `boundaries`      | `character.boundaries`      |

### Communication

| Field                     | Source                                    |
|---------------------------|-------------------------------------------|
| `communication_style`     | `communication.communication_style`       |
| `tone`                    | `communication.tone`                      |
| `vocabulary_preferences`  | `communication.vocabulary_preferences`    |
| `response_tendencies`     | `communication.response_tendencies`       |
| `formatting_preferences`  | `communication.formatting_preferences`    |

Reserved legacy communication data is **not** exposed in the projection.

### Preferences

Exposes authored `PreferenceEntry` objects with stable deterministic ordering (sorted by key).

### Behavior

Only `enabled == true` policies are exposed.

Disabled policies remain in the cartridge but are excluded from the default runtime projection.

---

## Provenance

The projection exposes the authored source identity:

| Field                     | Source                             |
|---------------------------|------------------------------------|
| `cartridge_id`            | `manifest.cartridge_id`            |
| `cartridge_schema_version`| `manifest.schema_version`          |

Manifest timestamps are not included.

---

## Builder

`RuntimeProjectionBuilder` in `app/models/projection.py` constructs projections:

```
RuntimeProjectionBuilder

↓

build(PersonaCartridge)

↓

RuntimePersonaProjection
```

The builder:

- Filters behavior policies to enabled-only
- Preserves preference ordering
- Excludes reserved legacy communication data
- Performs no validation (only forged cartridges may be projected)

---

## Determinism

Repeated projection of the same cartridge produces identical output.

No timestamps.

No UUID generation.

No mutation.

---

## Immutability

`RuntimePersonaProjection` is a frozen dataclass.

Runtime consumers may not mutate authored data.

---

## Ownership

### Projection owns

- Runtime view
- Filtering (enabled policies only)
- Ordering (preferences, policies)

### Projection does NOT own

- Validation
- Serialization (to_dict is optional and one-way)
- Persistence
- Upgrades
- Migration
- Execution
- Decision making
- Prompt generation
- Model formatting

---

## One-Way Serialization

`to_dict()` is optional.

If used:

- Serializes only the projection
- Never serializes back into a cartridge format
- The projection is a one-way transformation

---

## Out of Scope

The projection does NOT implement:

- Prompt generation
- Runtime execution
- Decision engines
- Communication States
- LION, GOAT, DRAGON
- Memory, learning, adaptation
- Drift Whisperer
- Policy evaluation
- Model formatting
- BRUNEL integration
- Runtime caching

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/projection.py`        | `RuntimePersonaProjection`, `RuntimeProjectionBuilder` |
| `tests/test_projection.py`        | Projection tests                        |
| `docs/RUNTIME_PROJECTION.md`      | This document                           |
