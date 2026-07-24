# Cartridge Evolution

## Compatibility Philosophy

A cartridge should still be readable and usable years from now.

The artifact that carries character must remain stable. Behavior can evolve, but the data structure that defines a persona must be forward-compatible, inspectable, and version-safe.

CHIMERA achieves this through three mechanisms:

1. **Manifest** — immutable metadata separated from persona content
2. **Extensions** — versionless namespaces for future expansion without schema changes
3. **Version Negotiation** — explicit version checking at serialization boundaries

---

## Schema Lifecycle

Every cartridge carries a `manifest` block containing its identity:

```json
{
  "manifest": {
    "cartridge_id": "550e8400-e29b-41d4-a716-446655440000",
    "schema_name": "archepersona.chimera.persona-cartridge",
    "schema_version": "0.6.0",
    "created_at": "2026-07-19T12:00:00+00:00",
    "updated_at": "2026-07-19T12:00:00+00:00"
  }
}
```

### Version History

| Version | Description                                      |
|---------|--------------------------------------------------|
| 0.1.0   | Initial canonical cartridge (flat structure)     |
| 0.2.0   | Compositional modules (identity, character, etc.)|
| 0.3.0   | `communication_style` removed from character, preserved in `communication.reserved` |
| 0.4.0   | `communication_style` promoted to first-class field on `CommunicationModule`; new `tone`, `vocabulary_preferences`, `response_tendencies`, `formatting_preferences` fields added |
| 0.5.0   | Generic key/value preference entries replaced with explicit `PreferenceEntry` records (key, value, scope, priority, description); deterministic ordering |
| 0.6.0   | Placeholder behavior `rules` replaced with explicit `BehaviorPolicy` records (identifier, title, description, category, policy_type, enabled); deterministic ordering |

### Version Format

Semantic versioning (`MAJOR.MINOR.PATCH`):

- **MAJOR** — incompatible schema changes (structural breaks, required field removal, type changes)
- **MINOR** — backward-compatible additions (new optional fields, new extension namespaces, structural reorganization)
- **PATCH** — backward-compatible fixes (clarifications, documentation, validation tightening)

### Differences Between 0.1.0 and 0.2.0

| Aspect        | 0.1.0                         | 0.2.0                                    |
|---------------|-------------------------------|------------------------------------------|
| Structure     | Flat fields on cartridge      | Compositional modules (identity, character, preferences, behavior, communication) |
| Serialization | `name`, `core_values`, etc. at top level | Fields nested under module keys          |
| Validation    | Monolithic field checks       | Per-module validation via `validate()`   |
| Upgrade       | —                             | 0.1.0 → 0.2.0 upgrade at read time      |

### Changes in 0.3.0

| Change        | 0.2.0                                    | 0.3.0                                    |
|---------------|------------------------------------------|------------------------------------------|
| communication_style | Owned by `CharacterModule`          | Removed from `CharacterModule`, preserved in `CommunicationModule.reserved` |
| Character keys | `communication_style`, `core_values`, `motivations`, `strengths`, `limitations`, `goals`, `boundaries` | `core_values`, `motivations`, `strengths`, `limitations`, `goals`, `boundaries` |
| Communication keys | `{}` (empty)                        | `reserved.communication_style.value` (if non-empty) |
| Cartridge schema version | Bumped from 0.1.0           | Bumped from 0.2.0                        |
| CharacterModule version | 1                            | 2 (communication_style removed)          |

### Changes in 0.4.0

| Change               | 0.3.0                                       | 0.4.0                                        |
|----------------------|---------------------------------------------|----------------------------------------------|
| communication_style  | Stored in `communication.reserved`          | First-class field on `CommunicationModule`   |
| Communication fields | `communication_style` via reserved only     | `communication_style`, `tone`, `vocabulary_preferences`, `response_tendencies`, `formatting_preferences` |
| CommunicationModule version | 1                                     | 2 (promoted reserved → owned, new fields)    |
| Cartridge schema version | Bumped from 0.2.0                       | Bumped from 0.3.0                            |

### Changes in 0.5.0

