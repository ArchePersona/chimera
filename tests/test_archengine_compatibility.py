import json

from app.integrations.archengine import (
    ARCHEngineCompatibilityShim,
    CartridgeDescriptorPayload,
    TranslationError,
)
from app.models.cartridge import (
    BehaviorModule,
    BehaviorPolicy,
    CartridgeStatus,
    PersonaCartridge,
    PersonaDraft,
    PreferenceEntry,
    PreferenceModule,
)
from app.models.projection import RuntimeProjectionBuilder
from app.services.forge import CartridgeForge
from app.services.serializer import CartridgeSerializer


# ===================================================================
# Helpers
# ===================================================================

def _make_valid_draft(**overrides) -> PersonaDraft:
    params = dict(
        name="Alex",
        identifier="alex",
        summary="A thoughtful guide",
        description="Optional description",
        aliases=["The Guide", "Alex the Great"],
        communication_style="Warm and direct",
        core_values=["Curiosity"],
        motivations=["To help others grow"],
        strengths=["Patience"],
        limitations=["Overthinking"],
        goals=["Inspire learning"],
        boundaries=["Never lie"],
        behavior_rules=["Ask before acting", "Be kind", "Cite sources"],
        preferences={"formality": "casual", "verbosity": "medium"},
    )
    params.update(overrides)
    return PersonaDraft(**params)


def _make_cartridge() -> PersonaCartridge:
    result = CartridgeForge.forge(_make_valid_draft())
    assert result.success is True
    assert result.cartridge is not None
    return result.cartridge


def _make_projection():
    return RuntimeProjectionBuilder.build(_make_cartridge())


def _make_flat_legacy_data() -> dict:
    return {
        "manifest": {
            "cartridge_id": "test-id-1234",
            "schema_name": "archepersona.chimera.persona-cartridge",
            "schema_version": "0.1.0",
            "created_at": "2026-07-19T12:00:00+00:00",
            "updated_at": "2026-07-19T12:00:00+00:00",
        },
        "name": "Alex",
        "identifier": "alex",
        "summary": "Guide",
        "description": "Optional",
        "communication_style": "Warm",
        "core_values": ["X"],
        "motivations": ["Y"],
        "strengths": ["Z"],
        "limitations": ["L"],
        "goals": ["G"],
        "boundaries": ["B"],
        "preferences": {"a": "1", "b": "2"},
        "behavior_rules": ["Be kind", "Ask before acting"],
        "extensions": {},
        "status": "forged",
    }


# ===================================================================
# Basic translation
# ===================================================================

