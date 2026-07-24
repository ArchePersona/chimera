# Character Domain

## Philosophy

Character is the collection of **enduring authored traits** that describe how a persona intends to conduct itself.

Character answers:

> **What enduring principles define this persona?**

Character is:
- **Declarative** — authored, not generated
- **Stable** — does not change at runtime
- **Independent** — cleanly separated from identity and behavior

---

## Authored vs. Inferred

Everything in Character is **explicitly authored** by the persona creator.

CHIMERA will **never**:
- Infer character from behavior
- Generate character from prompts
- Learn character from conversation
- Adapt character at runtime

If it is not in the cartridge, it is not character.

---

## Ownership

### Character owns

- Core values
- Motivations
- Strengths
- Limitations
- Goals
- Boundaries

### Character does NOT own

- Identity (display name, identifier, summary, description, aliases)
- Communication style
- Emotional state
- Runtime decisions
- Memories
- Learned behavior
- Conversation history
- Personality typing
- Psychological traits

---

## Fields

Each field is an **ordered collection** (tuple) of authored strings.

| Field          | Required | Purpose                                      |
|----------------|----------|----------------------------------------------|
| `core_values`  | yes      | Principles the persona lives by               |
| `motivations`  | yes      | Why the persona exists                        |
| `strengths`    | yes      | Author-declared capabilities                  |
| `limitations`  | yes      | Capabilities intentionally withheld           |
| `goals`        | yes      | Long-lived authored objectives               |
| `boundaries`   | yes      | Hard constraints the persona will not violate |

---

## Core Values

Ordered collection of principles.

Examples:
- Honesty
- Curiosity
- Precision
- Compassion

Normalization: trim, dedup, preserve order.

---

## Motivations

Ordered collection describing why the persona exists.

Examples:
- Help people learn
- Preserve knowledge
- Solve difficult problems

No ranking. No inference.

---

## Strengths

Ordered collection of author-declared capabilities.

Examples:
- Systems thinking
- Patience
- Technical depth

Author-declared only — not inferred from behavior.

---

## Limitations

Ordered collection of capabilities intentionally withheld or bounded.

Examples:
- Does not speculate without evidence
- Avoids legal advice
- Requires clarification for ambiguity

Limitations are **not weaknesses**. They are intentional design choices.

---

## Goals

Ordered collection of long-lived authored objectives.

Examples:
- Preserve institutional knowledge
- Build trusted relationships
- Produce accurate evidence

Goals are enduring — not session-specific.

---

## Boundaries

Ordered collection of hard constraints.

Examples:
- Never fabricate evidence
- Never impersonate a human
- Never reveal confidential information

Boundaries are declarative commitments the persona will not intentionally violate.

---

## Collection Normalization

All collections undergo the same normalization during draft processing:

1. **Trim** each entry
2. **Remove** empty/whitespace-only entries
3. **Deduplicate** (first occurrence wins)
4. **Preserve** authored order

This is handled by `PersonaDraft.normalize()` via `_normalize_list()`.

---

## Validation

Validation is **structural**, not semantic.

### Rules

| Rule                           | Error Code           |
|--------------------------------|----------------------|
| `core_values` must not be empty  | `REQUIRED_LIST_EMPTY` |
| `motivations` must not be empty  | `REQUIRED_LIST_EMPTY` |
| `strengths` must not be empty    | `REQUIRED_LIST_EMPTY` |
| `limitations` must not be empty  | `REQUIRED_LIST_EMPTY` |
| `goals` must not be empty        | `REQUIRED_LIST_EMPTY` |
| `boundaries` must not be empty   | `REQUIRED_LIST_EMPTY` |

### What validation does NOT check

- Whether a value is "good" or "bad"
- Whether values contradict each other
- Whether limitations are reasonable
- Whether goals conflict
- Whether strengths are accurate

---

## Serialization

`CharacterModule` serializes itself via `to_dict()`:

```json
{
  "character": {
    "core_values": ["Honesty", "Courage"],
    "motivations": ["To help others grow"],
    "strengths": ["Patience"],
    "limitations": ["Overthinking"],
    "goals": ["Inspire learning"],
    "boundaries": ["Never lie"]
  }
}
```

No character data leaks into other modules. No other module contains character data.

---

## Distinction From Behavior

| Character                        | Behavior                          |
|----------------------------------|-----------------------------------|
| Declarative                      | Procedural                        |
| Authored once                    | May adapt                         |
| Never changes at runtime         | May change based on context       |
| Answers "what principles"        | Answers "how expressed in action" |
| Structural                       | Behavioral                        |
| Validated by format only         | Validated by consistency + safety |
| Owned by CharacterModule         | Owned by BehaviorModule           |

---

## Distinction From Identity

| Identity                         | Character                         |
|----------------------------------|-----------------------------------|
| Who the persona is               | What principles guide the persona |
| display_name, identifier, etc.   | values, motivations, goals, etc.  |
| Name-based recognition           | Principle-based understanding     |
| Unique per persona               | May overlap across personas       |

---

## Module Version

`CharacterModule.module_schema_version` → **2**

Bumped from 1 because:
- `communication_style` was removed (not owned by character)
- The module's schema contract changed

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/cartridge.py`         | `CharacterModule` class, validation     |
| `app/services/forge.py`           | Maps draft collections to module        |
| `app/services/serializer.py`      | Deserializes character with defaults    |
| `tests/test_forge.py`            | Character collections, validation, serialization tests |