| Change               | 0.4.0                                       | 0.5.0                                        |
|----------------------|---------------------------------------------|----------------------------------------------|
| Preference storage   | `entries` as key/value `dict`               | `entries` as sorted list of `PreferenceEntry` records |
| Preference fields    | `key` → `value` (both strings)              | `key`, `value` (str|int|float|bool), `scope`, `priority`, `description` |
| Duplicate keys       | Silently overwritten (last wins)            | Reported as validation error                 |
| PreferenceModule version | 1                                        | 2 (entries replaced with PreferenceEntry)    |
| Ordering             | Insertion-order dependent                   | Deterministic, sorted by key                 |
| Cartridge schema version | Bumped from 0.3.0                       | Bumped from 0.4.0                            |

### Changes in 0.6.0

| Change               | 0.5.0                                       | 0.6.0                                        |
|----------------------|---------------------------------------------|----------------------------------------------|
| Behavior storage     | `rules` as list of strings                  | `policies` as sorted list of `BehaviorPolicy` records |
| Behavior fields      | Plain strings only                          | `identifier`, `title`, `description`, `category`, `policy_type`, `enabled` |
| Duplicate rules      | Silently accepted                           | Reported as validation error                 |
| BehaviorModule version | 1                                         | 2 (rules replaced with BehaviorPolicy)       |
| Ordering             | Insertion-order dependent                   | Deterministic, sorted by identifier          |
| Cartridge schema version | Bumped from 0.4.0                       | Bumped from 0.5.0                            |

### Version Policy

- The serializer always emits the current schema version (`0.6.0`).
- The deserializer accepts `0.1.0` (legacy flat), `0.2.0`, `0.3.0`, `0.4.0`, `0.5.0`, and `0.6.0` (current).
- Legacy `0.1.0` cartridges are upgraded via the chain `0.1.0 → 0.2.0 → 0.3.0 → 0.4.0 → 0.5.0 → 0.6.0`.
- Version `0.2.0` cartridges are upgraded via `0.2.0 → 0.3.0 → 0.4.0 → 0.5.0 → 0.6.0`.
- Version `0.3.0` cartridges are upgraded via `0.3.0 → 0.4.0 → 0.5.0 → 0.6.0`.
- Version `0.4.0` cartridges are upgraded via `0.4.0 → 0.5.0 → 0.6.0`.
- Version `0.5.0` cartridges are upgraded via `0.5.0 → 0.6.0`.
- Future versions will extend `SUPPORTED_VERSIONS` as needed.
- Unsupported versions raise `UnsupportedVersionError` with a clear message listing supported versions.

---

## Extension Rules

### Purpose

Extensions allow future architectural layers (communication states, cognition, memory, governance, etc.) to add data to a cartridge **without modifying the core schema**.

### Constraints

1. An extension is a `dict[str, dict]` — a mapping of namespace name to an arbitrary JSON object.
2. Extension namespaces must use lowercase alphanumeric + underscores (`[a-z][a-z0-9_]*`).
3. Extensions must not shadow core schema fields.
4. Extensions must not conflict with each other (each namespace is independent).
5. Extensions are **versionless** — they carry no version metadata of their own.
6. The core schema treats all extensions opaquely: it preserves them through serialize/deserialize but does not interpret them.
7. Extensions are **defensively copied** during construction and deserialization. No mutable references escape into the cartridge.

### Reserved Namespaces

The following namespaces are reserved for future use and must not be used by custom tooling:

| Namespace        | Reserved For                    |
|------------------|---------------------------------|
| `communication`  | Communication States (ST0–ST9)  |
| `cognition`      | Cognitive inference systems     |
| `memory`         | Memory persistence              |
| `governance`     | Behavioral governance           |
| `drift`          | Drift Whisperer                 |

### Example

```json
{
  "extensions": {
    "communication": {
      "state": "ST3",
      "compressors": { "noise_floor": -60, "limit": 0.8 }
    },
    "cognition": {
      "inference_model": "lion"
    }
  }
}
```

---

## Version Negotiation

### Serializer

The `CartridgeSerializer` class provides:

- **`serialize(cartridge)`** — produces a JSON-compatible dict from a `PersonaCartridge` (always 0.6.0 format)
- **`deserialize(data)`** — reconstructs a `PersonaCartridge` from a dict, upgrading legacy versions automatically