class TestShimBasic:
    def test_translate_returns_payload(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert isinstance(payload, CartridgeDescriptorPayload)

    def test_deterministic_translation(self):
        p = _make_projection()
        p1 = ARCHEngineCompatibilityShim.translate(p)
        p2 = ARCHEngineCompatibilityShim.translate(p)
        assert p1 == p2

    def test_repeated_translation_identical(self):
        p = _make_projection()
        results = [
            ARCHEngineCompatibilityShim.translate(p) for _ in range(5)
        ]
        assert all(r == results[0] for r in results)


# ===================================================================
# Provenance
# ===================================================================

class TestShimProvenance:
    def test_cartridge_id_preserved(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.id == p.cartridge_id

    def test_schema_version_preserved(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.version == p.cartridge_schema_version

    def test_active_is_true(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.active is True


# ===================================================================
# Identity
# ===================================================================

class TestShimIdentity:
    def test_display_name_maps_to_name(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.name == p.display_name

    def test_identifier_in_chimera_metadata(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.metadata["chimera"]["identifier"] == p.identifier

    def test_summary_in_chimera_metadata(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.metadata["chimera"]["summary"] == p.summary

    def test_description_in_chimera_metadata(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.metadata["chimera"]["description"] == p.description

    def test_aliases_in_chimera_metadata(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.metadata["chimera"]["aliases"] == list(p.aliases)


# ===================================================================
# Character
# ===================================================================

class TestShimCharacter:
    def test_core_values_in_values(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.values["core_values"] == list(p.core_values)

    def test_motivations_in_values(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.values["motivations"] == list(p.motivations)

    def test_strengths_in_disposition(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.disposition["strengths"] == list(p.strengths)

    def test_limitations_in_disposition(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.disposition["limitations"] == list(p.limitations)

    def test_goals_in_disposition(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.disposition["goals"] == list(p.goals)

    def test_character_boundaries_in_disposition(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.disposition["boundaries"] == list(p.boundaries)


# ===================================================================
# Communication
# ===================================================================

class TestShimCommunication:
    def test_communication_style_maps_to_system_prompt(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.system_prompt == p.communication_style

    def test_system_prompt_none_when_empty(self):
        draft = _make_valid_draft(communication_style="")
        c = CartridgeForge.forge(draft).cartridge
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.system_prompt is None

    def test_tone_in_chimera_metadata(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.metadata["chimera"]["tone"] == list(p.tone)

    def test_communication_extras_in_chimera_metadata(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert "vocabulary_preferences" in payload.metadata["chimera"]
        assert "response_tendencies" in payload.metadata["chimera"]
        assert "formatting_preferences" in payload.metadata["chimera"]


# ===================================================================
# Preferences
# ===================================================================

class TestShimPreferences:
    def test_preferences_mapped_as_key_value(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        expected = {e.key: e.value for e in p.preferences}
        assert payload.preferences == expected

    def test_preferences_deterministic(self):
        p = _make_projection()
        p1 = ARCHEngineCompatibilityShim.translate(p)
        p2 = ARCHEngineCompatibilityShim.translate(p)
        assert p1.preferences == p2.preferences


# ===================================================================
# Behavior — enabled policies
# ===================================================================

class TestShimBehavior:
    def test_enabled_policies_in_boundaries(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        expected = [pol.to_dict() for pol in p.policies]
        assert payload.boundaries["policies"] == expected

    def test_disabled_policies_absent(self):
        draft = _make_valid_draft(behavior_rules=["Rule 1"])
        c = CartridgeForge.forge(draft).cartridge
        # Add a disabled policy
        policies = list(c.behavior.policies)
        disabled = BehaviorPolicy(
            identifier="deprecated", title="Deprecated", enabled=False,
        )
        modified = BehaviorModule(policies=tuple(policies) + (disabled,))
        c2 = PersonaCartridge(
            manifest=c.manifest,
            identity=c.identity,
            character=c.character,
            preferences=c.preferences,
            behavior=modified,
            communication=c.communication,
            status=CartridgeStatus.FORGED,
        )
        p = RuntimeProjectionBuilder.build(c2)
        payload = ARCHEngineCompatibilityShim.translate(p)
        ids = [pol["identifier"] for pol in payload.boundaries["policies"]]
        assert "deprecated" not in ids

    def test_no_policies_when_all_disabled(self):
        draft = _make_valid_draft(behavior_rules=["R"])
        c = CartridgeForge.forge(draft).cartridge
        all_disabled = tuple(
            BehaviorPolicy(identifier=pol.identifier, title=pol.title, enabled=False)
            for pol in c.behavior.policies
        )
        modified = BehaviorModule(policies=all_disabled)
        c2 = PersonaCartridge(
            manifest=c.manifest,
            identity=c.identity,
            character=c.character,
            preferences=c.preferences,
            behavior=modified,
            communication=c.communication,
            status=CartridgeStatus.FORGED,
        )
        p = RuntimeProjectionBuilder.build(c2)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert len(payload.boundaries["policies"]) == 0


# ===================================================================
# Error handling
# ===================================================================

class TestShimErrors:
    def test_empty_cartridge_id_raises(self):
        draft = _make_valid_draft()
        c = CartridgeForge.forge(draft).cartridge
        # Build a cartridge with empty ID
        from app.models.cartridge import CartridgeManifest
        bad_manifest = CartridgeManifest(
            cartridge_id="",
            schema_name=c.manifest.schema_name,
            schema_version=c.manifest.schema_version,
        )
        bad = PersonaCartridge(
            manifest=bad_manifest,
            identity=c.identity,
            character=c.character,
            preferences=c.preferences,
            behavior=c.behavior,
            communication=c.communication,
            status=CartridgeStatus.FORGED,
        )
        p = RuntimeProjectionBuilder.build(bad)
        import pytest
        with pytest.raises(TranslationError, match="cartridge_id"):
            ARCHEngineCompatibilityShim.translate(p)

    def test_empty_display_name_raises(self):
        draft = _make_valid_draft(name="")
        result = CartridgeForge.validate(draft)
        # Draft with empty name fails validation, so forge fails too.
        # Build manually to test the shim error directly.
        c = _make_cartridge()
        from app.models.cartridge import IdentityModule
        bad_identity = IdentityModule(
            display_name="",
            identifier=c.identity.identifier,
            summary=c.identity.summary,
        )
        bad = PersonaCartridge(
            manifest=c.manifest,
            identity=bad_identity,
            character=c.character,
            preferences=c.preferences,
            behavior=c.behavior,
            communication=c.communication,
            status=CartridgeStatus.FORGED,
        )
        p = RuntimeProjectionBuilder.build(bad)
        import pytest
        with pytest.raises(TranslationError, match="display_name"):
            ARCHEngineCompatibilityShim.translate(p)


# ===================================================================
# Isolation
# ===================================================================

class TestShimIsolation:
    def test_no_shared_mutable_references(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        d = payload.to_dict()
        d["name"] = "MUTATED"
        assert payload.name != "MUTATED"

    def test_source_projection_unchanged(self):
        p = _make_projection()
        original_id = p.cartridge_id
        ARCHEngineCompatibilityShim.translate(p)
        assert p.cartridge_id == original_id

    def test_payload_not_projection(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert not isinstance(payload, type(p))

    def test_payload_not_cartridge(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert not isinstance(payload, PersonaCartridge)


# ===================================================================
# Serialization
# ===================================================================

class TestShimSerialization:
    def test_to_dict_returns_dict(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        d = payload.to_dict()
        assert isinstance(d, dict)

    def test_serializable_to_json(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        d = payload.to_dict()
        text = json.dumps(d, ensure_ascii=False)
        restored = json.loads(text)
        assert restored["id"] == payload.id
        assert restored["name"] == payload.name

    def test_to_dict_includes_all_keys(self):
        p = _make_projection()
        payload = ARCHEngineCompatibilityShim.translate(p)
        d = payload.to_dict()
        expected_keys = {
            "id", "name", "version", "active", "system_prompt",
            "values", "disposition", "preferences", "boundaries", "metadata",
        }
        assert set(d) == expected_keys


# ===================================================================
# Compatibility — legacy upgrade chain
# ===================================================================

class TestShimCompatibility:
    def test_legacy_0_1_0_translates_identically(self):
        data = _make_flat_legacy_data()
        upgraded = CartridgeSerializer.deserialize(data)
        p_upgraded = RuntimeProjectionBuilder.build(upgraded)
        payload_upgraded = ARCHEngineCompatibilityShim.translate(p_upgraded)

        draft = PersonaDraft(
            name="Alex",
            identifier="alex",
            summary="Guide",
            description="Optional",
            communication_style="Warm",
            core_values=["X"],
            motivations=["Y"],
            strengths=["Z"],
            limitations=["L"],
            goals=["G"],
            boundaries=["B"],
            preferences={"a": "1", "b": "2"},
            behavior_rules=["Be kind", "Ask before acting"],
        )
        forged = CartridgeForge.forge(draft)
        assert forged.success is True
        p_forged = RuntimeProjectionBuilder.build(forged.cartridge)
        payload_forged = ARCHEngineCompatibilityShim.translate(p_forged)

        assert payload_upgraded.name == payload_forged.name
        assert payload_upgraded.version == payload_forged.version
        assert payload_upgraded.values == payload_forged.values
        assert payload_upgraded.disposition == payload_forged.disposition
        assert payload_upgraded.system_prompt == payload_forged.system_prompt

    def test_legacy_0_2_0_chain_translates(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.id is not None
        assert payload.name is not None

    def test_legacy_round_trip_translates(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        p1 = RuntimeProjectionBuilder.build(c)
        payload1 = ARCHEngineCompatibilityShim.translate(p1)

        serialized = CartridgeSerializer.serialize(c)
        c2 = CartridgeSerializer.deserialize(serialized)
        p2 = RuntimeProjectionBuilder.build(c2)
        payload2 = ARCHEngineCompatibilityShim.translate(p2)

        assert payload1 == payload2
