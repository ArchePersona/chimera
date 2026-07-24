import copy
import json

from app.integrations.archengine import (
    ARCHEngineCompatibilityShim,
    CartridgeDescriptorPayload,
)
from app.models.cartridge import (
    CartridgeStatus,
    PersonaCartridge,
    PersonaStateModulation,
    ValidationCode,
)
from app.models.projection import (
    RuntimePersonaProjection,
    RuntimeProjectionBuilder,
)
from app.services.forge import CartridgeForge
from app.services.serializer import CartridgeSerializer
from tests.fixtures.archengine.fixtures import complete_cartridge


# ===================================================================
# Helpers
# ===================================================================

def _make_modulation(**overrides) -> PersonaStateModulation:
    params = dict(
        voice_texture=("warm", "resonant"),
        signature_phrasing=("Let me think about this",),
        preferred_moves=("ask clarifying question", "offer example"),
        forbidden_moves=("interrupt", "dismiss"),
        lexical_bias=("precise terminology",),
        metaphor_bias=("nature metaphors",),
        humor_boundary="no sarcasm",
        warmth_boundary="friendly but professional",
    )
    params.update(overrides)
    return PersonaStateModulation(**params)


def _make_cartridge_with_modulations() -> PersonaCartridge:
    base = complete_cartridge()
    mods = {
        "StDefault": _make_modulation(),
        "StReflective": _make_modulation(
            voice_texture=("soft", "measured"),
            humor_boundary=None,
        ),
    }
    return PersonaCartridge(
        manifest=base.manifest,
        identity=base.identity,
        character=base.character,
        preferences=base.preferences,
        behavior=base.behavior,
        communication=base.communication,
        state_modulations=mods,
        status=CartridgeStatus.FORGED,
    )


# ===================================================================
# PersonaStateModulation — construction & immutability
# ===================================================================

class TestModulationConstruction:
    def test_default_construction(self):
        m = PersonaStateModulation()
        assert m.voice_texture == ()
        assert m.signature_phrasing == ()
        assert m.preferred_moves == ()
        assert m.forbidden_moves == ()
        assert m.lexical_bias == ()
        assert m.metaphor_bias == ()
        assert m.humor_boundary is None
        assert m.warmth_boundary is None

    def test_construction_with_values(self):
        m = _make_modulation()
        assert len(m.voice_texture) == 2
        assert m.humor_boundary == "no sarcasm"
        assert m.warmth_boundary == "friendly but professional"

    def test_immutable(self):
        m = _make_modulation()
        with __import__("pytest").raises(Exception):
            m.voice_texture = ("changed",)  # type: ignore

    def test_frozen_copy_not_mutable(self):
        m = _make_modulation()
        d = m.to_dict()
        d["voice_texture"] = ["mutated"]
        assert m.voice_texture == ("warm", "resonant")


# ===================================================================
# PersonaStateModulation — to_dict
# ===================================================================

class TestModulationToDict:
    def test_empty_to_dict(self):
        m = PersonaStateModulation()
        assert m.to_dict() == {}

    def test_to_dict_all_fields(self):
        m = _make_modulation()
        d = m.to_dict()
        assert d["voice_texture"] == ["warm", "resonant"]
        assert d["signature_phrasing"] == ["Let me think about this"]
        assert d["preferred_moves"] == ["ask clarifying question", "offer example"]
        assert d["forbidden_moves"] == ["interrupt", "dismiss"]
        assert d["lexical_bias"] == ["precise terminology"]
        assert d["metaphor_bias"] == ["nature metaphors"]
        assert d["humor_boundary"] == "no sarcasm"
        assert d["warmth_boundary"] == "friendly but professional"

    def test_to_dict_omits_empty_tuples(self):
        m = PersonaStateModulation(humor_boundary="strict", warmth_boundary="warm")
        d = m.to_dict()
        assert "voice_texture" not in d
        assert "signature_phrasing" not in d
        assert "preferred_moves" not in d
        assert "forbidden_moves" not in d
        assert "lexical_bias" not in d
        assert "metaphor_bias" not in d
        assert d["humor_boundary"] == "strict"
        assert d["warmth_boundary"] == "warm"

    def test_to_dict_omits_none_boundaries(self):
        m = _make_modulation(humor_boundary=None, warmth_boundary=None)
        d = m.to_dict()
        assert "humor_boundary" not in d
        assert "warmth_boundary" not in d

    def test_to_dict_deterministic(self):
        m = _make_modulation()
        assert m.to_dict() == m.to_dict()