### Deserialization Rules

1. The `manifest` block must be present.
2. `manifest.schema_name` is read but not enforced (reserved for future multi-schema support).
3. `manifest.schema_version` is checked against `SUPPORTED_VERSIONS`.
4. If the version is `0.1.0`, it is upgraded via `0.1.0 → 0.2.0 → 0.3.0 → 0.4.0 → 0.5.0 → 0.6.0` chain.
5. If the version is `0.2.0`, it is upgraded via `0.2.0 → 0.3.0 → 0.4.0 → 0.5.0 → 0.6.0`.
6. If the version is `0.3.0`, it is upgraded via `0.3.0 → 0.4.0 → 0.5.0 → 0.6.0`.
7. If the version is `0.4.0`, it is upgraded via `0.4.0 → 0.5.0 → 0.6.0`.
8. If the version is `0.5.0`, it is upgraded via `0.5.0 → 0.6.0`.
9. If the version is not supported, `UnsupportedVersionError` is raised.
10. Unknown extension namespaces are preserved as-is via deep copy.
11. Missing optional fields default to their zero values (empty string, empty tuple, empty dict).

### Supported Versions

| Version | Supported | Notes                              |
|---------|-----------|------------------------------------|
| 0.1.0   | Yes       | Legacy flat — upgraded on read     |
| 0.2.0   | Yes       | Previous compositional — upgraded on read |
| 0.3.0   | Yes       | Previous compositional — upgraded on read |
| 0.4.0   | Yes       | Previous compositional — upgraded on read |
| 0.5.0   | Yes       | Previous compositional — upgraded on read |
| 0.6.0   | Yes       | Current compositional              |
| 0.7.0+  | No        | Future versions                    |
| 1.0.0+  | No        | Future major                       |

---

## Upgrade Philosophy

### How Upgrades Work

When a `0.1.0` cartridge is deserialized:

```
0.1.0 flat data
      ↓
detect version == "0.1.0"
      ↓
_upgrade_0_1_to_0_2()
  • map flat fields → module keys
  • schema_version → "0.2.0"
  • character.communication_style set from flat field
      ↓
_upgrade_0_2_to_0_3()
  • move character.communication_style → communication.reserved
  • schema_version → "0.3.0"
      ↓
_upgrade_0_3_to_0_4()
  • promote communication.reserved.communication_style → communication.communication_style
  • clear reserved if empty
  • schema_version → "0.4.0"
      ↓
_upgrade_0_4_to_0_5()
  • convert preferences entries dict → sorted PreferenceEntry list
  • each entry: scope=global, priority=normal, description=""
  • schema_version → "0.5.0"
      ↓
_upgrade_0_5_to_0_6()
  • convert behavior rules list → sorted BehaviorPolicy list
  • each policy: identifier=generated via generate_behavior_identifiers(), title=original,
    category=interaction, policy_type=preferred, enabled=true
  • schema_version → "0.6.0"
      ↓
build compositional PersonaCartridge (0.6.0)
      ↓
runtime
```

When a `0.2.0` cartridge is deserialized:

```
0.2.0 nested data
      ↓
detect version == "0.2.0"
      ↓
_upgrade_0_2_to_0_3()
  • move character.communication_style → communication.reserved
  • schema_version → "0.3.0"
      ↓
_upgrade_0_3_to_0_4()
  • promote communication.reserved.communication_style → communication.communication_style
  • clear reserved if empty
  • schema_version → "0.4.0"
      ↓
_upgrade_0_4_to_0_5()
  • convert preferences entries dict → sorted PreferenceEntry list
  • each entry: scope=global, priority=normal, description=""
  • schema_version → "0.5.0"
      ↓
_upgrade_0_5_to_0_6()
  • convert behavior rules list → sorted BehaviorPolicy list
  • each policy: identifier=generated via generate_behavior_identifiers(), title=original,
    category=interaction, policy_type=preferred, enabled=true
  • schema_version → "0.6.0"
      ↓
build compositional PersonaCartridge (0.6.0)
      ↓
runtime
```

When a `0.3.0` cartridge is deserialized:

