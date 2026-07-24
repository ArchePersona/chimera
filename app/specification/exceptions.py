"""Exceptions for Persona Cartridge Specification validation and compatibility."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.specification.rules import SpecificationViolation


class SpecificationError(Exception):
    """Base exception for all specification-related errors."""


class SpecificationVersionError(SpecificationError):
    """Raised when an unsupported or invalid specification version is encountered."""

    def __init__(self, version: str, supported: set[str] | frozenset[str]) -> None:
        self.version = version
        self.supported = supported
        super().__init__(
            f"Unsupported specification version '{version}'. "
            f"Supported versions: {', '.join(sorted(supported))}"
        )


class SpecificationValidationError(SpecificationError):
    """Raised when specification validation fails for a cartridge."""

    def __init__(
        self,
        violations: list[SpecificationViolation],
        message: str = "",
    ) -> None:
        self.violations = violations
        if not message:
            message = f"Specification validation failed with {len(violations)} violation(s)"
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "SpecificationValidationError",
            "message": str(self),
            "violations": [
                {
                    "rule": v.rule,
                    "location": v.location,
                    "reason": v.reason,
                    "recommendation": v.recommendation,
                }
                for v in self.violations
            ],
        }
