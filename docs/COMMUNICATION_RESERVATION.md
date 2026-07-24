# Communication Reservation

## Why Communication is Reserved

Communication is a domain of its own.

It is not owned by:

- **Identity** (who the persona is)
- **Character** (what principles guide the persona)
- **Behavior** (how principles are expressed)

When the Communication domain is eventually specified (ST0–ST9), it will own all authored and runtime communication semantics.

Until then, authored communication input must be preserved without interpretation.

---

## Preservation Philosophy

**Archival, not operational.**

Reserved data is:

- **Stored** — never discarded
- **Preserved** — survives upgrades and round trips
- **Never interpreted** — no validation, no inference, no transformation beyond storage
- **Serialized** — always included in cartridge output
- **Deterministic** — same input always produces same reserved output

Reserved data has no behavioral effect on the persona.

No runtime system reads `communication.reserved`.

---

## Structure

Reserved communication data lives in `CommunicationModule.reserved`:

```python
@dataclass(frozen=True)
class CommunicationModule:
    reserved: dict[str, dict]
```

Serialized form:

```json
{
  "communication": {
    "reserved": {
      "communication_style": {
        "value": "Warm and direct"
      }
    }
  }
}
```

Each key in `reserved` names a reserved field. Each value is a dict of key-value pairs describing that field.

---

## Current Reserved Fields

| Field                | Source                     | Preserved Since |
|----------------------|----------------------------|-----------------|
| `communication_style`| `PersonaDraft` / legacy 0.1.0 / 0.2.0 | Schema 0.3.0 |

---

## Migration Behavior

### Schema 0.1.0 (flat) → 0.3.0

1. `_upgrade_0_1_to_0_2` restructures flat data into 0.2.0 compositional format.
   `communication_style` is placed in `character.communication_style`.
2. `_upgrade_0_2_to_0_3` moves `communication_style` from `character` to
   `communication.reserved.communication_style.value`.

### Schema 0.2.0 (nested) → 0.3.0

`_upgrade_0_2_to_0_3` moves `character.communication_style` to
`communication.reserved.communication_style.value`.

If `communication_style` is empty, no entry is created in `reserved`.

### Schema 0.3.0 (current)

The forge maps `PersonaDraft.communication_style` directly to
`CommunicationModule(reserved={"communication_style": {"value": ...}})`.

Empty or whitespace-only values after normalization produce no reserved entry.

---

## Future Ownership

When the Communication domain is specified, its specification will:

1. Define which reserved fields graduate to owned fields.
2. Define migration from `reserved` to owned structure.
3. Remove archived fields from `reserved`.

Until then, `reserved` is append-only.

No field may be removed from `reserved` without a cartridge schema version bump.

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/cartridge.py`         | `CommunicationModule.reserved` field   |
| `app/services/forge.py`           | Maps draft communication_style to reserved |
| `app/services/serializer.py`      | `_upgrade_0_2_to_0_3`, `_deserialize_communication` |
| `tests/test_forge.py`            | `TestUpgrade_0_2_to_0_3`, `TestCommunicationPreservation` |