```
0.3.0 nested data
      ↓
detect version == "0.3.0"
      ↓
_upgrade_0_3_to_0_4()
  • promote communication.reserved.communication_style → communication.communication_style
  • clear reserved if empty
  • schema_version → "0.4.0"
      ↓
_upgrade_0_4_to_0_5()
  • convert preferences entries dict → sorted PreferenceEntry list
  • each entry: scope=global, priority=normal, description=""
  • schema_version → "0.5.0"
      ↓
_upgrade_0_5_to_0_6()
  • convert behavior rules list → sorted BehaviorPolicy list
  • each policy: identifier=generated via generate_behavior_identifiers(), title=original,
    category=interaction, policy_type=preferred, enabled=true
  • schema_version → "0.6.0"
      ↓
build compositional PersonaCartridge (0.6.0)
      ↓
runtime
```

When a `0.4.0` cartridge is deserialized:

```
0.4.0 nested data
      ↓
detect version == "0.4.0"
      ↓
_upgrade_0_4_to_0_5()
  • convert preferences entries dict → sorted PreferenceEntry list
  • each entry: scope=global, priority=normal, description=""
  • schema_version → "0.5.0"
      ↓
_upgrade_0_5_to_0_6()
  • convert behavior rules list → sorted BehaviorPolicy list
  • each policy: identifier=generated via generate_behavior_identifiers(), title=original,
    category=interaction, policy_type=preferred, enabled=true
  • schema_version → "0.6.0"
      ↓
build compositional PersonaCartridge (0.6.0)
      ↓
runtime
```

When a `0.5.0` cartridge is deserialized:

```
0.5.0 nested data
      ↓
detect version == "0.5.0"
      ↓
_upgrade_0_5_to_0_6()
  • convert behavior rules list → sorted BehaviorPolicy list
  • each policy: identifier=generated via generate_behavior_identifiers(), title=original,
    category=interaction, policy_type=preferred, enabled=true
  • schema_version → "0.6.0"
      ↓
build compositional PersonaCartridge (0.6.0)
      ↓
runtime
```

The upgrade is:
- **Deterministic** — same input always produces same output
- **Lossless** — no user information is discarded
- **Automatic** — consumers never see the legacy format

### The 0.2.0 → 0.3.0 Migration

This migration removes `communication_style` from `CharacterModule` and preserves it in `CommunicationModule.reserved`:

| Step | Description |
|------|-------------|
| 1 | Read `character.communication_style` from incoming data |
| 2 | If non-empty, store as `communication.reserved.communication_style.value` |
| 3 | Remove `communication_style` from `character` dict |
| 4 | Update `manifest.schema_version` to `0.3.0` |

If `communication_style` is empty, no reserved entry is created.

### The 0.3.0 → 0.4.0 Migration

This migration promotes `communication_style` from `CommunicationModule.reserved` to a first-class owned field on `CommunicationModule`, and adds new optional communication fields:

| Step | Description |
|------|-------------|
| 1 | Check `communication.reserved` for a `communication_style` entry |
| 2 | If `communication.communication_style` is not already set, read `reserved.communication_style.value` and set it |
| 3 | Remove `communication_style` entry from `reserved` |
| 4 | If `reserved` is now empty, remove the entire `reserved` block |
| 5 | Update `manifest.schema_version` to `0.4.0` |

If `communication.reserved` is empty, no migration occurs and `communication_style` defaults to `""`.

### The 0.4.0 → 0.5.0 Migration

This migration converts legacy key/value preference entries into `PreferenceEntry` records:

| Step | Description |
|------|-------------|
| 1 | Read `preferences.entries` dict (key → value) |
| 2 | For each entry, create `{"key": k, "value": v, "scope": "global", "priority": "normal", "description": ""}` |
| 3 | Sort resulting list by key |
| 4 | Replace `preferences.entries` with the sorted list |
| 5 | Update `manifest.schema_version` to `0.5.0` |

No authored information is lost.

### The 0.5.0 → 0.6.0 Migration

This migration converts legacy placeholder behavior rules into `BehaviorPolicy` records:

