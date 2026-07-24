from __future__ import annotations

import copy
from datetime import datetime, timezone

from app.models.cartridge import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    BehaviorModule,
    BehaviorPolicy,
    CartridgeManifest,
    CartridgeStatus,
    CharacterModule,
    CommunicationModule,
    IdentityModule,
    PersonaCartridge,
    PersonaStateModulation,
    PreferenceEntry,
    PreferenceModule,
    UnsupportedVersionError,
    generate_behavior_identifiers,
    is_version_supported,
)


class CartridgeSerializer:
    """Version-aware serializer/deserializer for PersonaCartridge.

    Serializes:  always 0.6.0 compositional format.
    Deserializes: 0.1.0 flat, 0.2.0, 0.3.0, 0.4.0, 0.5.0, and 0.6.0 nested.
    """

    SUPPORTED_VERSIONS: frozenset[str] = frozenset({
        "0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0", "0.6.0",
    })

    # ------------------------------------------------------------------
    # Serialize
    # ------------------------------------------------------------------

    @classmethod
    def serialize(cls, cartridge: PersonaCartridge) -> dict:
        return cartridge.to_dict()

    # ------------------------------------------------------------------
    # Deserialize
    # ------------------------------------------------------------------

    @classmethod
    def deserialize(cls, data: dict) -> PersonaCartridge:
        manifest_data = data.get("manifest")
        if not isinstance(manifest_data, dict):
            raise ValueError("Cartridge data must contain a 'manifest' object")

        version = manifest_data.get("schema_version", "")
        if not is_version_supported(version, cls.SUPPORTED_VERSIONS):
            raise UnsupportedVersionError(version, cls.SUPPORTED_VERSIONS)

        # Upgrade chain: 0.1.0 → 0.2.0 → 0.3.0 → 0.4.0 → 0.5.0 → 0.6.0
        if version == "0.1.0":
            data = cls._upgrade_0_1_to_0_2(data, manifest_data)
            data = cls._upgrade_0_2_to_0_3(data)
            data = cls._upgrade_0_3_to_0_4(data)
            data = cls._upgrade_0_4_to_0_5(data)
            data = cls._upgrade_0_5_to_0_6(data)
        elif version == "0.2.0":
            data = cls._upgrade_0_2_to_0_3(data)
            data = cls._upgrade_0_3_to_0_4(data)
            data = cls._upgrade_0_4_to_0_5(data)
            data = cls._upgrade_0_5_to_0_6(data)
        elif version == "0.3.0":
            data = cls._upgrade_0_3_to_0_4(data)
            data = cls._upgrade_0_4_to_0_5(data)
            data = cls._upgrade_0_5_to_0_6(data)
        elif version == "0.4.0":
            data = cls._upgrade_0_4_to_0_5(data)
            data = cls._upgrade_0_5_to_0_6(data)
        elif version == "0.5.0":
            data = cls._upgrade_0_5_to_0_6(data)

        manifest = CartridgeManifest(
            cartridge_id=data["manifest"]["cartridge_id"],
            schema_name=data["manifest"].get("schema_name", SCHEMA_NAME),
            schema_version=SCHEMA_VERSION,
            specification_version=data["manifest"].get("specification_version", "1.0.0"),
            created_at=_parse_dt(data["manifest"].get("created_at")),
            updated_at=_parse_dt(data["manifest"].get("updated_at")),
        )

        identity = cls._deserialize_identity(data)
        character = cls._deserialize_character(data)
        preferences = cls._deserialize_preferences(data)
        behavior = cls._deserialize_behavior(data)
        communication = cls._deserialize_communication(data)

        state_modulations = cls._deserialize_state_modulations(data)

        return PersonaCartridge(
            manifest=manifest,
            identity=identity,
            character=character,
            preferences=preferences,
            behavior=behavior,
            communication=communication,
            state_modulations=state_modulations,
            status=CartridgeStatus(data.get("status", "forged")),
            extensions=copy.deepcopy(data.get("extensions", {})),
        )

    # ------------------------------------------------------------------
    # Upgrade 0.1.0 → 0.2.0
    # ------------------------------------------------------------------

    @classmethod
    def _upgrade_0_1_to_0_2(cls, data: dict, manifest: dict) -> dict:
        """Restructure a legacy flat cartridge dict into 0.2.0 compositional format."""
        return {
            "manifest": {**manifest, "schema_version": "0.2.0"},
            "identity": {
                "display_name": data.get("name", ""),
                "identifier": data.get("identifier", ""),
                "summary": data.get("summary", ""),
                "description": data.get("description", ""),
                "aliases": list(data.get("aliases", ())),
            },
            "character": {
                "communication_style": data.get("communication_style", ""),
                "core_values": list(data.get("core_values", ())),
                "motivations": list(data.get("motivations", ())),
                "strengths": list(data.get("strengths", ())),
                "limitations": list(data.get("limitations", ())),
                "goals": list(data.get("goals", ())),
                "boundaries": list(data.get("boundaries", ())),
            },
            "preferences": {"entries": dict(data.get("preferences", {}))},
            "behavior": {"rules": list(data.get("behavior_rules", ()))},
            "communication": {},
            "extensions": copy.deepcopy(data.get("extensions", {})),
            "status": data.get("status", "forged"),
        }

    # ------------------------------------------------------------------
    # Upgrade 0.2.0 → 0.3.0
    # ------------------------------------------------------------------

    @classmethod
    def _upgrade_0_2_to_0_3(cls, data: dict) -> dict:
        """Migrate character.communication_style → communication.reserved.

        Character no longer owns communication_style.
        Preserve it as reserved archival data in the communication module.
        """
        character = data.get("character", {})
        comm_style = character.get("communication_style", "")

        reserved: dict[str, dict] = {}
        if comm_style:
            reserved["communication_style"] = {"value": comm_style}

        # Remove from character, add to communication
        result = copy.deepcopy(data)
        character_out = dict(result.get("character", {}))
        character_out.pop("communication_style", None)
        result["character"] = character_out
        result["communication"] = {"reserved": reserved}
        result["manifest"] = dict(result.get("manifest", {}))
        result["manifest"]["schema_version"] = "0.3.0"
        return result

    # ------------------------------------------------------------------
    # Upgrade 0.3.0 → 0.4.0
    # ------------------------------------------------------------------

    @classmethod
    def _upgrade_0_3_to_0_4(cls, data: dict) -> dict:
        """Migrate communication.reserved → formal communication fields.

        The reserved communication_style becomes a first-class field.
        No authored information may be lost.
        """
        result = copy.deepcopy(data)
        comm = dict(result.get("communication", {}))
        reserved = comm.get("reserved", {})

        # Migrate reserved communication_style
        cs_entry = reserved.get("communication_style", {})
        if isinstance(cs_entry, dict):
            cs_value = cs_entry.get("value", "")
            if cs_value and not comm.get("communication_style"):
                comm["communication_style"] = cs_value

        # Remove reserved block if empty after migration
        remaining = {k: v for k, v in reserved.items() if k != "communication_style"}
        if remaining:
            comm["reserved"] = remaining
        else:
            comm.pop("reserved", None)

        result["communication"] = comm
        result["manifest"] = dict(result.get("manifest", {}))
        result["manifest"]["schema_version"] = SCHEMA_VERSION
        return result

    # ------------------------------------------------------------------
    # Upgrade 0.4.0 → 0.5.0
    # ------------------------------------------------------------------

    @classmethod
    def _upgrade_0_4_to_0_5(cls, data: dict) -> dict:
        """Migrate legacy key/value preference entries → PreferenceEntry list.

        Each legacy entry gets defaults: scope=global, priority=normal, description=''.
        Sorted by key.
        """
        result = copy.deepcopy(data)
        raw = result.get("preferences", {})
        entries_data = raw.get("entries", {})
        if isinstance(entries_data, dict):
            new_entries = [
                {"key": k, "value": v, "scope": "global", "priority": "normal", "description": ""}
                for k, v in sorted(entries_data.items())
            ]
            result["preferences"] = {"entries": new_entries}
        result["manifest"] = dict(result.get("manifest", {}))
        result["manifest"]["schema_version"] = SCHEMA_VERSION
        return result

    # ------------------------------------------------------------------
    # Upgrade 0.5.0 → 0.6.0
    # ------------------------------------------------------------------

    @classmethod
    def _upgrade_0_5_to_0_6(cls, data: dict) -> dict:
        """Migrate legacy placeholder rules → BehaviorPolicy list.

        Each legacy rule becomes a BehaviorPolicy:
          identifier = normalized rule (lowercase with underscores)
          title = original rule
          description = ""
          category = "interaction"
          policy_type = "preferred"
          enabled = True
        Sorted by identifier.
        """
        result = copy.deepcopy(data)
        raw = result.get("behavior", {})
        rules_data = raw.get("rules", [])
        if isinstance(rules_data, list) and rules_data:
            identifiers = generate_behavior_identifiers(rules_data)
            new_policies = [
                {
                    "identifier": identifiers[i],
                    "title": rules_data[i].strip(),
                    "description": "",
                    "category": "interaction",
                    "policy_type": "preferred",
                    "enabled": True,
                }
                for i in range(len(rules_data))
            ]
            new_policies.sort(key=lambda p: p["identifier"])
            result["behavior"] = {"policies": new_policies}
        elif isinstance(rules_data, list):
            result["behavior"] = {"policies": []}
        result["manifest"] = dict(result.get("manifest", {}))
        result["manifest"]["schema_version"] = SCHEMA_VERSION
        return result

    # ------------------------------------------------------------------
    # Module deserializers (0.6.0 nested format)
    # ------------------------------------------------------------------

    @classmethod
    def _deserialize_identity(cls, data: dict) -> IdentityModule:
        raw = data.get("identity", {})
        return IdentityModule(
            display_name=raw.get("display_name", ""),
            identifier=raw.get("identifier", ""),
            summary=raw.get("summary", ""),
            description=raw.get("description", ""),
            aliases=tuple(raw.get("aliases", ())),
        )

    @classmethod
    def _deserialize_character(cls, data: dict) -> CharacterModule:
        raw = data.get("character", {})
        return CharacterModule(
            core_values=tuple(raw.get("core_values", ())),
            motivations=tuple(raw.get("motivations", ())),
            strengths=tuple(raw.get("strengths", ())),
            limitations=tuple(raw.get("limitations", ())),
            goals=tuple(raw.get("goals", ())),
            boundaries=tuple(raw.get("boundaries", ())),
        )

    @classmethod
    def _deserialize_preferences(cls, data: dict) -> PreferenceModule:
        raw = data.get("preferences", {})
        entries_data = raw.get("entries", raw)
        if isinstance(entries_data, list):
            entries = tuple(
                PreferenceEntry(
                    key=e["key"],
                    value=e["value"],
                    scope=e.get("scope", "global"),
                    priority=e.get("priority", "normal"),
                    description=e.get("description", ""),
                )
                for e in entries_data
            )
            return PreferenceModule(entries=entries)
        if isinstance(entries_data, dict):
            entries = tuple(
                PreferenceEntry(key=k, value=v)
                for k, v in sorted(entries_data.items())
            )
            return PreferenceModule(entries=entries)
        return PreferenceModule()

    @classmethod
    def _deserialize_behavior(cls, data: dict) -> BehaviorModule:
        raw = data.get("behavior", {})
        policies_data = raw.get("policies", None)
        if policies_data is not None and isinstance(policies_data, list):
            policies = tuple(
                BehaviorPolicy(
                    identifier=p["identifier"],
                    title=p["title"],
                    description=p.get("description", ""),
                    category=p.get("category", "interaction"),
                    policy_type=p.get("policy_type", "preferred"),
                    enabled=p.get("enabled", True),
                )
                for p in policies_data
            )
            return BehaviorModule(policies=policies)
        rules_data = raw.get("rules", [])
        if isinstance(rules_data, list):
            identifiers = generate_behavior_identifiers(rules_data)
            policies = tuple(
                BehaviorPolicy(
                    identifier=identifiers[i],
                    title=r.strip(),
                )
                for i, r in enumerate(rules_data)
            )
            return BehaviorModule(policies=policies)
        return BehaviorModule()

    @classmethod
    def _deserialize_communication(cls, data: dict) -> CommunicationModule:
        raw = data.get("communication", {})
        reserved_raw = raw.get("reserved", {})
        reserved: dict[str, dict] = {}
        for k, v in reserved_raw.items():
            if isinstance(v, dict):
                reserved[k] = dict(v)
        return CommunicationModule(
            communication_style=raw.get("communication_style", ""),
            tone=tuple(raw.get("tone", ())),
            vocabulary_preferences=tuple(raw.get("vocabulary_preferences", ())),
            response_tendencies=tuple(raw.get("response_tendencies", ())),
            formatting_preferences=tuple(raw.get("formatting_preferences", ())),
            reserved=reserved,
        )


    @classmethod
    def _deserialize_state_modulations(cls, data: dict) -> dict[str, PersonaStateModulation]:
        raw = data.get("state_modulations")
        if not isinstance(raw, dict):
            return {}
        modulations: dict[str, PersonaStateModulation] = {}
        for state_id, mod_data in raw.items():
            if not isinstance(state_id, str) or not isinstance(mod_data, dict):
                continue
            modulations[state_id] = PersonaStateModulation(
                voice_texture=tuple(mod_data.get("voice_texture", ())),
                signature_phrasing=tuple(mod_data.get("signature_phrasing", ())),
                preferred_moves=tuple(mod_data.get("preferred_moves", ())),
                forbidden_moves=tuple(mod_data.get("forbidden_moves", ())),
                lexical_bias=tuple(mod_data.get("lexical_bias", ())),
                metaphor_bias=tuple(mod_data.get("metaphor_bias", ())),
                humor_boundary=mod_data.get("humor_boundary"),
                warmth_boundary=mod_data.get("warmth_boundary"),
            )
        return modulations


def _parse_dt(raw) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        return datetime.fromisoformat(raw)
    return datetime.now(timezone.utc)
