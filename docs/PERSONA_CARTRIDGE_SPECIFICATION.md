# Persona Cartridge Specification v1.0.0

## Overview & Purpose

The **Persona Cartridge Specification** formalizes the portable contract for Persona Cartridges created by **CHIMERA** and consumed by compliant behavioral runtimes such as **ARCHEngine**.

It establishes an explicit, versioned, and language-agnostic boundary between **Persona Authoring** (CHIMERA) and **Behavioral Execution** (ARCHEngine).

---

## Architectural Position

In CHIMERA's pipeline, specification validation occurs immediately after forging:

```text
PersonaDraft
     │
     ▼
Validation
     │
     ▼
CartridgeForge
     │
     ▼
PersonaCartridge
     │
     ▼
Specification Validation (v1.0.0)
     │
     ▼
Runtime Projection
     │
     ▼
ARCHEngine Export
```

A forged cartridge is not considered compliant until it passes `SpecificationValidator`.

---

## Specification Versioning

The **Specification Version** is decoupled from the CHIMERA application version.

- **Canonical Specification Version**: `1.0.0`
- **Schema Name**: `archepersona.chimera.persona-cartridge`
- **Schema Version**: `0.6.0`
- **Canonical JSON Schema URI**: `https://archepersona.org/schemas/persona-cartridge-1.0.0.json`

Future CHIMERA releases may evolve internally while continuing to produce Specification 1.x cartridges.

---

## Ownership Boundaries

- **CHIMERA owns**: Persona authoring, interview sessions, drafts, validation, forging, cartridge lifecycle, runtime projection, and export.
- **Specification owns**: The portable contract definitions, JSON Schema, validation rules, required modules, and prohibited field definitions.
- **ARCHEngine owns**: Cartridge loading, runtime execution, communication state transitions, modes, memory selection, and prompt assembly.

---

## Required Modules & Structures

Specification v1.0.0 requires every compliant cartridge to contain five core modules:

1. **`identity`**: `display_name` (required, non-empty), `identifier` (required, lowercase letter start `[a-z][a-z0-9_-]*`), `summary` (required, non-empty), `description` (optional string), `aliases` (optional list of strings).
2. **`character`**: `core_values`, `motivations`, `strengths`, `limitations`, `goals`, `boundaries` (lists of strings).
3. **`communication`**: `communication_style` (optional string), `tone`, `vocabulary_preferences`, `response_tendencies`, `formatting_preferences` (lists of strings), `reserved` (object).
4. **`preferences`**: `entries` (list of `PreferenceEntry` objects with `key`, `value`, `scope`, `priority`, `description`).
5. **`behavior`**: `policies` (list of `BehaviorPolicy` objects with `identifier`, `title`, `description`, `category`, `policy_type`, `enabled`).

Every cartridge must also contain a `manifest` object with `cartridge_id`, `schema_name`, `schema_version`, `specification_version`, `created_at`, and `updated_at`.

---

## Prohibited Runtime Content

A Persona Cartridge represents pure authored persona intelligence. Runtime operational state must **NEVER** appear inside a cartridge.

Prohibited runtime fields include:
- `communication_state`, `communication_states`
- `runtime_mode`, `operational_mode`, `mode`
- `tribunal_state`, `tribunal`
- `drift_information`, `drift_whisperer`, `drift`
- `memories`, `memory`, `short_term_memory`, `long_term_memory`
- `investigation_data`, `investigation_history`, `investigations`
- `conversation_history`, `chat_history`, `messages`
- `provider_metadata`, `ai_provider`, `llm_config`
- `token_statistics`, `token_usage`
- `execution_timestamps`, `last_execution_time`
- `runtime_confidence`, `confidence_score`

`SpecificationValidator` recursively inspects all levels of cartridge data (including extensions) and rejects any cartridge containing prohibited runtime keys (`RULE_PROHIBITED_RUNTIME_DATA`).

---

## Deterministic Guarantees

1. **Preference Key Ordering**: Preference entries are deterministically sorted alphabetically by key.
2. **Policy Identifiers**: Behavior policies are assigned deterministic lowercase identifiers (`[a-z][a-z0-9_]*`) and must be strictly unique.
3. **Module Order**: Serialized dictionary output maintains a stable module ordering (`manifest`, `identity`, `character`, `preferences`, `behavior`, `communication`, `extensions`, `status`).
4. **Serialization Reproducibility**: Two equivalent authored drafts forge into cartridges with identical serialized dictionary representations (modulo unique `cartridge_id` and creation timestamps).

---

## JSON Schema

The canonical JSON Schema is published at:
`schemas/persona-cartridge-1.0.0.json`

It serves as the public source of truth for external systems and language runtimes.

---

## Specification Conformance & Validation

Validation is performed by `app.specification.SpecificationValidator`:

```python
from app.specification import SpecificationValidator

# Returns a structured SpecificationValidationResult
result = SpecificationValidator.validate(cartridge)

if not result.compliant:
    for violation in result.violations:
        print(f"Rule: {violation.rule}")
        print(f"Location: {violation.location}")
        print(f"Reason: {violation.reason}")
        print(f"Recommendation: {violation.recommendation}")
```

Or enforce via exception:

```python
from app.specification import SpecificationValidator

SpecificationValidator.validate_or_raise(cartridge)
```

---

## Compatibility Policy & Negotiation

- **Supported Specification Versions**: `{"1.0.0"}`
- **Deprecated Versions**: None
- **Downgrade Support**: Not supported.
- **Negotiation Strategy**: External runtimes inspect `manifest.specification_version` before loading. Specification v1.x additions are backwards-compatible and non-breaking.
