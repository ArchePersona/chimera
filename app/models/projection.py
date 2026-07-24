from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.cartridge import (
    BehaviorPolicy,
    PersonaCartridge,
    PersonaStateModulation,
    PreferenceEntry,
)


@dataclass(frozen=True)
class RuntimePersonaProjection:
    """Read-only runtime view of a PersonaCartridge.

    The runtime never consumes the cartridge directly.
    It consumes this deterministic projection.

    The projection owns no authored data.
    The cartridge remains immutable.
    """

    # Provenance
    cartridge_id: str
    cartridge_schema_version: str

    # Identity
    identifier: str
    display_name: str
    summary: str
    description: str
    aliases: tuple[str, ...]

    # Character
    core_values: tuple[str, ...]
    motivations: tuple[str, ...]
    strengths: tuple[str, ...]
    limitations: tuple[str, ...]
    goals: tuple[str, ...]
    boundaries: tuple[str, ...]

    # Communication (reserved legacy data excluded)
    communication_style: str
    tone: tuple[str, ...]
    vocabulary_preferences: tuple[str, ...]
    response_tendencies: tuple[str, ...]
    formatting_preferences: tuple[str, ...]

    # Preferences (stable deterministic ordering)
    preferences: tuple[PreferenceEntry, ...]

    # Behavior (enabled policies only)
    policies: tuple[BehaviorPolicy, ...]

    # State modulations (state_id → modulation)
    state_modulations: dict[str, PersonaStateModulation]

    def to_dict(self) -> dict[str, Any]:
        """Optional one-way serialization.

        Serializes only the projection.
        Never serialize back into a cartridge format.
        """
        d: dict[str, Any] = {
            "cartridge_id": self.cartridge_id,
            "cartridge_schema_version": self.cartridge_schema_version,
            "identifier": self.identifier,
            "display_name": self.display_name,
            "summary": self.summary,
            "description": self.description,
            "aliases": list(self.aliases),
            "core_values": list(self.core_values),
            "motivations": list(self.motivations),
            "strengths": list(self.strengths),
            "limitations": list(self.limitations),
            "goals": list(self.goals),
            "boundaries": list(self.boundaries),
            "communication_style": self.communication_style,
            "tone": list(self.tone),
            "vocabulary_preferences": list(self.vocabulary_preferences),
            "response_tendencies": list(self.response_tendencies),
            "formatting_preferences": list(self.formatting_preferences),
            "preferences": [e.to_dict() for e in self.preferences],
            "policies": [p.to_dict() for p in self.policies],
        }
        if self.state_modulations:
            d["state_modulations"] = {
                state_id: mod.to_dict()
                for state_id, mod in sorted(self.state_modulations.items())
            }
        return d


class RuntimeProjectionBuilder:
    """Builder that creates RuntimePersonaProjection from a PersonaCartridge.

    The cartridge is the source of truth.
    The runtime consumes a deterministic projection.
    The projection owns no authored data.
    """

    @staticmethod
    def build(cartridge: PersonaCartridge) -> RuntimePersonaProjection:
        """Build a read-only projection from an authored cartridge.

        Only enabled behavior policies are included.
        Reserved legacy communication data is excluded.
        """
        enabled = tuple(
            p for p in sorted(cartridge.behavior.policies, key=lambda x: x.identifier) if p.enabled
        )

        return RuntimePersonaProjection(
            cartridge_id=cartridge.manifest.cartridge_id,
            cartridge_schema_version=cartridge.manifest.schema_version,
            identifier=cartridge.identity.identifier,
            display_name=cartridge.identity.display_name,
            summary=cartridge.identity.summary,
            description=cartridge.identity.description,
            aliases=cartridge.identity.aliases,
            core_values=cartridge.character.core_values,
            motivations=cartridge.character.motivations,
            strengths=cartridge.character.strengths,
            limitations=cartridge.character.limitations,
            goals=cartridge.character.goals,
            boundaries=cartridge.character.boundaries,
            communication_style=cartridge.communication.communication_style,
            tone=cartridge.communication.tone,
            vocabulary_preferences=cartridge.communication.vocabulary_preferences,
            response_tendencies=cartridge.communication.response_tendencies,
            formatting_preferences=cartridge.communication.formatting_preferences,
            preferences=cartridge.preferences.entries,
            policies=enabled,
            state_modulations=dict(cartridge.state_modulations),
        )
