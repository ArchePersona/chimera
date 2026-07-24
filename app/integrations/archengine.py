from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.projection import RuntimePersonaProjection

# Compatibility layer version — bump when the shim's mapping contract changes.
CHIMERA_COMPATIBILITY_VERSION = "1.0"


class TranslationError(Exception):
    """Raised when a projection cannot be translated to an ARCHEngine payload."""


@dataclass(frozen=True)
class CartridgeDescriptorPayload:
    """Isolated, serializable payload matching the ARCHEngine CartridgeDescriptor contract.

    This type is owned by the compatibility shim, not by ARCHEngine itself.
    It is designed to be serialized and transferred across package/API/file boundaries
    without introducing ARCHEngine dependencies into CHIMERA's core models.
    """

    id: str
    name: str | None
    version: str
    active: bool
    system_prompt: str | None
    values: dict[str, Any]
    disposition: dict[str, Any]
    preferences: dict[str, Any]
    boundaries: dict[str, Any]
    state_modulations: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "active": self.active,
            "system_prompt": self.system_prompt,
            "values": dict(self.values),
            "disposition": dict(self.disposition),
            "preferences": dict(self.preferences),
            "boundaries": dict(self.boundaries),
            "metadata": dict(self.metadata),
        }
        if self.state_modulations:
            d["state_modulations"] = dict(self.state_modulations)
        return d


class ARCHEngineCompatibilityShim:
    """Narrow translation layer from CHIMERA RuntimePersonaProjection to ARCHEngine.

    The shim performs translation only:
      - deterministic
      - no execution
      - no validation
      - no mutation of the source projection
      - no ARCHEngine runtime code imported into CHIMERA
    """

    @staticmethod
    def translate(projection: RuntimePersonaProjection) -> CartridgeDescriptorPayload:
        if not projection.cartridge_id:
            raise TranslationError(
                "Cannot translate projection: cartridge_id is empty"
            )
        if not projection.display_name:
            raise TranslationError(
                "Cannot translate projection: display_name is empty"
            )

        values: dict[str, Any] = {
            "core_values": list(projection.core_values),
            "motivations": list(projection.motivations),
        }

        disposition: dict[str, Any] = {
            "strengths": list(projection.strengths),
            "limitations": list(projection.limitations),
            "goals": list(projection.goals),
            "boundaries": list(projection.boundaries),
        }

        prefs: dict[str, Any] = {
            e.key: e.value for e in projection.preferences
        }

        policies = [p.to_dict() for p in projection.policies]

        boundaries: dict[str, Any] = {
            "policies": policies,
        }

        chimera_meta: dict[str, Any] = {
            "identifier": projection.identifier,
            "summary": projection.summary,
            "description": projection.description,
            "aliases": list(projection.aliases),
            "tone": list(projection.tone),
            "vocabulary_preferences": list(projection.vocabulary_preferences),
            "response_tendencies": list(projection.response_tendencies),
            "formatting_preferences": list(projection.formatting_preferences),
        }

        metadata: dict[str, Any] = {
            "chimera": chimera_meta,
        }

        system_prompt: str | None = (
            projection.communication_style
            if projection.communication_style
            else None
        )

        state_modulations: dict[str, Any] = {
            state_id: mod.to_dict()
            for state_id, mod in sorted(projection.state_modulations.items())
        }

        return CartridgeDescriptorPayload(
            id=projection.cartridge_id,
            name=projection.display_name,
            version=projection.cartridge_schema_version,
            active=True,
            system_prompt=system_prompt,
            values=values,
            disposition=disposition,
            preferences=prefs,
            boundaries=boundaries,
            state_modulations=state_modulations,
            metadata=metadata,
        )