| Step | Description |
|------|-------------|
| 1 | Read `behavior.rules` list of strings |
| 2 | For each rule, generate a valid unique identifier via `generate_behavior_identifiers()` |
| 3 | Create `{"identifier": generated, "title": original, "description": "", "category": "interaction", "policy_type": "preferred", "enabled": true}` |
| 4 | Sort resulting list by identifier |
| 5 | Replace `behavior.rules` with `behavior.policies` containing the sorted list |
| 6 | Update `manifest.schema_version` to `0.6.0` |

#### Identifier Generation Guarantee

Valid legacy behavior data will not become invalid solely because identifiers were introduced in Schema 0.6.0. The migration:

- Handles normalization collisions (different rules → same base identifier → numeric suffix)
- Handles punctuation-only rules (fallback to `policy_N` based on source position)
- Handles digit-leading rules (prepends `policy_`)
- Handles repeated identical rules (each becomes a distinct policy)
- Never silently drops authored rules
- Never modifies the original rule text (preserved in `title`)
- Generates identifiers that always pass `BehaviorPolicy.validate_policy()`

No authored information is lost.

### Upgrading Module Versions

Module schema versions describe module evolution independently of cartridge schema versions:

| Event | Cartridge Schema | CharacterModule Version | CommunicationModule Version | PreferenceModule Version | BehaviorModule Version |
|-------|-----------------|------------------------|----------------------------|--------------------------|------------------------|
| Initial character module | 0.2.0 | 1 | — | — | — |
| `communication_style` removed from Character | 0.3.0 | 2 | 1 | — | — |
| `communication_style` promoted to first-class; new fields added | 0.4.0 | 2 | 2 | — | — |
| Preference entries replaced with PreferenceEntry records | 0.5.0 | 2 | 2 | 2 | — |
| Behavior rules replaced with BehaviorPolicy records | 0.6.0 | 2 | 2 | 2 | 2 |

### When Migrations Will Be Added

- **Assignment scope:** when a schema version change requires structural transformation beyond simple field remapping.
- **Trigger:** when `SUPPORTED_VERSIONS` expands and data must be converted between formats.
- **Mechanism:** `CartridgeSerializer` will gain a `_migrations` registry mapping `(from_version, to_version)` → callable.

---

## Compatibility Guarantees

| Scenario                        | Behavior                                      |
|---------------------------------|-----------------------------------------------|
| Current 0.6.0 cartridge         | Serializes and deserializes successfully      |
| Previous 0.5.0 cartridge        | Deserializes via automatic upgrade            |
| Previous 0.4.0 cartridge        | Deserializes via automatic upgrade chain      |
| Previous 0.3.0 cartridge        | Deserializes via automatic upgrade chain      |
| Previous 0.2.0 cartridge        | Deserializes via automatic upgrade chain      |
| Legacy 0.1.0 cartridge          | Deserializes via automatic upgrade chain      |
| Upgrade round-trip (0.1.0→0.6.0)| Round-trips without data loss                 |
| Upgrade round-trip (0.2.0→0.6.0)| Communication data preserved through chain    |
| Upgrade round-trip (0.3.0→0.6.0)| Communication data promoted from reserved     |
| Upgrade round-trip (0.4.0→0.6.0)| Preference entries migrated to PreferenceEntry records |
| Upgrade round-trip (0.5.0→0.6.0)| Behavior rules migrated to BehaviorPolicy records; identifiers generated deterministically |
| Unknown extension namespace     | Preserved through serialize/deserialize       |
| Future minor version (0.7.0)    | `UnsupportedVersionError` raised              |
| Future major version (1.0.0)    | `UnsupportedVersionError` raised              |
| Missing manifest                | `ValueError` raised                           |
| Missing schema_version          | `UnsupportedVersionError` raised              |
| Corrupted data (wrong types)    | Deserialization may fail with `TypeError`     |

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/cartridge.py`         | `CartridgeManifest`, `UnsupportedVersionError`, `parse_version`, `is_version_supported`, `PersonaCartridge.extensions` |
| `app/services/serializer.py`     | `CartridgeSerializer` (serialize/deserialize/upgrade) |
| `tests/test_forge.py`            | Compatibility tests for all scenarios    |
