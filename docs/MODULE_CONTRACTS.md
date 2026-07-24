# Module Contracts

## Ownership

Every cartridge module is an independent, immutable, self-validating unit.

The cartridge owns **composition**. Modules own **their own data**. The forge **assembles** them.

No module knows about runtime behavior. No module validates another module. No module imports another module directly.

---

## CartridgeModule Contract

All modules inherit from the `CartridgeModule` abstract base class and must implement:

```python
class CartridgeModule(ABC):
    @classmethod
    @abstractmethod
    def module_name(cls) -> str: ...

    @classmethod
    @abstractmethod
    def module_schema_version(cls) -> int: ...

    @abstractmethod
    def to_dict(self) -> dict: ...

    @abstractmethod
    def validate(
        self,
    ) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]: ...
```

### Method Responsibilities

| Method                 | Returns                                          | Responsibility                              |
|------------------------|--------------------------------------------------|---------------------------------------------|
| `module_name()`        | `str`                                            | Unique module identifier                    |
| `module_schema_version()` | `int`                                         | Module-internal version (independent of cartridge schema) |
| `to_dict()`            | `dict`                                           | Serialize module state to JSON-compatible dict |
| `validate()`           | `tuple[list[Error], list[Warning]]`              | Validate own structural integrity           |

### Contract Rules

1. `module_name()` must return a unique, non-empty string.
2. `module_schema_version()` must return an integer >= 1.
3. `to_dict()` must return a JSON-compatible dict (no non-serializable types).
4. `validate()` must always return a 2-tuple of lists, never `None`.
5. Every element in the errors list must be a `CartridgeValidationError`.
6. Every element in the warnings list must be a `CartridgeValidationWarning`.
7. Validation must be deterministic — same state always produces same results.
8. The abstract class `CartridgeModule` itself cannot be instantiated.

---

## Module Identity

Module versions are **independent** of the cartridge schema version (`0.2.0`).

| Module               | `module_name`    | `module_schema_version` |
|----------------------|------------------|-------------------------|
| IdentityModule       | `identity`       | 1                       |
| CharacterModule      | `character`      | 1                       |
| PreferenceModule     | `preferences`    | 1                       |
| BehaviorModule       | `behavior`       | 1                       |
| CommunicationModule  | `communication`  | 1                       |

Module versions are simple integers, not semver strings. This keeps module evolution explicit — a version bump means the module's schema changed in a backward-incompatible way.

Future modules may evolve independently. A new field in the identity module would bump `IdentityModule.module_schema_version` to 2 without affecting any other module.

---

## Module Lifecycle

```
Construct
    │
    ▼
Validate
    │
    ▼
Freeze (dataclass frozen=True)
    │
    ▼
Serialize (to_dict)
    │
    ▼
Deserialize (from_dict)
    │
    ▼
Upgrade (future — cross-version migration)
    │
    ▼
Runtime (read-only)
```

### Lifecycle Rules

1. **Construct** — Module is created with all required fields. No default may violate the schema.
2. **Validate** — `validate()` checks structural integrity. Errors prevent forging. Warnings are advisory.
3. **Freeze** — All modules are frozen dataclasses. No field may be mutated after construction.
4. **Serialize** — `to_dict()` produces a portable representation. No module state is lost.
5. **Deserialize** — `CartridgeSerializer` reconstructs modules from dicts. Unknown fields in the source are ignored.
6. **Upgrade** — Reserved for future cross-version transformations. Not yet implemented.
7. **Runtime** — Modules are read-only. The runtime never mutates module state.

---

## Dependency Rules

### Hard Rules

- **Modules must NOT validate other modules.**
- **Modules must NOT mutate other modules.**
- **Modules must NOT inspect other modules.**
- **Modules must NOT import other modules directly.**

### Enforcement

These rules are enforced by convention and architecture review, not by runtime checks.

The module contract (`CartridgeModule`) provides no methods for accessing other modules, and no module receives a reference to any other module during construction, validation, or serialization.

The only entity that coordinates modules is `PersonaCartridge` (the composition container) and `CartridgeForge` (the assembly pipeline).

---

## Validation Contract

Every module returns the same validation structure:

```python
def validate(self) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
    errors: list[CartridgeValidationError] = []
    warnings: list[CartridgeValidationWarning] = []
    # ... module-specific logic ...
    return errors, warnings
```

### Rules

1. The return type is always a 2-tuple.
2. The first element is always `list[CartridgeValidationError]`.
3. The second element is always `list[CartridgeValidationWarning]`.
4. Errors indicate structural problems that prevent forging.
5. Warnings indicate advisory information that does not prevent forging.
6. No module invents its own validation response format.

### Validation Field Paths

Validation error/warning `field` values use dot-separated paths that identify module ownership:

- `identity.display_name`
- `character.core_values`
- `preferences.entries`
- `behavior.rules`

This ensures that error messages are unambiguous even in a composed cartridge.

---

## Serialization Contract

Each module owns serialization of its own state via `to_dict()`.

No module serializes another module. The `CartridgeSerializer` (in `app/services/serializer.py`) composes individual module dicts into the full cartridge dict.

### Rules

1. `to_dict()` returns a dict containing only the module's own fields.
2. Module dicts are nested under their `module_name()` key in the final cartridge output.
3. All modules are always serialized — reserved/empty modules are included.
4. No module performs global serialization.

---

## Registry

The `ModuleRegistry` provides a mapping of module name → metadata.

### Registry Entry

```python
@dataclass(frozen=True)
class ModuleRegistryEntry:
    module_type: type[CartridgeModule]
    module_schema_version: int
```

### Registry API

| Method                       | Returns                           | Description                              |
|------------------------------|-----------------------------------|------------------------------------------|
| `ModuleRegistry.lookup(name)`  | `ModuleRegistryEntry`            | Look up a module by name. Raises `KeyError` if unknown. |
| `ModuleRegistry.entries()`     | `dict[str, ModuleRegistryEntry]` | Return a copy of all registered entries. |
| `ModuleRegistry.names()`       | `list[str]`                      | Return sorted list of registered names.  |

### Registry Rules

1. Every module is registered at import time via `register_module()`.
2. Module names must be unique.
3. The registry is append-only — entries cannot be removed.
4. The registry returns defensive copies of its entries.

### Purpose

The registry exists to:
- Associate module names with their types and versions
- Enable future schema migrations by name lookup
- Provide introspection without coupling modules to each other
- Support tools and serializers that need to discover available modules

---

## Philosophy

### Independence

A cartridge is a collection of independent, versioned modules bound together by a stable contract. Modules are replaceable and testable in isolation.

### Composability

The cartridge composes modules. Modules never compose themselves. The forge is the only assembly point.

### Stability

Contracts are stable. Module versions evolve independently. The cartridge schema version (`0.2.0`) describes the wire format; module schema versions (int) describe internal module structure.

### Evolution

Future capabilities are added by introducing or evolving modules — never by changing the rules that govern them.

---

## Files

| File                              | Role                                    |
|-----------------------------------|-----------------------------------------|
| `app/models/cartridge.py`         | `CartridgeModule` ABC, module definitions, `ModuleRegistry` |
| `app/services/forge.py`           | Module assembly and validation          |
| `app/services/serializer.py`      | Module-aware serialize/deserialize      |
| `tests/test_forge.py`            | Contract compliance, registry, lifecycle tests |
