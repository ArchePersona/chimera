"""Specification rules and prohibited fields for Persona Cartridge Specification v1.0.0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpecificationViolation:
    """Structured report of a single specification rule violation."""

    rule: str
    location: str
    reason: str
    recommendation: str


# Canonical required modules for Specification v1.0.0
REQUIRED_MODULES: tuple[str, ...] = (
    "identity",
    "character",
    "communication",
    "preferences",
    "behavior",
)

# Canonical rule identifier constants
RULE_REQUIRED_MANIFEST = "SPEC-001:REQUIRED_MANIFEST"
RULE_REQUIRED_MODULES = "SPEC-002:REQUIRED_MODULES"
RULE_PROHIBITED_RUNTIME_DATA = "SPEC-003:PROHIBITED_RUNTIME_DATA"
RULE_DETERMINISTIC_ORDERING = "SPEC-004:DETERMINISTIC_ORDERING"
RULE_IMMUTABLE_IDENTIFIERS = "SPEC-005:IMMUTABLE_IDENTIFIERS"
RULE_SPECIFICATION_VERSION = "SPEC-006:SPECIFICATION_VERSION"
RULE_SCHEMA_CONFORMANCE = "SPEC-007:SCHEMA_CONFORMANCE"

# Prohibited runtime information keys that must NEVER appear inside a cartridge
PROHIBITED_RUNTIME_KEYS: frozenset[str] = frozenset({
    "communication_state",
    "communication_states",
    "runtime_mode",
    "operational_mode",
    "mode",
    "tribunal_state",
    "tribunal",
    "drift_information",
    "drift_whisperer",
    "drift",
    "memories",
    "memory",
    "short_term_memory",
    "long_term_memory",
    "investigation_data",
    "investigation_history",
    "investigations",
    "conversation_history",
    "chat_history",
    "messages",
    "provider_metadata",
    "ai_provider",
    "llm_config",
    "token_statistics",
    "token_usage",
    "execution_timestamps",
    "last_execution_time",
    "runtime_confidence",
    "confidence_score",
})


def find_prohibited_runtime_keys(
    data: Any,
    current_path: str = "cartridge",
) -> list[SpecificationViolation]:
    """Recursively search for prohibited runtime state keys inside cartridge dict data."""
    violations: list[SpecificationViolation] = []

    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{current_path}.{key}" if current_path else key
            if key in PROHIBITED_RUNTIME_KEYS:
                violations.append(
                    SpecificationViolation(
                        rule=RULE_PROHIBITED_RUNTIME_DATA,
                        location=path,
                        reason=f"Prohibited runtime field '{key}' detected in authored cartridge",
                        recommendation=(
                            f"Remove '{key}' from cartridge data. Runtime execution state "
                            "must reside exclusively in the behavioral runtime."
                        ),
                    )
                )
            # Recurse into nested dictionaries or lists
            violations.extend(find_prohibited_runtime_keys(value, path))
    elif isinstance(data, (list, tuple)):
        for idx, item in enumerate(data):
            path = f"{current_path}[{idx}]"
            violations.extend(find_prohibited_runtime_keys(item, path))

    return violations
