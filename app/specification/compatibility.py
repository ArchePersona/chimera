"""Compatibility and version negotiation for Persona Cartridge Specification."""

from __future__ import annotations

from typing import Any

from app.specification.version import SPECIFICATION_VERSION

SUPPORTED_SPECIFICATION_VERSIONS: frozenset[str] = frozenset({"1.0.0"})
DEPRECATED_SPECIFICATION_VERSIONS: frozenset[str] = frozenset()

# Upgrade path definitions: (source_spec_version, target_spec_version)
UPGRADE_PATHS: dict[tuple[str, str], str] = {
    # e.g., ("0.9.0", "1.0.0"): "upgrade_0_9_to_1_0"
}


def is_specification_supported(version: str) -> bool:
    """Check if the given specification version is supported."""
    return version in SUPPORTED_SPECIFICATION_VERSIONS


def is_specification_deprecated(version: str) -> bool:
    """Check if the given specification version is deprecated."""
    return version in DEPRECATED_SPECIFICATION_VERSIONS


def get_specification_compatibility_report(cartridge_or_version: Any) -> dict[str, Any]:
    """Generate a structured compatibility report for a given specification version or cartridge object."""
    if isinstance(cartridge_or_version, str):
        version = cartridge_or_version
    elif hasattr(cartridge_or_version, "manifest"):
        version = getattr(cartridge_or_version.manifest, "specification_version", "1.0.0")
    elif isinstance(cartridge_or_version, dict):
        manifest = cartridge_or_version.get("manifest", {})
        version = manifest.get("specification_version", "1.0.0") if isinstance(manifest, dict) else "1.0.0"
    else:
        version = "1.0.0"

    supported = is_specification_supported(version)
    deprecated = is_specification_deprecated(version)

    return {
        "specification_version": version,
        "canonical_specification_version": SPECIFICATION_VERSION,
        "supported": supported,
        "deprecated": deprecated,
        "supported_versions": sorted(list(SUPPORTED_SPECIFICATION_VERSIONS)),
        "deprecated_versions": sorted(list(DEPRECATED_SPECIFICATION_VERSIONS)),
        "upgrade_required": version != SPECIFICATION_VERSION and supported,
        "downgrade_supported": False,
        "negotiation_strategy": (
            "CHIMERA produces Persona Cartridges conforming strictly to Specification v1.0.0. "
            "Runtimes must inspect manifest.specification_version to verify compatibility before loading. "
            "Forward compatibility guarantees that future 1.x specification additions remain non-breaking."
        ),
    }