# ===================================================================
# PersonaStateModulation — validate
# ===================================================================

class TestModulationValidate:
    def test_valid_modulation_no_errors(self):
        m = _make_modulation()
        errors, _ = m.validate()  # type: ignore
        assert len(errors) == 0

    def test_empty_modulation_valid(self):
        m = PersonaStateModulation()
        errors, _ = m.validate()  # type: ignore
        assert len(errors) == 0

    def test_invalid_tuple_field_type(self):
        m = PersonaStateModulation(voice_texture=("ok", 42))  # type: ignore
        errors, _ = m.validate()  # type: ignore
        assert any("voice_texture" in e.field for e in errors)

    def test_invalid_boundary_type(self):
        m = PersonaStateModulation(humor_boundary=42)  # type: ignore
        errors, _ = m.validate()  # type: ignore
        assert any("humor_boundary" in e.field for e in errors)

    def test_none_boundary_valid(self):
        m = PersonaStateModulation(humor_boundary=None)
        errors, _ = m.validate()  # type: ignore
        assert all("humor_boundary" not in e.field for e in errors)


# ===================================================================
# Cartridge — state_modulations field
# ===================================================================

class TestCartridgeStateModulations:
    def test_cartridge_defaults_empty(self):
        c = complete_cartridge()
        assert c.state_modulations == {}

    def test_cartridge_with_modulations(self):
        c = _make_cartridge_with_modulations()
        assert len(c.state_modulations) == 2
        assert "StDefault" in c.state_modulations
        assert "StReflective" in c.state_modulations

    def test_cartridge_immutable_modulations(self):
        c = _make_cartridge_with_modulations()
        with __import__("pytest").raises(Exception):
            c.state_modulations = {"StNew": _make_modulation()}  # type: ignore

    def test_to_dict_includes_state_modulations(self):
        c = _make_cartridge_with_modulations()
        d = c.to_dict()
        assert "state_modulations" in d
        assert "StDefault" in d["state_modulations"]
        assert "StReflective" in d["state_modulations"]
        assert d["state_modulations"]["StDefault"]["voice_texture"] == ["warm", "resonant"]

    def test_to_dict_omits_when_empty(self):
        c = complete_cartridge()
        d = c.to_dict()
        assert "state_modulations" not in d

    def test_to_dict_deterministic(self):
        c = _make_cartridge_with_modulations()
        assert c.to_dict() == c.to_dict()


# ===================================================================
# Projection — state_modulations
# ===================================================================

