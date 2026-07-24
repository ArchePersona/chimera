"""Authoritative validator for Persona Cartridge Specification v1.0.0."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.cartridge import SCHEMA_NAME, SCHEMA_VERSION, PersonaCartridge
from app.specification.exceptions import SpecificationValidationError
from app.specification.rules import (
    REQUIRED_MODULES,
    RULE_DETERMINISTIC_ORDERING,
    RULE_IMMUTABLE_IDENTIFIERS,
    RULE_PROHIBITED_RUNTIME_DATA,
    RULE_REQUIRED_MANIFEST,
    RULE_REQUIRED_MODULES,
    RULE_SPECIFICATION_VERSION,
    SpecificationViolation,
    find_prohibited_runtime_keys,
)
from app.specification.schema import validate_json_schema
from app.specification.version import SPECIFICATION_VERSION

IDENTIFIER_REGEX = re.compile(r"^[a-z][a-z0-9_-]*$")
PREFERENCE_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
BEHAVIOR_ID_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@dataclass(frozen=True)
class SpecificationValidationResult:
    """Structured result returned by SpecificationValidator."""

    compliant: bool
    specification_version: str = SPECIFICATION_VERSION
    violations: list[SpecificationViolation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "compliant": self.compliant,
            "specification_version": self.specification_version,
            "violations": [asdict(v) for v in self.violations],
        }


class SpecificationValidator:
    """Validates Persona Cartridges against Specification v1.0.0 rules.

    The validator performs NO repair or mutation; it strictly checks compliance.
    """

    @classmethod
    def validate(
        cls,
        cartridge: PersonaCartridge | dict[str, Any],
    ) -> SpecificationValidationResult:
        """Validate a PersonaCartridge object or serialized dictionary.

        Returns a SpecificationValidationResult containing all detected violations.
        """
        violations: list[SpecificationViolation] = []

        if isinstance(cartridge, PersonaCartridge):
            data = cartridge.to_dict()
        elif isinstance(cartridge, dict):
            data = cartridge
        else:
            violations.append(
                SpecificationViolation(
                    rule=RULE_REQUIRED_MANIFEST,
                    location="cartridge",
                    reason=f"Invalid cartridge input type: expected PersonaCartridge or dict, got {type(cartridge).__name__}",
                    recommendation="Provide a valid PersonaCartridge instance or dictionary representation.",
                )
            )
            return SpecificationValidationResult(compliant=False, violations=violations)

        # 1. Manifest & Version checks
        manifest = data.get("manifest")
        if not isinstance(manifest, dict):
            violations.append(
                SpecificationViolation(
                    rule=RULE_REQUIRED_MANIFEST,
                    location="cartridge.manifest",
                    reason="Missing or invalid 'manifest' object in cartridge",
                    recommendation="Include a valid 'manifest' dictionary with cartridge_id, schema, and specification version.",
                )
            )
        else:
            cartridge_id = manifest.get("cartridge_id", "")
            if not cartridge_id or not isinstance(cartridge_id, str) or not cartridge_id.strip():
                violations.append(
                    SpecificationViolation(
                        rule=RULE_IMMUTABLE_IDENTIFIERS,
                        location="cartridge.manifest.cartridge_id",
                        reason="Missing or empty 'cartridge_id' in manifest",
                        recommendation="Assign a non-empty unique string or UUID to 'cartridge_id'.",
                    )
                )

            s_name = manifest.get("schema_name", "")
            if s_name != SCHEMA_NAME:
                violations.append(
                    SpecificationViolation(
                        rule=RULE_REQUIRED_MANIFEST,
                        location="cartridge.manifest.schema_name",
                        reason=f"Schema name mismatch: expected '{SCHEMA_NAME}', got '{s_name}'",
                        recommendation=f"Set 'schema_name' to '{SCHEMA_NAME}'.",
                    )
                )

            s_ver = manifest.get("schema_version", "")
            if s_ver != SCHEMA_VERSION:
                violations.append(
                    SpecificationViolation(
                        rule=RULE_REQUIRED_MANIFEST,
                        location="cartridge.manifest.schema_version",
                        reason=f"Schema version mismatch: expected '{SCHEMA_VERSION}', got '{s_ver}'",
                        recommendation=f"Set 'schema_version' to '{SCHEMA_VERSION}'.",
                    )
                )

            spec_ver = manifest.get("specification_version", "")
            if spec_ver != SPECIFICATION_VERSION:
                violations.append(
                    SpecificationViolation(
                        rule=RULE_SPECIFICATION_VERSION,
                        location="cartridge.manifest.specification_version",
                        reason=f"Specification version mismatch: expected '{SPECIFICATION_VERSION}', got '{spec_ver}'",
                        recommendation=f"Set 'specification_version' to '{SPECIFICATION_VERSION}'.",
                    )
                )

        # 2. Required Modules check
        for mod_name in REQUIRED_MODULES:
            if mod_name not in data or not isinstance(data[mod_name], dict):
                violations.append(
                    SpecificationViolation(
                        rule=RULE_REQUIRED_MODULES,
                        location=f"cartridge.{mod_name}",
                        reason=f"Required module '{mod_name}' is missing or invalid",
                        recommendation=f"Ensure the '{mod_name}' module is present and properly forged.",
                    )
                )

        # Validate Identity fields if present
        identity = data.get("identity")
        if isinstance(identity, dict):
            identifier = identity.get("identifier", "")
            if not identifier or not isinstance(identifier, str):
                violations.append(
                    SpecificationViolation(
                        rule=RULE_IMMUTABLE_IDENTIFIERS,
                        location="cartridge.identity.identifier",
                        reason="Missing or empty persona identifier in identity module",
                        recommendation="Provide a valid persona identifier string.",
                    )
                )
            elif not IDENTIFIER_REGEX.match(identifier):
                violations.append(
                    SpecificationViolation(
                        rule=RULE_IMMUTABLE_IDENTIFIERS,
                        location="cartridge.identity.identifier",
                        reason=f"Identifier '{identifier}' violates syntax rules (lowercase letter start, [a-z0-9_-])",
                        recommendation="Normalize identifier to start with a letter and contain only lowercase alphanumeric, underscore, or hyphen.",
                    )
                )

            display_name = identity.get("display_name", "")
            if not display_name or not isinstance(display_name, str) or not display_name.strip():
                violations.append(
                    SpecificationViolation(
                        rule=RULE_REQUIRED_MODULES,
                        location="cartridge.identity.display_name",
                        reason="Missing or empty 'display_name' in identity module",
                        recommendation="Provide a non-empty display_name.",
                    )
                )

            summary = identity.get("summary", "")
            if not summary or not isinstance(summary, str) or not summary.strip():
                violations.append(
                    SpecificationViolation(
                        rule=RULE_REQUIRED_MODULES,
                        location="cartridge.identity.summary",
                        reason="Missing or empty 'summary' in identity module",
                        recommendation="Provide a non-empty summary.",
                    )
                )

        # 3. Prohibited Runtime Data check
        runtime_violations = find_prohibited_runtime_keys(data)
        violations.extend(runtime_violations)

        # 4. Deterministic Ordering check
        preferences = data.get("preferences")
        if isinstance(preferences, dict) and "entries" in preferences:
            entries = preferences["entries"]
            if isinstance(entries, list):
                keys = [e.get("key") for e in entries if isinstance(e, dict)]
                sorted_keys = sorted(keys)
                if keys != sorted_keys:
                    violations.append(
                        SpecificationViolation(
                            rule=RULE_DETERMINISTIC_ORDERING,
                            location="cartridge.preferences.entries",
                            reason="Preference entries are not deterministically sorted by key",
                            recommendation="Ensure preference entries are sorted alphabetically by key.",
                        )
                    )

        behavior = data.get("behavior")
        if isinstance(behavior, dict) and "policies" in behavior:
            policies = behavior["policies"]
            if isinstance(policies, list):
                b_ids = [p.get("identifier") for p in policies if isinstance(p, dict)]
                if len(b_ids) != len(set(b_ids)):
                    violations.append(
                        SpecificationViolation(
                            rule=RULE_DETERMINISTIC_ORDERING,
                            location="cartridge.behavior.policies",
                            reason="Behavior policies contain duplicate policy identifiers",
                            recommendation="Ensure all behavior policy identifiers are unique.",
                        )
                    )

        # 5. Schema Validation
        schema_violations = validate_json_schema(data)
        violations.extend(schema_violations)

        compliant = len(violations) == 0
        return SpecificationValidationResult(
            compliant=compliant,
            specification_version=SPECIFICATION_VERSION,
            violations=violations,
        )

    @classmethod
    def validate_or_raise(cls, cartridge: PersonaCartridge | dict[str, Any]) -> None:
        """Validate a cartridge and raise SpecificationValidationError if non-compliant."""
        result = cls.validate(cartridge)
        if not result.compliant:
            raise SpecificationValidationError(result.violations)
