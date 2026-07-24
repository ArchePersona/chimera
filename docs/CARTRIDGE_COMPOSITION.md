# Cartridge Composition

## Philosophy

A cartridge is one artifact composed of many modules.

The cartridge owns composition. The modules own their own data. The forge assembles them.

No module knows about runtime behavior. No module validates another module. Each module is a single-responsibility, immutable dataclass that serializes independently and validates itself.

Compositional modules were introduced in **Schema 0.2.0**.

---

## Cartridge Architecture

```
PersonaCartridge
├── manifest        (CartridgeManifest)   — immutable metadata
├── identity        (IdentityModule)      — who the persona is
├── character       (CharacterModule)     — stable personality definition
├── preferences     (PreferenceModule)    — user preferences
├── behavior        (BehaviorModule)      — reserved (empty)
├── communication   (CommunicationModule) — reserved (placeholder)
└── extensions      (dict[str, dict])     — future expansion
```

---

## Module Boundaries

### IdentityModule

**Responsibility:** Who the persona is.

| Field          | Type   | Required | Notes                     |
|----------------|--------|----------|---------------------------|
| `display_name` | str    | yes      | Public-facing persona name|
| `summary`      | str    | yes      | Brief persona description |
| `description`  | str    | no       | Extended description      |

**Does NOT own:** personality traits, values, behavior, preferences.

---

### CharacterModule

**Responsibility:** Stable personality definition.

| Field               | Type              | Required | Source draft field    |
|---------------------|-------------------|----------|-----------------------|
| `communication_style`| str              | yes      | `communication_style` |
| `core_values`       | tuple[str, ...]   | yes      | `core_values`         |
| `motivations`       | tuple[str, ...]   | yes      | `motivations`         |
| `strengths`         | tuple[str, ...]   | yes      | `strengths`           |
| `limitations`       | tuple[str, ...]   | yes      | `limitations`         |
| `goals`             | tuple[str, ...]   | yes      | `goals`               |
| `boundaries`        | tuple[str, ...]   | yes      | `boundaries`          |

**Does NOT own:** identity, preferences, behavior, communication state, cognitive data.

**Contains no psychology or behavioral inference.** This is a structural container for character-oriented fields. Interpretation happens at the engine layer, not here.

---

### PreferenceModule

**Responsibility:** User preferences.

| Field     | Type                         | Required |
|-----------|------------------------------|----------|
| `entries` | tuple[tuple[str, str], ...]  | no       |

Stored as a sorted tuple of key-value pairs.

**Duplicate-key behavior:** Python `dict` semantics apply. If duplicate keys exist in the source, the last value wins. The forge sorts entries by key for deterministic ordering. No validation warning is emitted for duplicates.

No interpretation. No hierarchy.

---

### BehaviorModule

**Responsibility:** Reserved for future behavioral rules.

| Field   | Type              | Required |
|---------|-------------------|----------|
| `rules` | tuple[str, ...]   | no       |

**Contains no behavioral logic.** Its existence establishes the architectural slot. Validation emits a warning when empty.

---

### CommunicationModule

**Responsibility:** Reserved for future communication state.

**Contains no fields.** No Communication States. No compressors. No signal chain.

Its existence establishes the architectural slot. Future assignments will define its content.

---

## Reserved Module Serialization Rule

**Rule: All modules are always serialized.**

Reserved modules (`BehaviorModule`, `CommunicationModule`) are included in the serialized output regardless of whether they contain data. This provides a stable schema contract and informs consumers of the cartridge's architectural capabilities.

| Module            | Empty output                  | With data                     |
|-------------------|-------------------------------|-------------------------------|
| `behavior`        | `{"rules": []}`               | `{"rules": ["Ask first"]}`    |
| `communication`   | `{}`                          | `{}` (reserved, no fields)    |

---

## Extension Defensive Copy Policy

Extension dictionaries are defensively deep-copied during:

- **Construction**: callers must not retain mutable references to data passed as extensions.
- **Deserialization**: `CartridgeSerializer.deserialize()` deep-copies the extensions dict before attaching it to the cartridge.
- **Upgrade**: the `0.1.0 → 0.2.0` upgrade path deep-copies extensions.

This guarantees that no external mutation can affect a frozen cartridge's extension data.

---

## Validation Ownership

Each module validates itself via a `validate()` method that returns:

```python
def validate(self) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
```

- Errors indicate structural problems (missing required fields, empty lists).
- Warnings indicate advisory notes (empty behavior rules, etc.).
- Modules may NOT validate other modules.
- The forge aggregates module validation results.
- Validation is deterministic — same input always produces same output.

### Validation Field Paths

To avoid ambiguity in a composed cartridge, validation error/warning `field` values use dot-separated paths that identify module ownership:

- `identity.display_name`
- `identity.summary`
- `character.communication_style`
- `character.core_values`
- `preferences.entries`
- `behavior.rules`

---

## Serialization Ownership

Each module serializes independently via a `to_dict()` method.

The cartridge serializer (`CartridgeSerializer`) composes module dicts into the full cartridge dict.

No module performs global serialization.

### Serialized Format (0.2.0, nested)

```json
{
  "manifest": { ... },
  "identity": {
    "display_name": "Alex",
    "summary": "A thoughtful guide",
    "description": ""
  },
  "character": {
    "communication_style": "Warm and direct",
    "core_values": ["Curiosity"],
    "motivations": ["To help others grow"],
    ...
  },
  "preferences": {
    "entries": { "formality": "casual" }
  },
  "behavior": {
    "rules": ["Ask before acting"]
  },
  "communication": {},
  "extensions": {},
  "status": "forged"
}
```

### Legacy 0.1.0 Format (flat)

Before composition, cartridges used a flat structure:

```json
{
  "manifest": { "schema_version": "0.1.0", ... },
  "name": "Alex",
  "summary": "A thoughtful guide",
  "communication_style": "Warm and direct",
  "core_values": ["Curiosity"],
  ...
}
```

The deserializer automatically detects and upgrades legacy 0.1.0 cartridges to 0.2.0 at read time.

---

## Composition Philosophy

1. **Single responsibility** — each module owns exactly one concern.
2. **No cross-module coupling** — modules never reference each other.
3. **Deterministic assembly** — given the same draft, the forge always produces the same cartridge.
4. **Evolution by replacement** — a cartridge evolves by replacing or extending modules, not by growing a monolithic data structure.
5. **The forge is the only assembly point** — modules are never composed outside the forge pipeline.

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/cartridge.py`         | Module definitions, `PersonaCartridge`  |
| `app/services/forge.py`           | Module construction and validation      |
| `app/services/serializer.py`      | Module-aware serialize/deserialize      |
| `tests/test_forge.py`             | Module, composition, compat tests       |
