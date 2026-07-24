# Communication Domain

## Philosophy

Communication defines the persona's **authored style of expression**.

Communication answers:

> **How does this persona intentionally express itself?**

Communication is:
- **Authored** — defined explicitly by the persona creator
- **Declarative** — describes preferences, not runtime behavior
- **Stable** — does not adapt or change at runtime
- **Independent** — cleanly separated from identity, character, and behavior

---

## Authored vs. Behavioral Communication

Everything in Communication is **authored preference**.

CHIMERA will **never**:
- Adapt communication style to context
- Infer tone from conversation
- Modulate emotion
- Select communication strategies at runtime
- Generate prompts

Communication is a **contract** — it tells consumers how the persona prefers to express itself.

Behavior determines how those preferences are **applied** in a specific interaction.

---

## Ownership

### Communication owns

- Communication style
- Tone
- Vocabulary preferences
- Response tendencies
- Formatting preferences
- Reserved (legacy archival data)

### Communication does NOT own

- Identity
- Core values
- Motivations
- Goals
- Boundaries
- Reasoning
- Emotions
- Runtime state
- Conversation history
- Communication States (ST0–ST9)
- Adaptive communication
- Context-sensitive selection

---

## Fields

| Field                     | Type              | Required | Purpose                                        |
|---------------------------|-------------------|----------|-------------------------------------------------|
| `communication_style`     | `str`             | no       | Overall style of expression                     |
| `tone`                    | `tuple[str, ...]` | no       | Ordered preferred tones                         |
| `vocabulary_preferences`  | `tuple[str, ...]` | no       | Ordered vocabulary choices                      |
| `response_tendencies`     | `tuple[str, ...]` | no       | Ordered authored communication habits           |
| `formatting_preferences`  | `tuple[str, ...]` | no       | Ordered formatting preferences                  |
| `reserved`                | `dict[str, dict]` | no       | Legacy archival data (survives upgrades)        |

---

## Communication Style

Single authored value describing the persona's overall expression style.

Examples:
- Direct
- Warm
- Clinical
- Formal
- Conversational

Optional.

---

## Tone

Ordered collection of preferred tones.

Examples:
- Respectful
- Calm
- Curious
- Encouraging
- Precise

Normalization: trim, dedup, preserve order.

---

## Vocabulary Preferences

Ordered collection describing language choices.

Examples:
- Plain language
- Technical terminology
- Analogies
- Minimal jargon

---

## Response Tendencies

Ordered collection describing authored communication habits.

Examples:
- Explains reasoning
- Asks clarifying questions
- Summarizes before concluding
- Uses examples

These are preferences — not runtime guarantees.

---

## Formatting Preferences

Ordered collection describing structural preferences.

Examples:
- Short paragraphs
- Bullet lists
- Tables when useful
- Step-by-step explanations

---

## Collection Normalization

All collection fields undergo the same normalization during draft processing:

1. **Trim** each entry
2. **Remove** empty/whitespace-only entries
3. **Deduplicate** (first occurrence wins)
4. **Preserve** authored order

---

## Validation

Validation is **structural**, not semantic.

### What validation checks

- None — all communication fields are optional
- No required field enforcement
- No semantic interpretation

### What validation does NOT check

- Whether a style is "good"
- Whether tones conflict
- Whether preferences are accurate
- Whether formatting choices are consistent

---

## Serialization

`CommunicationModule` serializes via `to_dict()`:

```json
{
  "communication": {
    "communication_style": "Warm",
    "tone": ["Respectful", "Calm"],
    "vocabulary_preferences": ["Plain language"],
    "response_tendencies": ["Explains reasoning"],
    "formatting_preferences": ["Short paragraphs"]
  }
}
```

Empty fields are omitted from serialized output.

Legacy `reserved` data serializes only when present (survives upgrades).

---

## Migration from Reserved Storage

In schema 0.3.0, `communication_style` was stored in `communication.reserved`.

Schema 0.4.0 promotes it to a first-class field.

### Migration path

| Step | Description |
|------|-------------|
| 1 | Read `communication.reserved.communication_style.value` |
| 2 | If non-empty and `communication.communication_style` is not already set, set it |
| 3 | Remove `communication_style` entry from `reserved` |
| 4 | If `reserved` is now empty, remove the entire block |

No authored information is lost.

### Upgrade chain

| From | To | Mechanism |
|------|----|-----------|
| 0.1.0 (flat) | 0.2.0 | `_upgrade_0_1_to_0_2`: flat → compositional, style in character |
| 0.2.0 | 0.3.0 | `_upgrade_0_2_to_0_3`: character → communication.reserved |
| 0.3.0 | 0.4.0 | `_upgrade_0_3_to_0_4`: reserved → owned field, clear reserved |

---

## Module Version

`CommunicationModule.module_schema_version` → **2**

Bumped from 1 because:
- `communication_style` promoted from reserved to first-class field
- `tone`, `vocabulary_preferences`, `response_tendencies`, `formatting_preferences` added
- The module's schema contract changed

---

## Distinction From Behavior

| Communication                    | Behavior                          |
|----------------------------------|-----------------------------------|
| Declarative (authored preference)| Procedural (action rules)         |
| Stable at runtime                | May adapt per interaction         |
| Answers "how to express"         | Answers "how to decide/act"       |
| No emotions or reasoning         | May encode safety reasoning       |
| Owned by CommunicationModule     | Owned by BehaviorModule           |

---

## Distinction From Character

| Character                        | Communication                     |
|----------------------------------|-----------------------------------|
| What principles guide the persona| How the persona expresses itself  |
| Core values, motivations, etc.   | Style, tone, formatting, etc.     |
| Required collections             | All fields optional               |
| Structural validation            | No validation required            |

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/cartridge.py`         | `CommunicationModule` class, fields, validation |
| `app/services/forge.py`           | Maps draft communication fields to module |
| `app/services/serializer.py`      | `_upgrade_0_3_to_0_4`, `_deserialize_communication` |
| `app/routes/api.py`               | `DraftBody` communication fields        |
| `tests/test_forge.py`            | `TestCommunicationDomain`, `TestCommunicationNormalization`, `TestCommunicationSerialization`, `TestCommunicationMigration`, `TestCommunicationPreservation`, `TestUpgrade_0_2_to_0_3` |
