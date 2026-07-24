# Identity Domain

## Philosophy

Identity is **declarative**. Identity is **authored**. Identity never changes during runtime.

A persona is who it claims to be — not who an algorithm infers it to be.

Behavior **expresses** identity. Behavior does **not create** identity.

IdentityModule answers one question:

> **"Who is this persona?"**

It does **not** answer:

- How does it think?
- How does it speak?
- How does it decide?
- How does it change?

Those belong to future domains (Character, Communication, Behavior).

---

## Ownership

### IdentityModule owns

- Display name (public-facing name)
- Identifier (stable logical ID)
- Summary (short recognition description)
- Description (long-form authored description)
- Aliases (ordered collection of alternate names)

### IdentityModule does NOT own

- Personality
- Goals
- Motivations
- Communication style
- Behavior rules
- Memory
- History
- Runtime state
- Provenance
- Authorship metadata

---

## Fields

| Field          | Type              | Required | Mutable | Purpose                              |
|----------------|-------------------|----------|---------|--------------------------------------|
| `display_name` | `str`             | yes      | no      | Human-readable name                  |
| `identifier`   | `str`             | yes      | no      | Stable machine-friendly logical ID   |
| `summary`      | `str`             | yes      | no      | One-to-two sentence recognition      |
| `description`  | `str`             | no       | no      | Long-form authored description       |
| `aliases`      | `tuple[str, ...]` | no       | no      | Ordered alternate names              |

---

## Identifier Rules

### Purpose

The identifier is a stable, machine-friendly logical ID that distinguishes the persona across systems.

It is:
- **Not** a UUID (use `cartridge_id` for that)
- **Not** the cartridge ID (separate concept)
- **Immutable** after forging

### Format

| Rule              | Description                                          |
|-------------------|------------------------------------------------------|
| Allowed chars     | `a-z`, `0-9`, `-`, `_`                               |
| Case              | Lowercase only                                       |
| First character   | Must be a letter (`a-z`)                             |
| Length            | At least 1 character                                 |

### Examples

Valid:
- `brunel`
- `sherlock`
- `athena`
- `my-persona-01`
- `guide_v2`

Invalid:
- `Brunel` (uppercase)
- `1brunel` (leading digit)
- `brunel!` (special character)
- `brunel name` (space)

### Normalization

During draft normalization:
- Whitespace is stripped
- Value is lowercased

---

## Alias Rules

### Purpose

Aliases provide alternate names by which the persona is known.

They are **declarative** — authored, not inferred.

### Normalization

During draft normalization:
- Each alias is whitespace-trimmed
- Empty/whitespace-only aliases are removed
- Duplicate aliases are removed (preserving first occurrence order)
- Remaining aliases preserve their authored order

### Examples

Draft aliases:
```
["  The Engineer  ", "Archivist", "", "  ", "Companion", "Archivist"]
```

After normalization:
```
["The Engineer", "Archivist", "Companion"]
```

---

## Validation Philosophy

Identity validation is **structural**, not semantic.

It checks:
- Required fields are present and non-empty
- Identifier format is valid
- Aliases are properly normalized

It does **not** check:
- Whether a name is "good"
- Whether a description is accurate
- Whether an identifier matches any convention beyond format

---

## Validation Rules

| Field            | Rule                                   | Error Code           |
|------------------|----------------------------------------|----------------------|
| `display_name`   | Must not be empty                      | `REQUIRED_FIELD_EMPTY` |
| `identifier`     | Must not be empty                      | `INVALID_IDENTIFIER` |
| `identifier`     | Must match format rules                | `INVALID_IDENTIFIER` |
| `summary`        | Must not be empty                      | `REQUIRED_FIELD_EMPTY` |
| `aliases`        | Normalized (whitespace, dedup, empty)  | — (forge-time only)  |

---

## Serialization

`IdentityModule` serializes itself via `to_dict()`:

```json
{
  "identity": {
    "display_name": "Alex",
    "identifier": "alex",
    "summary": "A thoughtful guide",
    "description": "An optional longer description.",
    "aliases": ["The Guide", "Alex the Great"]
  }
}
```

The cartridge serializer composes the identity dict into the full cartridge output.

No identity data leaks into other modules. No other module contains identity data.

---

## Distinction From Behavior

| Identity                          | Behavior                          |
|-----------------------------------|-----------------------------------|
| Declarative                       | Procedural                        |
| Authored once                     | May adapt                         |
| Never changes at runtime          | May change based on context       |
| Answers "who"                     | Answers "how"                     |
| Structural                        | Behavioral                        |
| Validated by format only          | Validated by consistency + safety |
| Owned by IdentityModule           | Owned by future BehaviorModule    |

---

## Module Version

`IdentityModule.module_schema_version` → **2**

Bumped from 1 because:
- `identifier` was added as a required field
- `aliases` was added as an optional field
- Both changes alter the module's schema contract

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/cartridge.py`         | `IdentityModule`, `_validate_identifier`, `_IDENTIFIER_ALLOWED` |
| `app/services/forge.py`           | Maps draft identifier/aliases to module |
| `app/services/serializer.py`      | Deserializes identity with defaults     |
| `app/routes/api.py`               | `DraftBody.identifier`, `DraftBody.aliases` |
| `tests/test_forge.py`            | Identifier validation, alias tests      |