class TestProjectionStateModulations:
    def test_projection_includes_modulations(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        assert len(p.state_modulations) == 2
        assert "StDefault" in p.state_modulations
        assert isinstance(p.state_modulations["StDefault"], PersonaStateModulation)

    def test_projection_empty_when_cartridge_empty(self):
        c = complete_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        assert p.state_modulations == {}

    def test_projection_to_dict_includes_modulations(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        assert "state_modulations" in d
        assert d["state_modulations"]["StDefault"]["voice_texture"] == ["warm", "resonant"]

    def test_projection_to_dict_omits_when_empty(self):
        c = complete_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        assert "state_modulations" not in d

    def test_projection_deterministic(self):
        c = _make_cartridge_with_modulations()
        p1 = RuntimeProjectionBuilder.build(c)
        p2 = RuntimeProjectionBuilder.build(c)
        assert p1.state_modulations == p2.state_modulations

    def test_projection_cartridge_unchanged(self):
        c = _make_cartridge_with_modulations()
        RuntimeProjectionBuilder.build(c)
        assert c.state_modulations["StDefault"].voice_texture == ("warm", "resonant")


# ===================================================================
# Payload — state_modulations
# ===================================================================

class TestPayloadStateModulations:
    def test_payload_includes_modulations(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert "StDefault" in payload.state_modulations
        assert "StReflective" in payload.state_modulations

    def test_payload_modulation_values(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        sd = payload.state_modulations["StDefault"]
        assert sd["voice_texture"] == ["warm", "resonant"]
        assert sd["forbidden_moves"] == ["interrupt", "dismiss"]
        assert sd["humor_boundary"] == "no sarcasm"
        assert sd["warmth_boundary"] == "friendly but professional"

    def test_payload_partial_modulation(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        sr = payload.state_modulations["StReflective"]
        assert sr["voice_texture"] == ["soft", "measured"]
        assert "humor_boundary" not in sr
        assert sr["warmth_boundary"] == "friendly but professional"

    def test_payload_empty_when_no_modulations(self):
        c = complete_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.state_modulations == {}

    def test_payload_to_dict_includes_modulations(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        d = payload.to_dict()
        assert "state_modulations" in d
        assert d["state_modulations"]["StDefault"]["voice_texture"] == ["warm", "resonant"]

    def test_payload_to_dict_omits_when_empty(self):
        c = complete_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        d = payload.to_dict()
        assert "state_modulations" not in d

    def test_payload_deterministic(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload1 = ARCHEngineCompatibilityShim.translate(p)
        payload2 = ARCHEngineCompatibilityShim.translate(p)
        assert payload1.state_modulations == payload2.state_modulations

    def test_json_serializable(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        d = payload.to_dict()
        text = json.dumps(d, ensure_ascii=False)
        restored = json.loads(text)
        assert restored["state_modulations"]["StDefault"]["voice_texture"] == ["warm", "resonant"]


# ===================================================================
# Translation — modulations pass through projection → payload
# ===================================================================

class TestTranslationStateModulations:
    def test_translation_preserves_count(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert len(payload.state_modulations) == len(p.state_modulations)

    def test_translation_preserves_state_ids(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert set(payload.state_modulations) == set(p.state_modulations)

    def test_translation_no_aliasing(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        payload.state_modulations["StDefault"]["voice_texture"] = ["mutated"]
        assert p.state_modulations["StDefault"].voice_texture == ("warm", "resonant")

    def test_translation_no_modulations_passes_empty(self):
        c = complete_cartridge()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.state_modulations == {}


# ===================================================================
# Serializer — state_modulations round-trip
# ===================================================================

class TestSerializerStateModulations:
    def test_serialize_deserialize_round_trip(self):
        c = _make_cartridge_with_modulations()
        serialized = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(serialized)
        assert restored.state_modulations == c.state_modulations

    def test_round_trip_preserves_all_fields(self):
        c = _make_cartridge_with_modulations()
        serialized = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(serialized)
        m = restored.state_modulations["StDefault"]
        assert m.voice_texture == ("warm", "resonant")
        assert m.signature_phrasing == ("Let me think about this",)
        assert m.preferred_moves == ("ask clarifying question", "offer example")
        assert m.forbidden_moves == ("interrupt", "dismiss")
        assert m.lexical_bias == ("precise terminology",)
        assert m.metaphor_bias == ("nature metaphors",)
        assert m.humor_boundary == "no sarcasm"
        assert m.warmth_boundary == "friendly but professional"

    def test_round_trip_partial_modulation(self):
        m = PersonaStateModulation(
            voice_texture=("soft",),
            humor_boundary="strict",
        )
        c = _make_cartridge_with_modulations()
        c2 = PersonaCartridge(
            manifest=c.manifest,
            identity=c.identity,
            character=c.character,
            preferences=c.preferences,
            behavior=c.behavior,
            communication=c.communication,
            state_modulations={"StTest": m},
            status=CartridgeStatus.FORGED,
        )
        serialized = CartridgeSerializer.serialize(c2)
        restored = CartridgeSerializer.deserialize(serialized)
        rm = restored.state_modulations["StTest"]
        assert rm.voice_texture == ("soft",)
        assert rm.signature_phrasing == ()
        assert rm.preferred_moves == ()
        assert rm.forbidden_moves == ()
        assert rm.lexical_bias == ()
        assert rm.metaphor_bias == ()
        assert rm.humor_boundary == "strict"
        assert rm.warmth_boundary is None

    def test_round_trip_none_boundaries(self):
        m = PersonaStateModulation(
            humor_boundary=None,
            warmth_boundary=None,
        )
        c = _make_cartridge_with_modulations()
        c2 = PersonaCartridge(
            manifest=c.manifest,
            identity=c.identity,
            character=c.character,
            preferences=c.preferences,
            behavior=c.behavior,
            communication=c.communication,
            state_modulations={"StTest": m},
            status=CartridgeStatus.FORGED,
        )
        serialized = CartridgeSerializer.serialize(c2)
        restored = CartridgeSerializer.deserialize(serialized)
        rm = restored.state_modulations["StTest"]
        assert rm.humor_boundary is None
        assert rm.warmth_boundary is None

    def test_empty_modulations_round_trip(self):
        c = complete_cartridge()
        serialized = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(serialized)
        assert restored.state_modulations == {}

    def test_deterministic_serialization(self):
        c = _make_cartridge_with_modulations()
        s1 = CartridgeSerializer.serialize(c)
        s2 = CartridgeSerializer.serialize(c)
        assert s1 == s2

    def test_serialized_has_modulations_key_only_when_present(self):
        c = _make_cartridge_with_modulations()
        d = CartridgeSerializer.serialize(c)
        assert "state_modulations" in d

        c2 = complete_cartridge()
        d2 = CartridgeSerializer.serialize(c2)
        assert "state_modulations" not in d2


# ===================================================================
# Legacy compatibility — no state_modulations in old data
# ===================================================================

class TestLegacyStateModulations:
    def test_legacy_0_1_0_has_no_modulations(self):
        data = {
            "manifest": {
                "cartridge_id": "legacy-test",
                "schema_name": "archepersona.chimera.persona-cartridge",
                "schema_version": "0.1.0",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            },
            "name": "Legacy",
            "identifier": "legacy",
            "summary": "Test",
            "description": "",
            "communication_style": "Formal",
            "core_values": ["X"],
            "motivations": ["Y"],
            "strengths": ["Z"],
            "limitations": ["L"],
            "goals": ["G"],
            "boundaries": ["B"],
            "preferences": {},
            "behavior_rules": [],
            "extensions": {},
            "status": "forged",
        }
        c = CartridgeSerializer.deserialize(data)
        assert c.state_modulations == {}

    def test_legacy_upgrade_preserves_no_modulations(self):
        data = {
            "manifest": {
                "cartridge_id": "legacy-test",
                "schema_name": "archepersona.chimera.persona-cartridge",
                "schema_version": "0.1.0",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            },
            "name": "Legacy",
            "identifier": "legacy",
            "summary": "Test",
            "description": "",
            "communication_style": "Formal",
            "core_values": ["X"],
            "motivations": ["Y"],
            "strengths": ["Z"],
            "limitations": ["L"],
            "goals": ["G"],
            "boundaries": ["B"],
            "preferences": {},
            "behavior_rules": [],
            "extensions": {},
            "status": "forged",
        }
        c = CartridgeSerializer.deserialize(data)
        serialized = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(serialized)
        assert restored.state_modulations == {}

    def test_legacy_export_has_no_modulations(self):
        data = {
            "manifest": {
                "cartridge_id": "legacy-test",
                "schema_name": "archepersona.chimera.persona-cartridge",
                "schema_version": "0.1.0",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            },
            "name": "Legacy",
            "identifier": "legacy",
            "summary": "Test",
            "description": "",
            "communication_style": "Formal",
            "core_values": ["X"],
            "motivations": ["Y"],
            "strengths": ["Z"],
            "limitations": ["L"],
            "goals": ["G"],
            "boundaries": ["B"],
            "preferences": {},
            "behavior_rules": [],
            "extensions": {},
            "status": "forged",
        }
        c = CartridgeSerializer.deserialize(data)
        from app.services.archengine_export import export_archengine_payload
        payload = export_archengine_payload(c)
        assert payload.state_modulations == {}


# ===================================================================
# Export — state_modulations flow through export pipeline
# ===================================================================

class TestExportStateModulations:
    def test_export_includes_modulations(self):
        c = _make_cartridge_with_modulations()
        from app.services.archengine_export import export_archengine_payload
        payload = export_archengine_payload(c)
        assert "StDefault" in payload.state_modulations

    def test_export_json_includes_modulations(self):
        c = _make_cartridge_with_modulations()
        from app.services.archengine_export import export_archengine_payload_json
        d = export_archengine_payload_json(c)
        assert "state_modulations" in d

    def test_export_json_round_trip(self):
        c = _make_cartridge_with_modulations()
        from app.services.archengine_export import export_archengine_payload_json
        d = export_archengine_payload_json(c)
        text = json.dumps(d, ensure_ascii=False)
        restored = json.loads(text)
        assert restored["state_modulations"]["StDefault"]["voice_texture"] == ["warm", "resonant"]

    def test_export_deterministic_modulo_timestamp(self):
        c = _make_cartridge_with_modulations()
        from app.services.archengine_export import export_archengine_payload
        p1 = export_archengine_payload(c)
        p2 = export_archengine_payload(c)
        assert p1.state_modulations == p2.state_modulations

    def test_export_empty_modulations(self):
        c = complete_cartridge()
        from app.services.archengine_export import export_archengine_payload
        payload = export_archengine_payload(c)
        assert payload.state_modulations == {}


# ===================================================================
# Integration — end-to-end flow with state_modulations
# ===================================================================

class TestIntegrationStateModulations:
    def test_full_round_trip(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        d = payload.to_dict()
        text = json.dumps(d, ensure_ascii=False)
        restored = json.loads(text)
        assert restored["state_modulations"]["StDefault"]["voice_texture"] == ["warm", "resonant"]
        assert restored["state_modulations"]["StReflective"]["voice_texture"] == ["soft", "measured"]
        assert "humor_boundary" not in restored["state_modulations"]["StReflective"]

    def test_cartridge_serialize_deserialize_project_translate(self):
        c = _make_cartridge_with_modulations()
        serialized = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(serialized)
        p = RuntimeProjectionBuilder.build(restored)
        payload = ARCHEngineCompatibilityShim.translate(p)
        assert payload.state_modulations["StDefault"]["voice_texture"] == ["warm", "resonant"]
        assert payload.state_modulations["StReflective"]["voice_texture"] == ["soft", "measured"]

    def test_many_state_modulations(self):
        mods = {}
        for i in range(10):
            mods[f"StState_{i}"] = _make_modulation(
                voice_texture=(f"texture_{i}",),
                signature_phrasing=(f"phrase_{i}",),
            )
        c = _make_cartridge_with_modulations()
        c2 = PersonaCartridge(
            manifest=c.manifest,
            identity=c.identity,
            character=c.character,
            preferences=c.preferences,
            behavior=c.behavior,
            communication=c.communication,
            state_modulations=mods,
            status=CartridgeStatus.FORGED,
        )
        serialized = CartridgeSerializer.serialize(c2)
        restored = CartridgeSerializer.deserialize(serialized)
        assert len(restored.state_modulations) == 10
        for i in range(10):
            sid = f"StState_{i}"
            assert restored.state_modulations[sid].voice_texture == (f"texture_{i}",)
            assert restored.state_modulations[sid].signature_phrasing == (f"phrase_{i}",)

    def test_to_dict_order_deterministic(self):
        mods = {
            "StZ": _make_modulation(voice_texture=("z",)),
            "StA": _make_modulation(voice_texture=("a",)),
            "StM": _make_modulation(voice_texture=("m",)),
        }
        c = _make_cartridge_with_modulations()
        c2 = PersonaCartridge(
            manifest=c.manifest,
            identity=c.identity,
            character=c.character,
            preferences=c.preferences,
            behavior=c.behavior,
            communication=c.communication,
            state_modulations=mods,
            status=CartridgeStatus.FORGED,
        )
        d1 = c2.to_dict()
        d2 = c2.to_dict()
        keys1 = list(d1["state_modulations"].keys())
        keys2 = list(d2["state_modulations"].keys())
        assert keys1 == keys2 == ["StA", "StM", "StZ"]


# ===================================================================
# Isolation — no shared mutable references
# ===================================================================

class TestIsolationStateModulations:
    def test_cartridge_modulations_not_shared_with_projection(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        assert p.state_modulations is not c.state_modulations

    def test_mutating_projection_to_dict_does_not_affect_cartridge(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        d = p.to_dict()
        d["state_modulations"]["StDefault"]["voice_texture"] = ["mutated"]
        assert c.state_modulations["StDefault"].voice_texture == ("warm", "resonant")

    def test_mutating_payload_does_not_affect_projection(self):
        c = _make_cartridge_with_modulations()
        p = RuntimeProjectionBuilder.build(c)
        payload = ARCHEngineCompatibilityShim.translate(p)
        payload.state_modulations["StDefault"]["voice_texture"] = ["mutated"]
        assert p.state_modulations["StDefault"].voice_texture == ("warm", "resonant")

    def test_serialized_modulations_deep_copy(self):
        c = _make_cartridge_with_modulations()
        serialized = CartridgeSerializer.serialize(c)
        serialized["state_modulations"]["StDefault"]["voice_texture"] = ["mutated"]
        assert c.state_modulations["StDefault"].voice_texture == ("warm", "resonant")
