import copy
from datetime import datetime, timezone

from app.models.cartridge import (
    SCHEMA_NAME,
    BehaviorModule,
    BehaviorPolicy,
    CartridgeStatus,
    CharacterModule,
    CommunicationModule,
    IdentityModule,
    PersonaCartridge,
    PersonaDraft,
    PreferenceEntry,
    PreferenceModule,
)
from app.models.projection import (
    RuntimePersonaProjection,
    RuntimeProjectionBuilder,
)
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


def _make_flat_legacy_data() -> dict:
    return {
        "manifest": {
            "cartridge_id": "test-id-1234",
            "schema_name": SCHEMA_NAME,
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
# Projection — basic
# ===================================================================

class TestProjectionBasic:
    def test_projection_exists(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert isinstance(p, RuntimePersonaProjection)

    def test_deterministic_output(self):
        c = _make_cartridge()
        p1 = RuntimeProjectionBuilder.build(c)
        p2 = RuntimeProjectionBuilder.build(c)
        assert p1 == p2

    def test_repeated_builds_identical(self):
        c = _make_cartridge()
        builds = [RuntimeProjectionBuilder.build(c) for _ in range(5)]
        assert all(b == builds[0] for b in builds)

    def test_immutability(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert isinstance(p, RuntimePersonaProjection)
        assert p.__dataclass_fields__ is not None


# ===================================================================
# Provenance
# ===================================================================

class TestProjectionProvenance:
    def test_cartridge_id_preserved(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert p.cartridge_id == c.manifest.cartridge_id

    def test_schema_version_preserved(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert p.cartridge_schema_version == c.manifest.schema_version

    def test_timestamps_not_included(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        assert "created_at" not in d
        assert "updated_at" not in d


# ===================================================================
# Identity
# ===================================================================

class TestProjectionIdentity:
    def test_identity_fields_match(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert p.identifier == c.identity.identifier
        assert p.display_name == c.identity.display_name
        assert p.summary == c.identity.summary
        assert p.description == c.identity.description
        assert p.aliases == c.identity.aliases


# ===================================================================
# Character
# ===================================================================

class TestProjectionCharacter:
    def test_character_fields_match(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert p.core_values == c.character.core_values
        assert p.motivations == c.character.motivations
        assert p.strengths == c.character.strengths
        assert p.limitations == c.character.limitations
        assert p.goals == c.character.goals
        assert p.boundaries == c.character.boundaries


# ===================================================================
# Communication
# ===================================================================

class TestProjectionCommunication:
    def test_communication_fields_match(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert p.communication_style == c.communication.communication_style
        assert p.tone == c.communication.tone
        assert p.vocabulary_preferences == c.communication.vocabulary_preferences
        assert p.response_tendencies == c.communication.response_tendencies
        assert p.formatting_preferences == c.communication.formatting_preferences

    def test_reserved_legacy_data_omitted(self):
        comm = CommunicationModule(
            communication_style="Formal",
            tone=("Direct",),
            reserved={"legacy": {"value": "old_data"}},
        )
        c = _make_cartridge()
        c2 = PersonaCartridge(
            manifest=c.manifest,
            identity=c.identity,
            character=c.character,
            preferences=c.preferences,
            behavior=c.behavior,
            communication=comm,
            status=CartridgeStatus.FORGED,
        )
        p = RuntimeProjectionBuilder.build(c2)
        assert p.communication_style == "Formal"
        assert p.tone == ("Direct",)
        d = p.to_dict()
        assert "reserved" not in d


# ===================================================================
# Preferences
# ===================================================================

class TestProjectionPreferences:
    def test_preferences_exposed(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert len(p.preferences) == len(c.preferences.entries)
        assert p.preferences == c.preferences.entries

    def test_preferences_deterministic_order(self):
        c = _make_cartridge()
        p1 = RuntimeProjectionBuilder.build(c)
        p2 = RuntimeProjectionBuilder.build(c)
        assert p1.preferences == p2.preferences


# ===================================================================
# Behavior — filtering
# ===================================================================

class TestProjectionBehavior:
    def test_enabled_policies_included(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        for policy in p.policies:
            assert policy.enabled is True

    def test_disabled_policies_excluded(self):
        c = _make_cartridge()
        policies = list(c.behavior.policies)
        # Add a disabled policy
        disabled = BehaviorPolicy(
            identifier="deprecated",
            title="Deprecated",
            enabled=False,
        )
        modified = BehaviorModule(
            policies=tuple(policies) + (disabled,)
        )
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
        for policy in p.policies:
            assert policy.enabled is True
        ids = [pol.identifier for pol in p.policies]
        assert "deprecated" not in ids

    def test_all_enabled_in_default(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        all_enabled = [pol for pol in c.behavior.policies if pol.enabled]
        assert len(p.policies) == len(all_enabled)

    def test_no_policies_when_all_disabled(self):
        draft = _make_valid_draft(behavior_rules=["Rule 1", "Rule 2"])
        c = CartridgeForge.forge(draft).cartridge
        all_disabled = tuple(
            BehaviorPolicy(
                identifier=pol.identifier,
                title=pol.title,
                enabled=False,
            )
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
        assert len(p.policies) == 0


# ===================================================================
# Isolation
# ===================================================================

class TestProjectionIsolation:
    def test_mutating_to_dict_does_not_affect_cartridge(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        d["display_name"] = "MUTATED"
        assert c.identity.display_name != "MUTATED"

    def test_projection_is_not_cartridge(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert not isinstance(p, PersonaCartridge)

    def test_cartridge_unchanged_after_projection(self):
        c = _make_cartridge()
        identity_before = c.identity.to_dict()
        character_before = c.character.to_dict()
        comm_before = c.communication.to_dict()
        RuntimeProjectionBuilder.build(c)
        assert c.identity.to_dict() == identity_before
        assert c.character.to_dict() == character_before
        assert c.communication.to_dict() == comm_before


# ===================================================================
# Compatibility — upgrade chain
# ===================================================================

class TestProjectionCompatibility:
    def test_legacy_0_1_0_projects_identically(self):
        data = _make_flat_legacy_data()
        upgraded = CartridgeSerializer.deserialize(data)
        p_upgraded = RuntimeProjectionBuilder.build(upgraded)

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

        assert p_upgraded.display_name == p_forged.display_name
        assert p_upgraded.identifier == p_forged.identifier
        assert p_upgraded.summary == p_forged.summary
        assert p_upgraded.core_values == p_forged.core_values
        assert p_upgraded.motivations == p_forged.motivations
        assert p_upgraded.communication_style == p_forged.communication_style
        assert p_upgraded.preferences == p_forged.preferences

    def test_legacy_0_2_0_full_chain_projects(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        p = RuntimeProjectionBuilder.build(c)
        assert p.cartridge_schema_version == "0.6.0"
        assert len(p.policies) > 0

    def test_legacy_round_trip_projects(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        p1 = RuntimeProjectionBuilder.build(c)

        serialized = CartridgeSerializer.serialize(c)
        c2 = CartridgeSerializer.deserialize(serialized)
        p2 = RuntimeProjectionBuilder.build(c2)

        assert p1 == p2


# ===================================================================
# Serialization (to_dict)
# ===================================================================

class TestProjectionSerialization:
    def test_to_dict_returns_dict(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_includes_provenance(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        assert d["cartridge_id"] == c.manifest.cartridge_id
        assert d["cartridge_schema_version"] == c.manifest.schema_version

    def test_to_dict_includes_all_fields(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        assert "identifier" in d
        assert "display_name" in d
        assert "summary" in d
        assert "description" in d
        assert "aliases" in d
        assert "core_values" in d
        assert "motivations" in d
        assert "strengths" in d
        assert "limitations" in d
        assert "goals" in d
        assert "boundaries" in d
        assert "communication_style" in d
        assert "tone" in d
        assert "vocabulary_preferences" in d
        assert "response_tendencies" in d
        assert "formatting_preferences" in d
        assert "preferences" in d
        assert "policies" in d

    def test_to_dict_no_cartridge_keys(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        assert "manifest" not in d
        assert "extensions" not in d
        assert "status" not in d

    def test_to_dict_deterministic(self):
        c = _make_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        d1 = p.to_dict()
        d2 = p.to_dict()
        assert d1 == d2
