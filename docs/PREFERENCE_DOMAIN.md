# Preference Domain

## Philosophy

A preference expresses an **authored inclination**.

Preference answers:

> **What stable authored choices does this persona intentionally carry?**

Preferences are authored, declarative, and stable. They influence future behavior but do not execute behavior.

---

## Authored vs. Learned Preferences

Preferences are **authored**. They are:
- Defined explicitly by the persona creator
- Stable at runtime
- Not adapted, inferred, or learned

CHIMERA does NOT implement:
- Learned preferences
- User-specific preferences
- Adaptive preferences
- Preference inheritance
- Preference conflict resolution
- Runtime overrides
- Memory-derived preferences
- Behavioral weighting

Preferences are a **contract** — they tell consumers what the persona intentionally carries.

---

## Ownership

### PreferenceModule owns

- Authored preferences (as `PreferenceEntry` records)
- Preference normalization (whitespace)
- Preference validation (structural, not semantic)
- Deterministic ordering (sorted by key)

### PreferenceModule does NOT own

- Learned preferences
- Inferred preferences
- Runtime overrides
- User preferences
- Conflict resolution
- Adaptation
- Core values (CharacterModule)
- Motivation (CharacterModule)
- Behavior rules (BehaviorModule)
- Communication style (CommunicationModule)

---

## PreferenceEntry

Each preference is an immutable record:

| Field         | Type                    | Required | Default    | Purpose                            |
|---------------|-------------------------|----------|------------|-------------------------------------|
| `key`         | `str`                   | yes      | —          | Stable machine identifier           |
| `value`       | `str \| int \| float \| bool` | yes | —          | Authored value                      |
| `scope`       | `str`                   | no       | `"global"` | Where the preference applies        |
| `priority`    | `str`                   | no       | `"normal"` | Authored importance                 |
| `description` | `str`                   | no       | `""`       | Optional authored explanation        |

---

## Key Rules

- Lowercase letters, digits, underscores only (`[a-z][a-z0-9_]*`)
- Must begin with a letter
- Immutable after forging
- Machine-friendly

---

## Value

May be:
- `str`
- `int`
- `float`
- `bool`

Collections are out of scope.

---

## Scope

Defines where the preference applies.

Allowed values:
- `global` — applies everywhere
- `contextual` — applies in specific contexts

No additional scopes. No semantic interpretation.

---

## Priority

Declares authored importance.

Allowed values:
- `low`
- `normal`
- `high`

This is **descriptive metadata**. It is **not** runtime weighting.

---

## Validation

Validation is **structural**, not semantic.

### What validation checks

- Key syntax: lowercase, alphanumeric + underscore, leading letter
- Duplicate keys
- Allowed value types (str, int, float, bool)
- Scope values (global, contextual)
- Priority values (low, normal, high)
- Field-path reporting for all errors
- Whitespace normalization

### What validation does NOT check

- Whether a preference is "good"
- Whether values are semantically valid
- Whether preferences conflict
- Whether preferences are relevant
- Whether scope is appropriate

---

## Duplicate Keys

Duplicate authored keys are **not permitted**.

- Validation reports them as errors
- Validation does **not** silently overwrite
- Field path: `preferences.entries.<key>`

---

## Ordering

Serialization order is **deterministic**.

- Entries are sorted by key
- Never depends on insertion order

---

## Serialization

`PreferenceModule` serializes via `to_dict()`:

```json
{
  "preferences": {
    "entries": [
      {
        "key": "verbosity",
        "value": "high",
        "scope": "global",
        "priority": "normal",
        "description": ""
      }
    ]
  }
}
```

Sorted by key.

---

## Migration from Legacy Format

In schema 0.4.0, preferences were stored as key/value dict entries:

```json
{
  "preferences": {
    "entries": {"verbosity": "high"}
  }
}
```

Schema 0.5.0 migrates each entry to a `PreferenceEntry` record with defaults:

| Field         | Legacy → Migrated Value |
|---------------|--------------------------|
| `key`         | Preserved                |
| `value`       | Preserved                |
| `scope`       | `"global"` (default)     |
| `priority`    | `"normal"` (default)    |
| `description` | `""` (default)           |

### Upgrade chain

| From | To | Mechanism |
|------|----|-----------|
| 0.1.0 (flat) | 0.2.0 | `_upgrade_0_1_to_0_2`: flat → compositional |
| 0.2.0 | 0.3.0 | `_upgrade_0_2_to_0_3`: character → communication.reserved |
| 0.3.0 | 0.4.0 | `_upgrade_0_3_to_0_4`: reserved → owned communication fields |
| 0.4.0 | 0.5.0 | `_upgrade_0_4_to_0_5`: legacy dict → sorted PreferenceEntry list |

---

## Module Version

`PreferenceModule.module_schema_version` → **2**

Bumped from 1 because:
- Generic key/value entries replaced with `PreferenceEntry` records
- Added scope, priority, description fields
- Duplicate key detection added
- Deterministic sorting by key added

---

## Distinction From Character

| Character (CharacterModule)       | Preference (PreferenceModule)       |
|-----------------------------------|--------------------------------------|
| What enduring principles          | What stable authored choices         |
| Required collections              | Optional entries                     |
| Core values, motivations, etc.    | Key/value with scope/priority        |
| Structural validation required    | Structural validation on each entry  |

---

## Distinction From Behavior

| Preference                        | Behavior (BehaviorModule)         |
|-----------------------------------|-----------------------------------|
| Declarative (authored inclination)| Procedural (action rules)         |
| Does not execute behavior         | Encodes decision rules            |
| Stable at runtime                 | May adapt per interaction         |

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/cartridge.py`         | `PreferenceEntry`, `PreferenceModule`, validation |
| `app/services/forge.py`           | Maps draft preferences to `PreferenceEntry` objects |
| `app/services/serializer.py`      | `_upgrade_0_4_to_0_5`, `_deserialize_preferences` |
| `app/routes/api.py`               | `DraftBody` preferences field           |
| `tests/test_forge.py`            | Test classes covering entries, duplicates, ordering, migration, compatibility |
