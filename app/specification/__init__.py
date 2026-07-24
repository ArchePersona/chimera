"""Persona Cartridge Specification package for CHIMERA."""

from app.specification.compatibility import (
    DEPRECATED_SPECIFICATION_VERSIONS,
    SUPPORTED_SPECIFICATION_VERSIONS,
    get_specification_compatibility_report,
    is_specification_deprecated,
    is_specification_supported,
)
from app.specification.exceptions import (
    SpecificationError,
    SpecificationValidationError,
    SpecificationVersionError,
)
from app.specification.rules import (
    PROHIBITED_RUNTIME_KEYS,
    REQUIRED_MODULES,
    SpecificationViolation,
)
from app.specification.schema import (
    get_canonical_json_schema,
    validate_json_schema,
)
from app.specification.validator import (
    SpecificationValidationResult,
    SpecificationValidator,
)
from app.specification.version import (
    SPECIFICATION_NAME,
    SPECIFICATION_SCHEMA_URI,
    SPECIFICATION_VERSION,
)

__all__ = [
    "SPECIFICATION_NAME",
    "SPECIFICATION_VERSION",
    "SPECIFICATION_SCHEMA_URI",
    "SpecificationValidator",
    "SpecificationValidationResult",
    "SpecificationViolation",
    "SpecificationError",
    "SpecificationValidationError",
    "SpecificationVersionError",
    "REQUIRED_MODULES",
    "PROHIBITED_RUNTIME_KEYS",
    "SUPPORTED_SPECIFICATION_VERSIONS",
    "DEPRECATED_SPECIFICATION_VERSIONS",
    "is_specification_supported",
    "is_specification_deprecated",
    "get_specification_compatibility_report",
    "get_canonical_json_schema",
    "validate_json_schema",
]
