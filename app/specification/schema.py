"""JSON schema interface for Persona Cartridge Specification v1.0.0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.specification.rules import (
    RULE_SCHEMA_CONFORMANCE,
    SpecificationViolation,
)

SCHEMA_FILE_PATH = Path(__file__).resolve().parent.parent.parent / "schemas" / "persona-cartridge-1.0.0.json"


def get_canonical_json_schema() -> dict[str, Any]:
    """Load and return the canonical JSON Schema for Persona Cartridge Specification v1.0.0."""
    if not SCHEMA_FILE_PATH.exists():
        raise FileNotFoundError(f"Canonical schema file not found at: {SCHEMA_FILE_PATH}")

    with open(SCHEMA_FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_json_schema(cartridge_dict: dict[str, Any]) -> list[SpecificationViolation]:
    """Validate a serialized cartridge dictionary against the canonical JSON Schema.

    Returns a list of SpecificationViolation instances for any schema discrepancies.
    """
    violations: list[SpecificationViolation] = []
    try:
        import jsonschema

        schema = get_canonical_json_schema()
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(cartridge_dict))

        for err in errors:
            path = ".".join(str(p) for p in err.absolute_path) or "cartridge"
            violations.append(
                SpecificationViolation(
                    rule=RULE_SCHEMA_CONFORMANCE,
                    location=path,
                    reason=f"JSON Schema validation error: {err.message}",
                    recommendation=f"Ensure '{path}' conforms to the canonical JSON schema specification.",
                )
            )
    except ImportError:
        # Fallback structural checks if jsonschema library is not installed
        schema = get_canonical_json_schema()
        required_top = schema.get("required", [])
        for req in required_top:
            if req not in cartridge_dict:
                violations.append(
                    SpecificationViolation(
                        rule=RULE_SCHEMA_CONFORMANCE,
                        location=f"cartridge.{req}",
                        reason=f"Missing required top-level key '{req}'",
                        recommendation=f"Provide required key '{req}' in cartridge dictionary.",
                    )
                )

    return violations
