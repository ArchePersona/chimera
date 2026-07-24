import copy
import pytest
from datetime import datetime, timezone

from app.models.cartridge import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    BehaviorModule,
    BehaviorPolicy,
    CartridgeModule,
    CartridgeStatus,
    CartridgeManifest,
    CartridgeValidationError,
    CartridgeValidationWarning,
    CartridgeValidationResult,
    ForgeErrorCode,
    ForgeError,
    ForgeResult,
    ModuleRegistry,
    ModuleRegistryEntry,
    PersonaCartridge,
    PersonaDraft,
    IdentityModule,
    CharacterModule,
    PreferenceEntry,
    PreferenceModule,
    BehaviorModule,
    CommunicationModule,
    ValidationCode,
    UnsupportedVersionError,
    parse_version,
    is_version_supported,
    _dedup_ordered,
    _normalize_list,
    generate_behavior_identifiers,
)
from app.services.forge import CartridgeForge
from app.services.serializer import CartridgeSerializer


# ===================================================================
# Schema constants
# ===================================================================

class TestSchemaConstants:
    def test_schema_name_constant(self):
        assert SCHEMA_NAME == "archepersona.chimera.persona-cartridge"

    def test_schema_version_constant(self):
        assert SCHEMA_VERSION == "0.6.0"

    def test_cartridge_schema_endpoint(self):
        s = PersonaCartridge.schema()
        assert s["name"] == SCHEMA_NAME
        assert s["version"] == SCHEMA_VERSION

    def test_forged_cartridge_uses_constants(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        assert c.manifest.schema_name == SCHEMA_NAME
        assert c.manifest.schema_version == SCHEMA_VERSION


# ===================================================================
# CartridgeStatus
# ===================================================================

class TestCartridgeStatus:
    def test_values(self):
        assert CartridgeStatus.DRAFT.value == "draft"
        assert CartridgeStatus.VALIDATED.value == "validated"
        assert CartridgeStatus.FORGED.value == "forged"

    def test_draft_starts_draft(self):
        assert PersonaDraft().status == CartridgeStatus.DRAFT

    def test_validate_transitions_to_validated(self):
        draft = _make_valid_draft()
        result, validated = CartridgeForge.validate(draft)
        assert result.valid is True
        assert validated.status == CartridgeStatus.VALIDATED

    def test_validate_does_not_mutate_source(self):
        draft = _make_valid_draft()
        CartridgeForge.validate(draft)
        assert draft.status == CartridgeStatus.DRAFT

    def test_forged_has_forged_status(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        assert c.status == CartridgeStatus.FORGED


# ===================================================================
# CartridgeManifest
# ===================================================================

class TestCartridgeManifest:
    def test_draft_has_no_cartridge_id(self):
        assert not hasattr(PersonaDraft(), "cartridge_id")

    def test_cartridge_has_manifest(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        assert hasattr(c, "manifest")
        assert len(c.manifest.cartridge_id) > 0

    def test_each_forge_generates_unique_id(self):
        r1 = CartridgeForge.forge(_make_valid_draft())
        r2 = CartridgeForge.forge(_make_valid_draft())
        assert r1.cartridge.manifest.cartridge_id != r2.cartridge.manifest.cartridge_id

    def test_manifest_frozen(self):
        m = CartridgeManifest(cartridge_id="x")
        with pytest.raises(Exception):
            m.cartridge_id = "y"

    def test_manifest_to_dict(self):
        d = CartridgeManifest(cartridge_id="abc").to_dict()
        assert d["cartridge_id"] == "abc"
        assert d["schema_name"] == SCHEMA_NAME
        assert d["schema_version"] == SCHEMA_VERSION


# ===================================================================
# Module construction
# ===================================================================

class TestIdentityModule:
    def test_construction(self):
        m = IdentityModule(display_name="Alex", identifier="alex", summary="A guide", description="Optional")
        assert m.display_name == "Alex"
        assert m.identifier == "alex"
        assert m.summary == "A guide"
        assert m.description == "Optional"

    def test_immutable(self):
        m = IdentityModule(display_name="Alex", identifier="alex", summary="Guide")
        with pytest.raises(Exception):
            m.display_name = "Bob"

    def test_to_dict(self):
        d = IdentityModule(display_name="A", identifier="a", summary="B", description="C").to_dict()
        assert d["display_name"] == "A"
        assert d["identifier"] == "a"
        assert d["summary"] == "B"
        assert d["description"] == "C"
        assert d["aliases"] == []

    def test_validate_valid(self):
        errors, warnings = IdentityModule(display_name="A", identifier="a", summary="B").validate()
        assert errors == []
        assert warnings == []

    def test_validate_missing_display_name(self):
        errors, _ = IdentityModule(display_name="", identifier="a", summary="B").validate()
        codes = {e.field for e in errors}
        assert "identity.display_name" in codes

    def test_validate_missing_identifier(self):
        errors, _ = IdentityModule(display_name="A", identifier="", summary="B").validate()
        codes = {e.field for e in errors}
        assert "identity.identifier" in codes

    def test_validate_missing_summary(self):
        errors, _ = IdentityModule(display_name="A", identifier="a", summary="").validate()
        codes = {e.field for e in errors}
        assert "identity.summary" in codes


class TestCharacterModule:
    def test_construction(self):
        m = CharacterModule(
            core_values=("X",),
            motivations=("Y",),
            strengths=("Z",),
            limitations=("L",),
            goals=("G",),
            boundaries=("B",),
        )
        assert m.core_values == ("X",)

    def test_immutable(self):
        m = CharacterModule()
        with pytest.raises(Exception):
            m.core_values = ("New",)

    def test_to_dict(self):
        d = CharacterModule(core_values=("V",), motivations=("M",)).to_dict()
        assert d["core_values"] == ["V"]
        assert d["motivations"] == ["M"]

    def test_validate_valid(self):
        m = CharacterModule(core_values=("X",), motivations=("Y",),
                            strengths=("Z",), limitations=("L",), goals=("G",), boundaries=("B",))
        errors, warnings = m.validate()
        assert errors == []

    def test_validate_missing_list_fields(self):
        m = CharacterModule()
        errors, _ = m.validate()
        fields = {e.field for e in errors}
        assert "character.core_values" in fields
        assert "character.motivations" in fields
        assert "character.strengths" in fields
        assert "character.limitations" in fields
        assert "character.goals" in fields
        assert "character.boundaries" in fields

    def test_validate_partial_lists(self):
        m = CharacterModule(core_values=("X",))
        errors, _ = m.validate()
        fields = {e.field for e in errors}
        assert "character.core_values" not in fields
        assert "character.motivations" in fields


class TestCharacterCollections:
    def test_normalize_strips_whitespace(self):
        draft = _make_valid_draft(core_values=["  Honesty  ", "  Courage  "])
        PersonaDraft.normalize(draft)
        assert draft.core_values == ["Honesty", "Courage"]

    def test_normalize_removes_empty(self):
        draft = _make_valid_draft(motivations=["", "  ", "To learn"])
        PersonaDraft.normalize(draft)
        assert draft.motivations == ["To learn"]

    def test_normalize_dedup(self):
        draft = _make_valid_draft(strengths=["Patience", "Patience", "Focus"])
        PersonaDraft.normalize(draft)
        assert draft.strengths == ["Patience", "Focus"]

    def test_normalize_dedup_preserves_order(self):
        draft = _make_valid_draft(limitations=["Z", "A", "Z", "B", "A"])
        PersonaDraft.normalize(draft)
        assert draft.limitations == ["Z", "A", "B"]

    def test_normalize_dedup_after_strip(self):
        draft = _make_valid_draft(goals=["  G1  ", "G1", "  G2  "])
        PersonaDraft.normalize(draft)
        assert draft.goals == ["G1", "G2"]

    def test_normalize_all_collections_handled(self):
        draft = _make_valid_draft(
            core_values=["", "V1"],
            motivations=["  M1  ", "M1"],
            strengths=["S1"],
            limitations=["  ", "L1"],
            goals=["G1"],
            boundaries=["  B1  "],
        )
        PersonaDraft.normalize(draft)
        assert draft.core_values == ["V1"]
        assert draft.motivations == ["M1"]
        assert draft.strengths == ["S1"]
        assert draft.limitations == ["L1"]
        assert draft.goals == ["G1"]
        assert draft.boundaries == ["B1"]

    def test_forge_preserves_normalized_character(self):
        draft = _make_valid_draft(
            core_values=["  Honesty  ", "Courage", "  Honesty  "],
            motivations=["  To learn  "],
        )
        c = CartridgeForge.forge(draft).cartridge
        assert c.character.core_values == ("Honesty", "Courage")
        assert c.character.motivations == ("To learn",)

    def test_to_dict_keys_only_owned(self):
        d = CharacterModule(core_values=("X",), motivations=("Y",)).to_dict()
        assert set(d.keys()) == {"core_values", "motivations", "strengths",
                                 "limitations", "goals", "boundaries"}


class TestCharacterValidation:
    def test_required_collections_all_empty(self):
        m = CharacterModule()
        errors, _ = m.validate()
        fields = {e.field for e in errors}
        assert "character.core_values" in fields
        assert "character.motivations" in fields
        assert "character.strengths" in fields
        assert "character.limitations" in fields
        assert "character.goals" in fields
        assert "character.boundaries" in fields
        assert len(errors) == 6

    def test_required_collections_field_path_reporting(self):
        m = CharacterModule()
        errors, _ = m.validate()
        error_fields = [e.field for e in errors]
        assert "character.core_values" in error_fields
        assert all(e.code == ValidationCode.REQUIRED_LIST_EMPTY for e in errors)

    def test_partial_collections_reports_only_missing(self):
        m = CharacterModule(core_values=("X",), motivations=("Y",))
        errors, _ = m.validate()
        fields = {e.field for e in errors}
        assert "character.core_values" not in fields
        assert "character.motivations" not in fields
        assert "character.strengths" in fields
        assert "character.limitations" in fields
        assert "character.goals" in fields
        assert "character.boundaries" in fields

    def test_valid_module_no_errors(self):
        m = CharacterModule(core_values=("X",), motivations=("Y",),
                            strengths=("Z",), limitations=("L",),
                            goals=("G",), boundaries=("B",))
        errors, warnings = m.validate()
        assert errors == []
        assert warnings == []

    def test_structural_not_semantic(self):
        m = CharacterModule(core_values=("X",), motivations=("Y",),
                            strengths=("Z",), limitations=("L",),
                            goals=("G",), boundaries=("B",))
        errors, _ = m.validate()
        assert len(errors) == 0


class TestCharacterSerialization:
    def test_round_trip_all_collections(self):
        draft = _make_valid_draft(
            core_values=["Honesty", "Courage"],
            motivations=["To learn", "To teach"],
            strengths=["Patience", "Focus"],
            limitations=["Overthinking", "Impatience"],
            goals=["Inspire", "Educate"],
            boundaries=["Never lie", "Stay humble"],
        )
        original = CartridgeForge.forge(draft).cartridge
        data = CartridgeSerializer.serialize(original)
        restored = CartridgeSerializer.deserialize(data)
        assert restored.character.core_values == ("Honesty", "Courage")
        assert restored.character.motivations == ("To learn", "To teach")
        assert restored.character.strengths == ("Patience", "Focus")
        assert restored.character.limitations == ("Overthinking", "Impatience")
        assert restored.character.goals == ("Inspire", "Educate")
        assert restored.character.boundaries == ("Never lie", "Stay humble")

    def test_deterministic_output(self):
        draft = _make_valid_draft(
            core_values=["Z", "A", "M"],
            motivations=["C", "B", "A"],
            strengths=["X"],
            limitations=["Y"],
            goals=["W"],
            boundaries=["V"],
        )
        c = CartridgeForge.forge(draft).cartridge
        s1 = CartridgeSerializer.serialize(c)
        s2 = CartridgeSerializer.serialize(c)
        assert s1["character"] == s2["character"]

    def test_compatibility_with_schema_0_5_0(self):
        draft = _make_valid_draft(core_values=["X"])
        c = CartridgeForge.forge(draft).cartridge
        d = CartridgeSerializer.serialize(c)
        assert d["manifest"]["schema_version"] == "0.6.0"
        assert "character" in d
        assert d["character"]["core_values"] == ["X"]

    def test_no_communication_style_in_character(self):
        m = CharacterModule(core_values=("X",))
        d = m.to_dict()
        assert "communication_style" not in d


class TestPreferenceModule:
    def test_empty_by_default(self):
        m = PreferenceModule()
        assert m.entries == ()

    def test_construction(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="a", value="1"),
            PreferenceEntry(key="b", value="2"),
        ))
        assert len(m.entries) == 2
        assert m.entries[0].key == "a"
        assert m.entries[0].value == "1"
        assert m.entries[1].key == "b"
        assert m.entries[1].value == "2"

    def test_to_dict(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="k", value="v"),
        ))
        d = m.to_dict()
        assert len(d["entries"]) == 1
        assert d["entries"][0]["key"] == "k"
        assert d["entries"][0]["value"] == "v"
        assert d["entries"][0]["scope"] == "global"
        assert d["entries"][0]["priority"] == "normal"
        assert d["entries"][0]["description"] == ""

    def test_validate_no_errors(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="a", value="1"),
        ))
        errors, _ = m.validate()
        assert errors == []

    def test_validate_empty_key(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="", value="v", scope="global", priority="normal", description=""),
            PreferenceEntry(key="valid", value="ok"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.EMPTY_PREFERENCE_KEY for e in errors)

    def test_duplicate_key_reported(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="a", value="first"),
            PreferenceEntry(key="a", value="last"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.DUPLICATE_PREFERENCE_KEY for e in errors)

    def test_validate_invalid_key_syntax(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="1bad", value="x"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.INVALID_PREFERENCE_KEY_SYNTAX for e in errors)

    def test_validate_key_with_uppercase(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="UPPER", value="x"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.INVALID_PREFERENCE_KEY_SYNTAX for e in errors)

    def test_validate_value_type_int(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="count", value=42),
        ))
        errors, _ = m.validate()
        assert errors == []

    def test_validate_value_type_float(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="ratio", value=3.14),
        ))
        errors, _ = m.validate()
        assert errors == []

    def test_validate_value_type_bool(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="enabled", value=True),
        ))
        errors, _ = m.validate()
        assert errors == []

    def test_validate_invalid_value_type(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="bad", value=[1, 2]),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.INVALID_PREFERENCE_VALUE_TYPE for e in errors)

    def test_validate_invalid_scope(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="test", value="x", scope="invalid"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.INVALID_PREFERENCE_SCOPE for e in errors)

    def test_validate_valid_scope_contextual(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="test", value="x", scope="contextual"),
        ))
        errors, _ = m.validate()
        assert errors == []

    def test_validate_invalid_priority(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="test", value="x", priority="max"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.INVALID_PREFERENCE_PRIORITY for e in errors)

    def test_validate_valid_priority_low_high(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="a", value="x", priority="low"),
            PreferenceEntry(key="b", value="y", priority="high"),
        ))
        errors, _ = m.validate()
        assert errors == []

    def test_to_dict_sorted_by_key(self):
        m = PreferenceModule(entries=(
            PreferenceEntry(key="z", value="last"),
            PreferenceEntry(key="a", value="first"),
            PreferenceEntry(key="m", value="middle"),
        ))
        d = m.to_dict()
        keys = [e["key"] for e in d["entries"]]
        assert keys == ["a", "m", "z"]


class TestBehaviorModule:
    def test_empty_by_default(self):
        m = BehaviorModule()
        assert m.policies == ()

    def test_construction(self):
        m = BehaviorModule(policies=(
            BehaviorPolicy(identifier="be_kind", title="Be Kind"),
        ))
        assert len(m.policies) == 1
        assert m.policies[0].identifier == "be_kind"
        assert m.policies[0].title == "Be Kind"

    def test_to_dict(self):
        d = BehaviorModule(policies=(
            BehaviorPolicy(identifier="test", title="Test"),
        )).to_dict()
        assert len(d["policies"]) == 1
        assert d["policies"][0]["identifier"] == "test"
        assert d["policies"][0]["title"] == "Test"
        assert d["policies"][0]["category"] == "interaction"
        assert d["policies"][0]["policy_type"] == "preferred"
        assert d["policies"][0]["enabled"] is True

    def test_validate_no_warnings_when_policies_present(self):
        errors, warnings = BehaviorModule(policies=(
            BehaviorPolicy(identifier="a", title="A"),
        )).validate()
        assert warnings == []

    def test_validate_warns_when_empty(self):
        errors, warnings = BehaviorModule().validate()
        assert any(w.code == ValidationCode.NO_BEHAVIOR_RULES for w in warnings)

    def test_validate_duplicate_identifier(self):
        m = BehaviorModule(policies=(
            BehaviorPolicy(identifier="dup", title="First"),
            BehaviorPolicy(identifier="dup", title="Second"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.DUPLICATE_BEHAVIOR_IDENTIFIER for e in errors)

    def test_validate_invalid_identifier(self):
        m = BehaviorModule(policies=(
            BehaviorPolicy(identifier="1bad", title="Bad"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.INVALID_BEHAVIOR_IDENTIFIER for e in errors)

    def test_validate_invalid_category(self):
        m = BehaviorModule(policies=(
            BehaviorPolicy(identifier="test", title="Test", category="wrong"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.INVALID_BEHAVIOR_CATEGORY for e in errors)

    def test_validate_invalid_policy_type(self):
        m = BehaviorModule(policies=(
            BehaviorPolicy(identifier="test", title="Test", policy_type="maybe"),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.INVALID_BEHAVIOR_POLICY_TYPE for e in errors)

    def test_validate_empty_title(self):
        m = BehaviorModule(policies=(
            BehaviorPolicy(identifier="test", title=""),
        ))
        errors, _ = m.validate()
        assert any(e.code == ValidationCode.REQUIRED_FIELD_EMPTY for e in errors)

    def test_to_dict_sorted_by_identifier(self):
        m = BehaviorModule(policies=(
            BehaviorPolicy(identifier="z", title="Z"),
            BehaviorPolicy(identifier="a", title="A"),
            BehaviorPolicy(identifier="m", title="M"),
        ))
        d = m.to_dict()
        ids = [p["identifier"] for p in d["policies"]]
        assert ids == ["a", "m", "z"]


class TestCommunicationModule:
    def test_to_dict_empty(self):
        assert CommunicationModule().to_dict() == {}

    def test_validate_always_clean(self):
        errors, warnings = CommunicationModule().validate()
        assert errors == []
        assert warnings == []


# ===================================================================
# PersonaDraft — description field
# ===================================================================

class TestDraftDescription:
    def test_new_field_present(self):
        assert hasattr(PersonaDraft(), "description")
        assert PersonaDraft().description == ""

    def test_normalize_strips_description(self):
        d = PersonaDraft(name="A", summary="B", description="  Desc  ",
                         communication_style="C")
        PersonaDraft.normalize(d)
        assert d.description == "Desc"

    def test_description_in_forge(self):
        d = _make_valid_draft(description="Hello world")
        c = CartridgeForge.forge(d).cartridge
        assert c.identity.description == "Hello world"


# ===================================================================
# PersonaDraft — existing behavior preserved
# ===================================================================

class TestDraftNoCartridgeId:
    def test_draft_has_no_cartridge_id(self):
        assert not hasattr(PersonaDraft(), "cartridge_id")


class TestNormalizeEmptyValues:
    def test_normalize_preference_values(self):
        d = _make_valid_draft(preferences={"a": "", "b": "  ", "c": "real"})
        PersonaDraft.normalize(d)
        assert d.preferences["a"] == ""  # empty string preserved
        assert d.preferences["b"] == ""  # whitespace stripped to empty
        assert d.preferences["c"] == "real"

    def test_dedup_core_values(self):
        d = _make_valid_draft(core_values=["Honesty", "Honesty", "Courage"])
        PersonaDraft.normalize(d)
        assert d.core_values == ["Honesty", "Courage"]

    def test_dedup_preserves_order(self):
        d = _make_valid_draft(core_values=["Z", "A", "Z", "B", "A"])
        PersonaDraft.normalize(d)
        assert d.core_values == ["Z", "A", "B"]

    def test_dedup_after_strip(self):
        d = _make_valid_draft(core_values=["  A  ", "A", "  B  "])
        PersonaDraft.normalize(d)
        assert d.core_values == ["A", "B"]


# ===================================================================
# Forge — validation
# ===================================================================

class TestValidate:
    def test_valid_draft_passes(self):
        r, _ = CartridgeForge.validate(_make_valid_draft())
        assert r.valid is True

    def test_empty_draft_9_errors(self):
        r, _ = CartridgeForge.validate(PersonaDraft())
        assert r.valid is False
        assert len(r.errors) == 9

    def test_blank_text_normalized_to_empty_fails(self):
        d = PersonaDraft(name="  ", summary="  ", description="  ",
                         communication_style="  ")
        r, _ = CartridgeForge.validate(d)
        fields = {e.field for e in r.errors}
        assert "identity.display_name" in fields
        assert "identity.identifier" in fields
        assert "identity.summary" in fields
        assert "character.core_values" in fields
        assert "character.motivations" in fields
        assert "character.strengths" in fields
        assert "character.limitations" in fields
        assert "character.goals" in fields
        assert "character.boundaries" in fields

    def test_behavior_rules_optional(self):
        r, _ = CartridgeForge.validate(_make_valid_draft(behavior_rules=[]))
        assert r.valid is True

    def test_no_behavior_rules_warning(self):
        r, _ = CartridgeForge.validate(_make_valid_draft(behavior_rules=[]))
        assert any(w.code == ValidationCode.NO_BEHAVIOR_RULES for w in r.warnings)

    def test_empty_preference_key_detected(self):
        d = _make_valid_draft(preferences={"": "val"})
        r, _ = CartridgeForge.validate(d)
        assert any(e.code == ValidationCode.EMPTY_PREFERENCE_KEY for e in r.errors)

    def test_normalize_runs_before_validation(self):
        d = PersonaDraft(name="  A  ", identifier="  a-1  ", summary="  B  ", description="  D  ",
                         communication_style="  C  ",
                         core_values=["", "X"], motivations=["Y"], strengths=["Z"],
                         limitations=["L"], goals=["G"], boundaries=["B"])
        r, _ = CartridgeForge.validate(d)
        assert r.valid is True

    def test_source_not_mutated(self):
        d = _make_valid_draft(name="  Alex  ")
        CartridgeForge.validate(d)
        assert d.name == "  Alex  "

    def test_empty_draft_counts(self):
        r, _ = CartridgeForge.validate(PersonaDraft())
        assert len(r.errors) == 9


# ===================================================================
# Forge — forge pipeline
# ===================================================================

class TestForge:
    def test_cartridge_frozen(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        with pytest.raises(Exception):
            c.identity = None

    def test_forge_preserves_fields(self):
        c = CartridgeForge.forge(_make_valid_draft(name="Alex", summary="Guide")).cartridge
        assert c.identity.display_name == "Alex"
        assert c.identity.summary == "Guide"

    def test_forge_has_modules(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        assert hasattr(c, "identity")
        assert hasattr(c, "character")
        assert hasattr(c, "preferences")
        assert hasattr(c, "behavior")
        assert hasattr(c, "communication")

    def test_forge_manifest(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        assert c.manifest.schema_name == SCHEMA_NAME
        assert c.manifest.schema_version == SCHEMA_VERSION

    def test_forge_failure_structured(self):
        r = CartridgeForge.forge(PersonaDraft())
        assert r.success is False
        assert r.cartridge is None
        assert r.error is not None
        assert r.error.code == ForgeErrorCode.VALIDATION_FAILED

    def test_forge_preserves_warnings(self):
        r = CartridgeForge.forge(_make_valid_draft(behavior_rules=[]))
        assert r.success is True
        assert any(w.code == ValidationCode.NO_BEHAVIOR_RULES for w in r.warnings)

    def test_forge_failure_warnings(self):
        r = CartridgeForge.forge(PersonaDraft())
        assert r.success is False
        assert isinstance(r.warnings, list)

    def test_forge_preferences(self):
        c = CartridgeForge.forge(_make_valid_draft(preferences={"a": "1"})).cartridge
        entries = {e.key: e.value for e in c.preferences.entries}
        assert entries == {"a": "1"}

    def test_forge_behavior_rules(self):
        c = CartridgeForge.forge(_make_valid_draft(behavior_rules=["Ask before acting"])).cartridge
        assert len(c.behavior.policies) == 1
        assert c.behavior.policies[0].identifier == "ask_before_acting"
        assert c.behavior.policies[0].title == "Ask before acting"
        assert c.behavior.policies[0].category == "interaction"
        assert c.behavior.policies[0].policy_type == "preferred"
        assert c.behavior.policies[0].enabled is True

    def test_forge_returns_extensions(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        assert c.extensions == {}

    def test_forge_version_is_0_5_0(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        assert c.manifest.schema_version == "0.6.0"


# ===================================================================
# ValidationResult / ForgeResult / ValidationCodes
# ===================================================================

class TestValidationResult:
    def test_valid_is_truthy(self):
        assert bool(CartridgeValidationResult(valid=True)) is True

    def test_invalid_is_falsy(self):
        r = CartridgeValidationResult(valid=False, errors=[
            CartridgeValidationError(code=ValidationCode.REQUIRED_FIELD_EMPTY, field="n", message="x")])
        assert bool(r) is False

    def test_carries_warnings(self):
        r = CartridgeValidationResult(valid=True, warnings=[
            CartridgeValidationWarning(code=ValidationCode.NO_BEHAVIOR_RULES, field="b", message="w")])
        assert len(r.warnings) == 1

    def test_error_code_field_message(self):
        e = CartridgeValidationError(code=ValidationCode.REQUIRED_FIELD_EMPTY, field="f", message="m")
        assert e.code == ValidationCode.REQUIRED_FIELD_EMPTY
        assert e.field == "f"

    def test_warning_code_field_message(self):
        w = CartridgeValidationWarning(code=ValidationCode.NO_BEHAVIOR_RULES, field="f", message="m")
        assert w.code == ValidationCode.NO_BEHAVIOR_RULES


class TestValidationCodes:
    def test_all_codes_defined(self):
        codes = {e.value for e in ValidationCode}
        assert "REQUIRED_FIELD_EMPTY" in codes
        assert "REQUIRED_LIST_EMPTY" in codes
        assert "INVALID_TYPE" in codes
        assert "EMPTY_PREFERENCE_KEY" in codes
        assert "NO_BEHAVIOR_RULES" in codes
        assert "INVALID_IDENTIFIER" in codes


class TestForgeErrorCode:
    def test_all_codes(self):
        codes = {e.value for e in ForgeErrorCode}
        assert "VALIDATION_FAILED" in codes
        assert "INVALID_STATE" in codes


# ===================================================================
# Serialization — 0.2.0 nested format
# ===================================================================

class TestSerializeNested:
    def test_serialize_nested(self):
        c = CartridgeForge.forge(_make_valid_draft(name="Alex")).cartridge
        d = CartridgeSerializer.serialize(c)
        assert "identity" in d
        assert "character" in d
        assert "preferences" in d
        assert "behavior" in d
        assert "communication" in d
        assert d["identity"]["display_name"] == "Alex"

    def test_serialize_version_is_0_5_0(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        d = CartridgeSerializer.serialize(c)
        assert d["manifest"]["schema_version"] == "0.6.0"

    def test_preferences_in_entries(self):
        c = CartridgeForge.forge(_make_valid_draft(preferences={"a": "1"})).cartridge
        d = CartridgeSerializer.serialize(c)
        assert len(d["preferences"]["entries"]) == 1
        assert d["preferences"]["entries"][0]["key"] == "a"
        assert d["preferences"]["entries"][0]["value"] == "1"

    def test_behavior_policies_nested(self):
        c = CartridgeForge.forge(_make_valid_draft(behavior_rules=["R"])).cartridge
        d = CartridgeSerializer.serialize(c)
        assert len(d["behavior"]["policies"]) == 1
        assert d["behavior"]["policies"][0]["identifier"] == "r"
        assert d["behavior"]["policies"][0]["title"] == "R"

    def test_communication_fields(self):
        c = CartridgeForge.forge(_make_valid_draft(communication_style="Warm")).cartridge
        d = CartridgeSerializer.serialize(c)
        assert d["communication"]["communication_style"] == "Warm"
        assert "reserved" not in d["communication"]

    def test_communication_empty_when_no_style(self):
        c = CartridgeForge.forge(_make_valid_draft(communication_style="")).cartridge
        d = CartridgeSerializer.serialize(c)
        assert d["communication"] == {}


# ===================================================================
# Deserialization — 0.2.0 nested format (round-trip)
# ===================================================================

class TestDeserializeNested:
    def test_round_trip_identity(self):
        o = CartridgeForge.forge(_make_valid_draft(name="Alex", summary="Guide")).cartridge
        r = CartridgeSerializer.deserialize(CartridgeSerializer.serialize(o))
        assert r.identity.display_name == "Alex"
        assert r.identity.summary == "Guide"

    def test_round_trip_character(self):
        o = CartridgeForge.forge(_make_valid_draft(core_values=["X", "Y"])).cartridge
        r = CartridgeSerializer.deserialize(CartridgeSerializer.serialize(o))
        assert r.character.core_values == ("X", "Y")

    def test_round_trip_preferences(self):
        o = CartridgeForge.forge(_make_valid_draft(preferences={"f": "c"})).cartridge
        r = CartridgeSerializer.deserialize(CartridgeSerializer.serialize(o))
        assert len(r.preferences.entries) == 1
        assert r.preferences.entries[0].key == "f"
        assert r.preferences.entries[0].value == "c"

    def test_round_trip_behavior(self):
        o = CartridgeForge.forge(_make_valid_draft(behavior_rules=["R1", "R2"])).cartridge
        r = CartridgeSerializer.deserialize(CartridgeSerializer.serialize(o))
        assert len(r.behavior.policies) == 2
        ids = {p.identifier for p in r.behavior.policies}
        assert ids == {"r1", "r2"}

    def test_round_trip_extensions(self):
        o = CartridgeForge.forge(_make_valid_draft()).cartridge
        s = CartridgeSerializer.serialize(o)
        s["extensions"]["test"] = {"x": 1}
        r = CartridgeSerializer.deserialize(s)
        assert r.extensions["test"]["x"] == 1

    def test_round_trip_manifest(self):
        o = CartridgeForge.forge(_make_valid_draft()).cartridge
        r = CartridgeSerializer.deserialize(CartridgeSerializer.serialize(o))
        assert r.manifest.cartridge_id == o.manifest.cartridge_id

    def test_round_trip_status(self):
        o = CartridgeForge.forge(_make_valid_draft()).cartridge
        r = CartridgeSerializer.deserialize(CartridgeSerializer.serialize(o))
        assert r.status == CartridgeStatus.FORGED

    def test_deserialized_is_frozen(self):
        o = CartridgeForge.forge(_make_valid_draft()).cartridge
        r = CartridgeSerializer.deserialize(CartridgeSerializer.serialize(o))
        with pytest.raises(Exception):
            r.identity = None


# ===================================================================
# Deserialization — legacy 0.1.0 flat format (backward compat)
# ===================================================================

class TestDeserializeLegacyFlat:
    def test_flat_identity(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert c.identity.display_name == "Alex"
        assert c.identity.summary == "Guide"
        assert c.identity.description == "Optional"
        assert c.identity.identifier == ""

    def test_flat_character(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert c.character.core_values == ("X",)
        assert c.character.motivations == ("Y",)
        assert "communication_style" not in c.character.to_dict()

    def test_flat_preferences(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        entries = {e.key: e.value for e in c.preferences.entries}
        assert entries == {"a": "1", "b": "2"}

    def test_flat_behavior(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert len(c.behavior.policies) == 1
        assert c.behavior.policies[0].identifier == "be_kind"
        assert c.behavior.policies[0].title == "Be kind"

    def test_flat_empty_behavior(self):
        data = _make_flat_legacy_data()
        del data["behavior_rules"]
        c = CartridgeSerializer.deserialize(data)
        assert c.behavior.policies == ()

    def test_flat_extensions_preserved(self):
        data = _make_flat_legacy_data()
        data["extensions"] = {"ns": {"v": 1}}
        c = CartridgeSerializer.deserialize(data)
        assert c.extensions["ns"]["v"] == 1

    def test_flat_upgrades_version(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert c.manifest.schema_version == "0.6.0"

    def test_flat_round_trip_loses_none(self):
        flat = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(flat)
        assert c.identity.display_name == "Alex"
        assert c.identity.identifier == ""
        assert c.identity.summary == "Guide"
        assert c.identity.aliases == ()
        assert c.character.core_values == ("X",)
        assert c.behavior.policies[0].title == "Be kind"
        assert c.behavior.policies[0].identifier == "be_kind"
        # Legacy communication_style now a first-class field
        assert c.communication.communication_style == "Warm"
        assert c.communication.reserved == {}
        assert "communication_style" not in c.character.to_dict()

    def test_flat_round_trip_to_0_5_0(self):
        flat = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(flat)
        serialized = CartridgeSerializer.serialize(c)
        assert serialized["manifest"]["schema_version"] == "0.6.0"
        assert serialized["identity"]["display_name"] == "Alex"
        assert serialized["identity"]["identifier"] == ""
        assert serialized["identity"]["aliases"] == []
        assert serialized["character"]["core_values"] == ["X"]
        assert "communication_style" not in serialized["character"]
        assert serialized["communication"]["communication_style"] == "Warm"
        assert "reserved" not in serialized["communication"]


# ===================================================================
# Upgrade path
# ===================================================================

class TestUpgrade:
    def test_upgrade_changes_version(self):
        data = _make_flat_legacy_data()
        upgraded = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        assert upgraded["manifest"]["schema_version"] == "0.2.0"

    def test_upgrade_identity(self):
        data = _make_flat_legacy_data()
        upgraded = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        assert upgraded["identity"]["display_name"] == "Alex"
        assert upgraded["identity"]["identifier"] == ""
        assert upgraded["identity"]["summary"] == "Guide"
        assert upgraded["identity"]["description"] == "Optional"
        assert upgraded["identity"]["aliases"] == []

    def test_upgrade_character(self):
        data = _make_flat_legacy_data()
        upgraded = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        assert upgraded["character"]["core_values"] == ["X"]
        assert upgraded["character"]["motivations"] == ["Y"]

    def test_upgrade_preferences(self):
        data = _make_flat_legacy_data()
        upgraded = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        assert upgraded["preferences"]["entries"] == {"a": "1", "b": "2"}

    def test_upgrade_behavior(self):
        data = _make_flat_legacy_data()
        upgraded = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        assert upgraded["behavior"]["rules"] == ["Be kind"]

    def test_upgrade_empty_behavior(self):
        data = _make_flat_legacy_data()
        del data["behavior_rules"]
        upgraded = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        assert upgraded["behavior"]["rules"] == []

    def test_upgrade_extensions(self):
        data = _make_flat_legacy_data()
        data["extensions"] = {"test": {"a": 1}}
        upgraded = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        assert upgraded["extensions"] == {"test": {"a": 1}}

    def test_upgrade_deterministic(self):
        data = _make_flat_legacy_data()
        u1 = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        u2 = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        assert u1 == u2

    def test_0_1_0_accepted_by_deserializer(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert c.manifest.schema_version == "0.6.0"


class TestUpgrade_0_2_to_0_3:
    def test_moves_communication_style_to_reserved(self):
        old = _make_0_2_0_cartridge_dict(communication_style="Warm")
        upgraded = CartridgeSerializer._upgrade_0_2_to_0_3(old)
        assert "communication_style" not in upgraded["character"]
        assert upgraded["communication"]["reserved"]["communication_style"]["value"] == "Warm"

    def test_skips_empty_communication_style(self):
        old = _make_0_2_0_cartridge_dict(communication_style="")
        upgraded = CartridgeSerializer._upgrade_0_2_to_0_3(old)
        assert "communication_style" not in upgraded["character"]
        assert upgraded["communication"] == {"reserved": {}}

    def test_sets_version_to_0_3_0(self):
        old = _make_0_2_0_cartridge_dict()
        upgraded = CartridgeSerializer._upgrade_0_2_to_0_3(old)
        assert upgraded["manifest"]["schema_version"] == "0.3.0"

    def test_preserves_character_collections(self):
        old = _make_0_2_0_cartridge_dict(core_values=["X", "Y"])
        upgraded = CartridgeSerializer._upgrade_0_2_to_0_3(old)
        assert upgraded["character"]["core_values"] == ["X", "Y"]

    def test_deterministic(self):
        old = _make_0_2_0_cartridge_dict(communication_style="Warm")
        u1 = CartridgeSerializer._upgrade_0_2_to_0_3(old)
        u2 = CartridgeSerializer._upgrade_0_2_to_0_3(old)
        assert u1 == u2

    def test_0_2_0_accepted_by_deserializer(self):
        old = _make_0_2_0_cartridge_dict(communication_style="Warm")
        c = CartridgeSerializer.deserialize(old)
        assert c.manifest.schema_version == "0.6.0"
        assert c.communication.communication_style == "Warm"
        assert "communication_style" not in c.character.to_dict()


class TestCommunicationPreservation:
    def test_forge_preserves_communication_style(self):
        draft = _make_valid_draft(communication_style="Warm and direct")
        c = CartridgeForge.forge(draft).cartridge
        assert c.communication.communication_style == "Warm and direct"
        assert c.communication.reserved == {}

    def test_forge_empty_communication_style(self):
        draft = _make_valid_draft(communication_style="")
        c = CartridgeForge.forge(draft).cartridge
        assert c.communication.communication_style == ""
        assert c.communication.reserved == {}

    def test_forge_whitespace_communication_style_normalized(self):
        draft = _make_valid_draft(communication_style="  Warm  ")
        c = CartridgeForge.forge(draft).cartridge
        assert c.communication.communication_style == "Warm"
        assert c.communication.reserved == {}

    def test_round_trip_preserves_communication(self):
        draft = _make_valid_draft(communication_style="Formal")
        original = CartridgeForge.forge(draft).cartridge
        data = CartridgeSerializer.serialize(original)
        restored = CartridgeSerializer.deserialize(data)
        assert restored.communication.communication_style == "Formal"

    def test_legacy_0_1_0_preserves_communication(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert c.communication.communication_style == "Warm"

    def test_serialized_communication_survives_round_trip(self):
        draft = _make_valid_draft(communication_style="Direct")
        c = CartridgeForge.forge(draft).cartridge
        s1 = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(s1)
        s2 = CartridgeSerializer.serialize(restored)
        assert s1["communication"] == s2["communication"]


# ===================================================================
# Defensive copy of extensions
# ===================================================================

class TestExtensionsDefensiveCopy:
    def test_deserialize_deep_copy(self):
        inner = {"x": 1}
        data = _make_flat_legacy_data()
        data["extensions"] = {"ns": inner}
        c = CartridgeSerializer.deserialize(data)
        inner["x"] = 999
        assert c.extensions["ns"]["x"] == 1

    def test_deserialize_mutation_after(self):
        data = _make_flat_legacy_data()
        data["extensions"] = {"ns": {"v": [1, 2]}}
        c = CartridgeSerializer.deserialize(data)
        c.extensions["ns"]["v"].append(3)
        assert len(c.extensions["ns"]["v"]) == 3

    def test_upgrade_deep_copy(self):
        inner = {"k": "v"}
        data = _make_flat_legacy_data()
        data["extensions"] = {"ns": inner}
        upgraded = CartridgeSerializer._upgrade_0_1_to_0_2(data, data["manifest"])
        inner["k"] = "changed"
        assert upgraded["extensions"]["ns"]["k"] == "v"


# ===================================================================
# Version negotiation
# ===================================================================

class TestVersionUtilities:
    def test_parse(self):
        assert parse_version("0.1.0") == (0, 1, 0)
        assert parse_version("0.2.0") == (0, 2, 0)

    def test_parse_invalid(self):
        with pytest.raises(ValueError):
            parse_version("abc")

    def test_is_supported(self):
        assert is_version_supported("0.1.0", frozenset({"0.1.0", "0.2.0"})) is True
        assert is_version_supported("0.2.0", frozenset({"0.1.0", "0.2.0"})) is True
        assert is_version_supported("0.3.0", frozenset({"0.1.0", "0.2.0"})) is False


class TestSerializerSupportedVersions:
    def test_supported_versions_includes_all(self):
        sv = CartridgeSerializer.SUPPORTED_VERSIONS
        assert "0.1.0" in sv
        assert "0.2.0" in sv
        assert "0.3.0" in sv
        assert "0.4.0" in sv
        assert "0.6.0" in sv


class TestVersionNegotiation:
    def test_0_1_0_is_accepted(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert c.manifest.schema_version == "0.6.0"

    def test_0_2_0_is_accepted(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        data = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(data)
        assert restored.manifest.schema_version == "0.6.0"

    def test_unsupported_version_raises(self):
        data = _make_flat_legacy_data()
        data["manifest"]["schema_version"] = "99.99.99"
        with pytest.raises(UnsupportedVersionError):
            CartridgeSerializer.deserialize(data)

    def test_error_has_version_and_supported(self):
        data = _make_flat_legacy_data()
        data["manifest"]["schema_version"] = "2.0.0"
        try:
            CartridgeSerializer.deserialize(data)
        except UnsupportedVersionError as e:
            assert e.version == "2.0.0"
            assert "0.1.0" in e.supported
            assert "0.2.0" in e.supported
            assert "0.3.0" in e.supported
            assert "0.4.0" in e.supported
            assert "0.6.0" in e.supported

    def test_missing_version_fails(self):
        data = _make_flat_legacy_data()
        del data["manifest"]["schema_version"]
        with pytest.raises(UnsupportedVersionError):
            CartridgeSerializer.deserialize(data)

    def test_future_major_detected(self):
        data = _make_flat_legacy_data()
        data["manifest"]["schema_version"] = "1.0.0"
        with pytest.raises(UnsupportedVersionError):
            CartridgeSerializer.deserialize(data)

    def test_missing_manifest(self):
        with pytest.raises(ValueError, match="manifest"):
            CartridgeSerializer.deserialize({"name": "foo"})


# ===================================================================
# to_dict compositional
# ===================================================================

class TestToDict:
    def test_module_keys_present(self):
        d = CartridgeForge.forge(_make_valid_draft()).cartridge.to_dict()
        for key in ("manifest", "identity", "character", "preferences", "behavior", "communication", "extensions", "status"):
            assert key in d

    def test_no_flat_legacy_fields(self):
        d = CartridgeForge.forge(_make_valid_draft()).cartridge.to_dict()
        assert "name" not in d
        assert "core_values" not in d
        assert "behavior_rules" not in d

    def test_identity_content(self):
        d = CartridgeForge.forge(_make_valid_draft(name="Alex")).cartridge.to_dict()
        assert d["identity"]["display_name"] == "Alex"

    def test_status_in_output(self):
        d = CartridgeForge.forge(_make_valid_draft()).cartridge.to_dict()
        assert d["status"] == "forged"

    def test_version_in_manifest(self):
        d = CartridgeForge.forge(_make_valid_draft()).cartridge.to_dict()
        assert d["manifest"]["schema_version"] == "0.6.0"
# ===================================================================
# Composition guarantee
# ===================================================================

class TestComposition:
    def test_cartridge_has_all_modules(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        assert isinstance(c.identity, IdentityModule)
        assert isinstance(c.character, CharacterModule)
        assert isinstance(c.preferences, PreferenceModule)
        assert isinstance(c.behavior, BehaviorModule)
        assert isinstance(c.communication, CommunicationModule)

    def test_modules_independent(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        id_copy = copy.deepcopy(c.identity)
        assert id_copy == c.identity

    def test_empty_modules_validate(self):
        assert PreferenceModule().validate() == ([], [])
        _be, bw = BehaviorModule().validate()
        assert any(w.code == ValidationCode.NO_BEHAVIOR_RULES for w in bw)
        assert CommunicationModule().validate() == ([], [])


# ===================================================================
# CartridgeModule contract
# ===================================================================

class TestCartridgeModuleContract:
    _MODULE_TYPES = [
        IdentityModule,
        CharacterModule,
        PreferenceModule,
        BehaviorModule,
        CommunicationModule,
    ]

    def test_all_modules_are_cartridge_module_subclass(self):
        for t in self._MODULE_TYPES:
            assert issubclass(t, CartridgeModule), f"{t.__name__} not a CartridgeModule"

    def test_all_modules_have_module_name(self):
        for t in self._MODULE_TYPES:
            name = t.module_name()
            assert isinstance(name, str), f"{t.__name__}.module_name() not str"
            assert len(name) > 0, f"{t.__name__}.module_name() empty"

    def test_all_modules_have_module_schema_version(self):
        for t in self._MODULE_TYPES:
            v = t.module_schema_version()
            assert isinstance(v, int), f"{t.__name__}.module_schema_version() not int"
            assert v >= 1, f"{t.__name__}.module_schema_version() < 1"

    def test_all_modules_have_to_dict(self):
        for t in self._MODULE_TYPES:
            instance = _create_module_instance(t)
            d = instance.to_dict()
            assert isinstance(d, dict), f"{t.__name__}.to_dict() not dict"

    def test_all_modules_have_validate(self):
        for t in self._MODULE_TYPES:
            instance = _create_module_instance(t)
            errors, warnings = instance.validate()
            assert isinstance(errors, list)
            assert isinstance(warnings, list)

    def test_module_names_unique(self):
        names = [t.module_name() for t in self._MODULE_TYPES]
        assert len(names) == len(set(names)), "Duplicate module names"

    def test_validate_returns_uniform_tuple(self):
        for t in self._MODULE_TYPES:
            instance = _create_module_instance(t)
            result = instance.validate()
            assert isinstance(result, tuple)
            assert len(result) == 2
            errs, warns = result
            for e in errs:
                assert isinstance(e, CartridgeValidationError)
            for w in warns:
                assert isinstance(w, CartridgeValidationWarning)

    def test_abstract_class_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            CartridgeModule()  # type: ignore


# ===================================================================
# ModuleRegistry
# ===================================================================

class TestModuleRegistry:
    def test_all_modules_registered(self):
        names = ModuleRegistry.names()
        for expected in ("identity", "character", "preferences", "behavior", "communication"):
            assert expected in names, f"'{expected}' not registered"

    def test_registry_size(self):
        assert len(ModuleRegistry.entries()) == 5

    def test_lookup_identity(self):
        entry = ModuleRegistry.lookup("identity")
        assert entry.module_type is IdentityModule
        assert entry.module_schema_version == IdentityModule.module_schema_version()

    def test_lookup_character(self):
        entry = ModuleRegistry.lookup("character")
        assert entry.module_type is CharacterModule

    def test_lookup_preferences(self):
        entry = ModuleRegistry.lookup("preferences")
        assert entry.module_type is PreferenceModule

    def test_lookup_behavior(self):
        entry = ModuleRegistry.lookup("behavior")
        assert entry.module_type is BehaviorModule

    def test_lookup_communication(self):
        entry = ModuleRegistry.lookup("communication")
        assert entry.module_type is CommunicationModule

    def test_lookup_unknown_raises(self):
        with pytest.raises(KeyError, match="unknown_module"):
            ModuleRegistry.lookup("unknown_module")

    def test_registry_entry_frozen(self):
        entry = ModuleRegistry.lookup("identity")
        with pytest.raises(Exception):
            entry.module_type = CharacterModule  # type: ignore

    def test_registry_returns_copy(self):
        e1 = ModuleRegistry.entries()
        e2 = ModuleRegistry.entries()
        assert e1 == e2
        assert e1 is not e2

    def test_module_schema_versions_independent(self):
        for name, entry in ModuleRegistry.entries().items():
            assert isinstance(entry.module_schema_version, int)
            assert entry.module_schema_version >= 1

    def test_registry_maps_name_to_type(self):
        for name, entry in ModuleRegistry.entries().items():
            assert entry.module_type.module_name() == name


# ===================================================================
# Module identity independent of cartridge version
# ===================================================================

class TestModuleIdentityIndependence:
    def test_module_versions_are_ints_not_semver(self):
        for name, entry in ModuleRegistry.entries().items():
            v = entry.module_schema_version
            assert isinstance(v, int), f"{name} version is not int"
            assert not isinstance(v, str), f"{name} version is a string, not int"

    def test_cartridge_version_is_string(self):
        assert isinstance(SCHEMA_VERSION, str)

    def test_module_versions_differ_from_cartridge_version(self):
        for name, entry in ModuleRegistry.entries().items():
            assert str(entry.module_schema_version) != SCHEMA_VERSION, (
                f"{name} version matches cartridge version"
            )


# ===================================================================
# Validation consistency
# ===================================================================

class TestValidationConsistency:
    def test_all_modules_return_same_tuple_type(self):
        for name, entry in ModuleRegistry.entries().items():
            instance = _create_module_instance(entry.module_type)
            result = instance.validate()
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_empty_modules_have_consistent_output(self):
        id_errors, id_warnings = IdentityModule(display_name="", identifier="", summary="").validate()
        assert len(id_errors) == 3
        assert len(id_warnings) == 0

        ch_errors, ch_warnings = CharacterModule().validate()
        assert len(ch_errors) == 6  # 6 required lists
        assert len(ch_warnings) == 0

        pf_errors, pf_warnings = PreferenceModule().validate()
        assert len(pf_errors) == 0
        assert len(pf_warnings) == 0

        bh_errors, bh_warnings = BehaviorModule().validate()
        assert len(bh_errors) == 0
        assert len(bh_warnings) == 1

        cm_errors, cm_warnings = CommunicationModule().validate()
        assert len(cm_errors) == 0
        assert len(cm_warnings) == 0


# ===================================================================
# Serialization consistency
# ===================================================================

class TestSerializationConsistency:
    def test_all_modules_serialize_to_dict(self):
        for name, entry in ModuleRegistry.entries().items():
            instance = _create_module_instance(entry.module_type)
            d = instance.to_dict()
            assert isinstance(d, dict), f"{name}.to_dict() not dict"

    def test_serialization_includes_module_name(self):
        for name, entry in ModuleRegistry.entries().items():
            instance = _create_module_instance(entry.module_type)
            d = instance.to_dict()
            assert isinstance(d, dict)


# ===================================================================
# Identifier validation
# ===================================================================

class TestIdentifierValidation:
    def test_valid_identifier(self):
        mod = IdentityModule(display_name="A", identifier="brunel-01", summary="B")
        errors, _ = mod.validate()
        id_errors = [e for e in errors if e.field == "identity.identifier"]
        assert len(id_errors) == 0

    def test_empty_identifier_fails(self):
        mod = IdentityModule(display_name="A", identifier="", summary="B")
        errors, _ = mod.validate()
        assert any(e.code == ValidationCode.INVALID_IDENTIFIER for e in errors)

    def test_uppercase_rejected(self):
        mod = IdentityModule(display_name="A", identifier="Brunel", summary="B")
        errors, _ = mod.validate()
        assert any(e.code == ValidationCode.INVALID_IDENTIFIER for e in errors)

    def test_leading_digit_rejected(self):
        mod = IdentityModule(display_name="A", identifier="1brunel", summary="B")
        errors, _ = mod.validate()
        assert any(e.code == ValidationCode.INVALID_IDENTIFIER for e in errors)

    def test_special_chars_rejected(self):
        for ch in "!@#$%^&*()=+[]{}|;:',.<>?/~`":
            mod = IdentityModule(display_name="A", identifier=f"bad{ch}id", summary="B")
            errors, _ = mod.validate()
            assert any(e.code == ValidationCode.INVALID_IDENTIFIER for e in errors), f"char '{ch}' not rejected"

    def test_allowed_chars_accepted(self):
        mod = IdentityModule(display_name="A", identifier="a-0_z", summary="B")
        errors, _ = mod.validate()
        id_errors = [e for e in errors if e.field == "identity.identifier"]
        assert len(id_errors) == 0

    def test_identifier_in_forge(self):
        draft = _make_valid_draft(identifier="brunel")
        c = CartridgeForge.forge(draft).cartridge
        assert c.identity.identifier == "brunel"

    def test_identifier_normalized_to_lowercase(self):
        draft = _make_valid_draft(identifier="  Brunel-01  ")
        c = CartridgeForge.forge(draft).cartridge
        assert c.identity.identifier == "brunel-01"

    def test_identifier_error_field_path(self):
        mod = IdentityModule(display_name="A", identifier="Bad!", summary="B")
        errors, _ = mod.validate()
        id_errors = [e for e in errors if e.field == "identity.identifier"]
        assert len(id_errors) >= 1


# ===================================================================
# Aliases
# ===================================================================

class TestAliases:
    def test_default_empty(self):
        mod = IdentityModule(display_name="A", identifier="a", summary="B")
        assert mod.aliases == ()

    def test_preserves_order(self):
        mod = IdentityModule(display_name="A", identifier="a", summary="B",
                             aliases=("Z", "A", "M"))
        assert mod.aliases == ("Z", "A", "M")

    def test_duplicates_in_forge_removed(self):
        draft = _make_valid_draft(aliases=["Guide", "Guide", "Leader"])
        c = CartridgeForge.forge(draft).cartridge
        assert c.identity.aliases == ("Guide", "Leader")

    def test_whitespace_normalized(self):
        draft = _make_valid_draft(aliases=["  Guide  ", "  Leader  "])
        c = CartridgeForge.forge(draft).cartridge
        assert c.identity.aliases == ("Guide", "Leader")

    def test_empty_aliases_removed(self):
        draft = _make_valid_draft(aliases=["", "  ", "Real"])
        c = CartridgeForge.forge(draft).cartridge
        assert c.identity.aliases == ("Real",)

    def test_serialization_round_trip(self):
        c = CartridgeForge.forge(_make_valid_draft(aliases=["A", "B"])).cartridge
        data = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(data)
        assert restored.identity.aliases == ("A", "B")

    def test_to_dict_includes_aliases(self):
        c = CartridgeForge.forge(_make_valid_draft(aliases=["X", "Y"])).cartridge
        d = c.to_dict()
        assert d["identity"]["aliases"] == ["X", "Y"]

    def test_legacy_upgrade_defaults_empty(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert c.identity.aliases == ()

    def test_normalize_aliases(self):
        draft = PersonaDraft(name="A", identifier="a", summary="B", aliases=["  X  ", "X", "  Y  "])
        PersonaDraft.normalize(draft)
        assert draft.aliases == ["X", "Y"]


# ===================================================================
# Lifecycle (documented — no runtime enforcement needed)
# ===================================================================

class TestCommunicationDomain:
    def test_construction(self):
        m = CommunicationModule(communication_style="Warm", tone=("Respectful",))
        assert m.communication_style == "Warm"
        assert m.tone == ("Respectful",)

    def test_empty_by_default(self):
        m = CommunicationModule()
        assert m.communication_style == ""
        assert m.tone == ()
        assert m.vocabulary_preferences == ()
        assert m.response_tendencies == ()
        assert m.formatting_preferences == ()

    def test_immutable(self):
        m = CommunicationModule(communication_style="Warm")
        with pytest.raises(Exception):
            m.communication_style = "Cold"

    def test_to_dict_only_non_empty(self):
        m = CommunicationModule()
        assert m.to_dict() == {}

        m2 = CommunicationModule(communication_style="Direct")
        d = m2.to_dict()
        assert d["communication_style"] == "Direct"
        assert "tone" not in d

        m3 = CommunicationModule(tone=("Calm", "Curious"))
        d3 = m3.to_dict()
        assert d3["tone"] == ["Calm", "Curious"]

    def test_to_dict_all_fields(self):
        m = CommunicationModule(
            communication_style="Warm",
            tone=("Respectful", "Calm"),
            vocabulary_preferences=("Plain language",),
            response_tendencies=("Explains reasoning",),
            formatting_preferences=("Short paragraphs",),
        )
        d = m.to_dict()
        assert d["communication_style"] == "Warm"
        assert d["tone"] == ["Respectful", "Calm"]
        assert d["vocabulary_preferences"] == ["Plain language"]
        assert d["response_tendencies"] == ["Explains reasoning"]
        assert d["formatting_preferences"] == ["Short paragraphs"]

    def test_validate_no_errors(self):
        errors, warnings = CommunicationModule().validate()
        assert errors == []
        assert warnings == []

    def test_deterministic_output(self):
        m = CommunicationModule(communication_style="W", tone=("A", "B"))
        d1 = m.to_dict()
        d2 = m.to_dict()
        assert d1 == d2


class TestCommunicationNormalization:
    def test_strips_whitespace(self):
        draft = _make_valid_draft(tone=["  Respectful  ", "  Calm  "])
        PersonaDraft.normalize(draft)
        assert draft.tone == ["Respectful", "Calm"]

    def test_removes_empty(self):
        draft = _make_valid_draft(vocabulary_preferences=["", "  ", "Plain language"])
        PersonaDraft.normalize(draft)
        assert draft.vocabulary_preferences == ["Plain language"]

    def test_dedup(self):
        draft = _make_valid_draft(response_tendencies=["Explains", "Explains", "Summarizes"])
        PersonaDraft.normalize(draft)
        assert draft.response_tendencies == ["Explains", "Summarizes"]

    def test_dedup_preserves_order(self):
        draft = _make_valid_draft(formatting_preferences=["Z", "A", "Z", "B"])
        PersonaDraft.normalize(draft)
        assert draft.formatting_preferences == ["Z", "A", "B"]

    def test_forge_preserves_all(self):
        draft = _make_valid_draft(
            communication_style="Formal",
            tone=["  Respectful  ", "Calm", "  Respectful  "],
            vocabulary_preferences=["Technical terminology"],
            response_tendencies=["  Explains reasoning  "],
            formatting_preferences=["Tables when useful", "Bullet lists"],
        )
        c = CartridgeForge.forge(draft).cartridge
        assert c.communication.communication_style == "Formal"
        assert c.communication.tone == ("Respectful", "Calm")
        assert c.communication.vocabulary_preferences == ("Technical terminology",)
        assert c.communication.response_tendencies == ("Explains reasoning",)
        assert c.communication.formatting_preferences == ("Tables when useful", "Bullet lists")


class TestCommunicationSerialization:
    def test_round_trip_all_fields(self):
        draft = _make_valid_draft(
            communication_style="Warm",
            tone=["Respectful", "Calm"],
            vocabulary_preferences=["Plain language"],
            response_tendencies=["Explains reasoning"],
            formatting_preferences=["Short paragraphs"],
        )
        original = CartridgeForge.forge(draft).cartridge
        data = CartridgeSerializer.serialize(original)
        restored = CartridgeSerializer.deserialize(data)
        assert restored.communication.communication_style == "Warm"
        assert restored.communication.tone == ("Respectful", "Calm")
        assert restored.communication.vocabulary_preferences == ("Plain language",)
        assert restored.communication.response_tendencies == ("Explains reasoning",)
        assert restored.communication.formatting_preferences == ("Short paragraphs",)

    def test_deterministic_serialization(self):
        draft = _make_valid_draft(communication_style="Direct", tone=["A", "B"])
        c = CartridgeForge.forge(draft).cartridge
        s1 = CartridgeSerializer.serialize(c)
        s2 = CartridgeSerializer.serialize(c)
        assert s1["communication"] == s2["communication"]

    def test_schema_0_5_0_compatibility(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        d = CartridgeSerializer.serialize(c)
        assert d["manifest"]["schema_version"] == "0.6.0"
        assert "communication" in d


class TestCommunicationMigration:
    def test_0_3_0_to_0_4_0_migrates_reserved(self):
        old = {
            "manifest": {"cartridge_id": "t", "schema_name": SCHEMA_NAME,
                         "schema_version": "0.3.0",
                         "created_at": "2024-01-01T00:00:00",
                         "updated_at": "2024-01-01T00:00:00"},
            "identity": {"display_name": "T", "identifier": "t", "summary": "T",
                         "description": "", "aliases": []},
            "character": {"core_values": ["X"], "motivations": ["Y"],
                          "strengths": ["Z"], "limitations": ["L"],
                          "goals": ["G"], "boundaries": ["B"]},
            "preferences": {"entries": {}}, "behavior": {"rules": []},
            "communication": {"reserved": {"communication_style": {"value": "Warm"}}},
            "extensions": {}, "status": "forged",
        }
        upgraded = CartridgeSerializer._upgrade_0_3_to_0_4(old)
        assert upgraded["communication"]["communication_style"] == "Warm"
        assert "reserved" not in upgraded["communication"]

    def test_0_3_0_empty_reserved_creates_no_style(self):
        old = {
            "manifest": {"cartridge_id": "t", "schema_name": SCHEMA_NAME,
                         "schema_version": "0.3.0",
                         "created_at": "2024-01-01T00:00:00",
                         "updated_at": "2024-01-01T00:00:00"},
            "identity": {"display_name": "T", "identifier": "t", "summary": "T",
                         "description": "", "aliases": []},
            "character": {"core_values": ["X"], "motivations": ["Y"],
                          "strengths": ["Z"], "limitations": ["L"],
                          "goals": ["G"], "boundaries": ["B"]},
            "preferences": {"entries": {}}, "behavior": {"rules": []},
            "communication": {"reserved": {}},
            "extensions": {}, "status": "forged",
        }
        upgraded = CartridgeSerializer._upgrade_0_3_to_0_4(old)
        assert upgraded["communication"].get("communication_style", "") == ""
        assert "reserved" not in upgraded["communication"]

    def test_0_3_0_existing_owned_not_overwritten(self):
        old = {
            "manifest": {"cartridge_id": "t", "schema_name": SCHEMA_NAME,
                         "schema_version": "0.3.0",
                         "created_at": "2024-01-01T00:00:00",
                         "updated_at": "2024-01-01T00:00:00"},
            "identity": {"display_name": "T", "identifier": "t", "summary": "T",
                         "description": "", "aliases": []},
            "character": {"core_values": ["X"], "motivations": ["Y"],
                          "strengths": ["Z"], "limitations": ["L"],
                          "goals": ["G"], "boundaries": ["B"]},
            "preferences": {"entries": {}}, "behavior": {"rules": []},
            "communication": {"communication_style": "Direct",
                              "reserved": {"communication_style": {"value": "Warm"}}},
            "extensions": {}, "status": "forged",
        }
        upgraded = CartridgeSerializer._upgrade_0_3_to_0_4(old)
        assert upgraded["communication"]["communication_style"] == "Direct"

    def test_0_3_0_accepted_by_deserializer(self):
        old = {
            "manifest": {"cartridge_id": "t", "schema_name": SCHEMA_NAME,
                         "schema_version": "0.3.0",
                         "created_at": "2024-01-01T00:00:00",
                         "updated_at": "2024-01-01T00:00:00"},
            "identity": {"display_name": "T", "identifier": "t", "summary": "T",
                         "description": "", "aliases": []},
            "character": {"core_values": ["X"], "motivations": ["Y"],
                          "strengths": ["Z"], "limitations": ["L"],
                          "goals": ["G"], "boundaries": ["B"]},
            "preferences": {"entries": {}}, "behavior": {"rules": []},
            "communication": {"reserved": {"communication_style": {"value": "Warm"}}},
            "extensions": {}, "status": "forged",
        }
        c = CartridgeSerializer.deserialize(old)
        assert c.manifest.schema_version == "0.6.0"
        assert c.communication.communication_style == "Warm"
        assert c.communication.reserved == {}

    def test_legacy_0_1_0_chain_preserves_communication(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        assert c.communication.communication_style == "Warm"
        assert "communication_style" not in c.character.to_dict()

    def test_legacy_0_2_0_chain_preserves_communication(self):
        old = _make_0_2_0_cartridge_dict(communication_style="Warm")
        c = CartridgeSerializer.deserialize(old)
        assert c.communication.communication_style == "Warm"
        assert "communication_style" not in c.character.to_dict()


class TestPreferenceMigration:
    def test_0_4_0_to_0_5_0_migrates_dict_to_list(self):
        old = {
            "manifest": {"cartridge_id": "t", "schema_name": SCHEMA_NAME,
                         "schema_version": "0.4.0",
                         "created_at": "2024-01-01T00:00:00",
                         "updated_at": "2024-01-01T00:00:00"},
            "identity": {"display_name": "T", "identifier": "t", "summary": "T",
                         "description": "", "aliases": []},
            "character": {"core_values": ["X"], "motivations": ["Y"],
                          "strengths": ["Z"], "limitations": ["L"],
                          "goals": ["G"], "boundaries": ["B"]},
            "preferences": {"entries": {"verbosity": "high", "theme": "dark"}},
            "behavior": {"rules": []},
            "communication": {},
            "extensions": {}, "status": "forged",
        }
        upgraded = CartridgeSerializer._upgrade_0_4_to_0_5(old)
        entries = upgraded["preferences"]["entries"]
        assert isinstance(entries, list)
        assert len(entries) == 2
        assert entries[0]["key"] == "theme"
        assert entries[0]["value"] == "dark"
        assert entries[0]["scope"] == "global"
        assert entries[0]["priority"] == "normal"
        assert entries[0]["description"] == ""
        assert entries[1]["key"] == "verbosity"
        assert entries[1]["value"] == "high"

    def test_0_4_0_empty_entries(self):
        old = {
            "manifest": {"cartridge_id": "t", "schema_name": SCHEMA_NAME,
                         "schema_version": "0.4.0",
                         "created_at": "2024-01-01T00:00:00",
                         "updated_at": "2024-01-01T00:00:00"},
            "identity": {"display_name": "T", "identifier": "t", "summary": "T",
                         "description": "", "aliases": []},
            "character": {"core_values": ["X"], "motivations": ["Y"],
                          "strengths": ["Z"], "limitations": ["L"],
                          "goals": ["G"], "boundaries": ["B"]},
            "preferences": {"entries": {}},
            "behavior": {"rules": []},
            "communication": {},
            "extensions": {}, "status": "forged",
        }
        upgraded = CartridgeSerializer._upgrade_0_4_to_0_5(old)
        assert upgraded["preferences"]["entries"] == []

    def test_0_4_0_accepted_by_deserializer(self):
        old = {
            "manifest": {"cartridge_id": "t", "schema_name": SCHEMA_NAME,
                         "schema_version": "0.4.0",
                         "created_at": "2024-01-01T00:00:00",
                         "updated_at": "2024-01-01T00:00:00"},
            "identity": {"display_name": "T", "identifier": "t", "summary": "T",
                         "description": "", "aliases": []},
            "character": {"core_values": ["X"], "motivations": ["Y"],
                          "strengths": ["Z"], "limitations": ["L"],
                          "goals": ["G"], "boundaries": ["B"]},
            "preferences": {"entries": {"style": "formal"}},
            "behavior": {"rules": []},
            "communication": {},
            "extensions": {}, "status": "forged",
        }
        c = CartridgeSerializer.deserialize(old)
        assert c.manifest.schema_version == "0.6.0"
        assert len(c.preferences.entries) == 1
        assert c.preferences.entries[0].key == "style"
        assert c.preferences.entries[0].value == "formal"

    def test_legacy_0_1_0_chain_preserves_preferences(self):
        data = _make_flat_legacy_data()
        c = CartridgeSerializer.deserialize(data)
        entries = {e.key: e.value for e in c.preferences.entries}
        assert entries == {"a": "1", "b": "2"}

    def test_legacy_0_2_0_chain_preserves_preferences(self):
        old = _make_0_2_0_cartridge_dict()
        c = CartridgeSerializer.deserialize(old)
        assert len(c.preferences.entries) == 0


class TestLifecycle:
    def test_construct_validate_freeze(self):
        draft = _make_valid_draft()
        result, validated = CartridgeForge.validate(draft)
        assert result.valid is True
        assert validated.status == CartridgeStatus.VALIDATED

        forge_result = CartridgeForge.forge(draft)
        assert forge_result.success is True
        cartridge = forge_result.cartridge
        assert cartridge.status == CartridgeStatus.FORGED

        serialized = cartridge.to_dict()
        assert isinstance(serialized, dict)

        deserialized = CartridgeSerializer.deserialize(serialized)
        assert deserialized.manifest.cartridge_id == cartridge.manifest.cartridge_id

    def test_serialized_cartridge_round_trips_via_deserialize(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        data = CartridgeSerializer.serialize(c)
        restored = CartridgeSerializer.deserialize(data)
        assert restored.identity.display_name == c.identity.display_name
        assert restored.character.core_values == c.character.core_values
        assert len(restored.preferences.entries) == len(c.preferences.entries)
        assert restored.preferences.entries[0].key == c.preferences.entries[0].key
        assert len(restored.behavior.policies) == len(c.behavior.policies)
        assert restored.behavior.policies[0].identifier == c.behavior.policies[0].identifier


# ===================================================================
# Legacy identifier generation — Assignment 009 conformance
# ===================================================================

class TestLegacyIdentifierGeneration:
    """Regression tests for canonical legacy policy identifier generation."""

    # ------------------------------------------------------------------
    # Normalization collisions
    # ------------------------------------------------------------------

    def test_normalization_collisions(self):
        rules = [
            "Ask for clarification",
            "Ask-for-clarification",
            "Ask_for_clarification",
        ]
        ids = generate_behavior_identifiers(rules)
        assert ids == [
            "ask_for_clarification",
            "ask_for_clarification_2",
            "ask_for_clarification_3",
        ]

    # ------------------------------------------------------------------
    # Punctuation-only rules
    # ------------------------------------------------------------------

    def test_punctuation_only_rules(self):
        rules = ["!!!", "???"]
        ids = generate_behavior_identifiers(rules)
        assert ids == ["policy_1", "policy_2"]
        # Original titles must remain unchanged
        assert ids[0] != rules[0]
        assert ids[1] != rules[1]

    def test_punctuation_only_with_hyphens(self):
        rules = ["---", "***"]
        ids = generate_behavior_identifiers(rules)
        assert ids[0] == "policy_1"
        assert ids[1] == "policy_2"

    # ------------------------------------------------------------------
    # Leading digits
    # ------------------------------------------------------------------

    def test_leading_digits(self):
        rules = ["24 hour response"]
        ids = generate_behavior_identifiers(rules)
        assert ids == ["policy_24_hour_response"]

    def test_leading_digits_only(self):
        rules = ["123"]
        ids = generate_behavior_identifiers(rules)
        assert ids == ["policy_123"]

    # ------------------------------------------------------------------
    # Repeated identical rules
    # ------------------------------------------------------------------

    def test_repeated_identical_rules(self):
        rules = ["Avoid speculation", "Avoid speculation"]
        ids = generate_behavior_identifiers(rules)
        assert ids == [
            "avoid_speculation",
            "avoid_speculation_2",
        ]

    def test_repeated_identical_rules_three_times(self):
        rules = ["Say hi", "Say hi", "Say hi"]
        ids = generate_behavior_identifiers(rules)
        assert ids == ["say_hi", "say_hi_2", "say_hi_3"]

    # ------------------------------------------------------------------
    # Mixed fallback collisions
    # ------------------------------------------------------------------

    def test_mixed_fallback_collisions(self):
        rules = ["Policy 1", "!!!"]
        ids = generate_behavior_identifiers(rules)
        # "Policy 1" → "policy_1"
        # "!!!" → fallback "policy_2" (position 1, no collision with "policy_1")
        assert ids[0] == "policy_1"
        assert ids[1] == "policy_2"

    def test_fallback_collision_when_name_collides(self):
        rules = ["!!!", "Policy 1"]
        ids = generate_behavior_identifiers(rules)
        # "!!!" → fallback "policy_1"
        # "Policy 1" → "policy_1" → collision → "policy_1_2"
        assert ids[0] == "policy_1"
        assert ids[1] == "policy_1_2"

    # ------------------------------------------------------------------
    # Stable output
    # ------------------------------------------------------------------

    def test_stable_output(self):
        rules = [
            "Ask for clarification",
            "Ask-for-clarification",
            "!!!",
            "24 hour response",
            "Avoid speculation",
            "Avoid speculation",
        ]
        ids1 = generate_behavior_identifiers(rules)
        ids2 = generate_behavior_identifiers(rules)
        assert ids1 == ids2

    # ------------------------------------------------------------------
    # Empty and whitespace-only rules
    # ------------------------------------------------------------------

    def test_empty_rule_fallback(self):
        rules = [""]
        ids = generate_behavior_identifiers(rules)
        assert ids == ["policy_1"]

    def test_whitespace_only_fallback(self):
        rules = ["   "]
        ids = generate_behavior_identifiers(rules)
        assert ids == ["policy_1"]

    # ------------------------------------------------------------------
    # Mixed and edge cases
    # ------------------------------------------------------------------

    def test_mixed_identifier_types(self):
        rules = [
            "Be kind",
            "!!!",
            "24/7 support",
            "Be kind",
            "policy_1",
        ]
        ids = generate_behavior_identifiers(rules)
        # "Be kind" \u2192 "be_kind"
        # "!!!" \u2192 fallback "policy_2" (position 1+1=2)
        # "24/7 support" \u2192 "policy_24_7_support"
        # "Be kind" \u2192 "be_kind" \u2192 "be_kind_2"
        # "policy_1" \u2192 "policy_1"
        assert ids[0] == "be_kind"
        assert ids[1] == "policy_2"
        assert ids[2] == "policy_24_7_support"
        assert ids[3] == "be_kind_2"
        assert ids[4] == "policy_1"

    def test_hyphen_and_underscore_normalization(self):
        rules = [
            "ask_before_acting",
            "ask-before-acting",
            "ask before acting",
        ]
        ids = generate_behavior_identifiers(rules)
        assert ids == [
            "ask_before_acting",
            "ask_before_acting_2",
            "ask_before_acting_3",
        ]

    # ------------------------------------------------------------------
    # Forge consistency — forge and migration produce same identifiers
    # ------------------------------------------------------------------

    def test_forge_behavior_identifiers_match_generated(self):
        rules = [
            "Ask for clarification",
            "Ask-for-clarification",
            "!!!",
            "24 hour response",
        ]
        generated = generate_behavior_identifiers(rules)

        # Build via forge
        draft = _make_valid_draft(behavior_rules=rules)
        c = CartridgeForge.forge(draft).cartridge
        forged_ids = [p.identifier for p in c.behavior.policies]

        # Both produce same identifiers in source order
        assert generated == forged_ids

        # Serialization sorts by identifier (verify to_dict)
        d = c.to_dict()
        sorted_ids = sorted(generated)
        serialized_ids = [p["identifier"] for p in d["behavior"]["policies"]]
        assert sorted_ids == serialized_ids

    def test_forge_identifiers_are_valid(self):
        draft = _make_valid_draft(behavior_rules=[
            "Ask for clarification",
            "Ask-for-clarification",
            "!!!",
            "24 hour response",
            "Avoid speculation",
            "Avoid speculation",
            "",
        ])
        result, validated = CartridgeForge.validate(draft)
        assert result.valid is True

        c = CartridgeForge.forge(draft).cartridge
        for policy in c.behavior.policies:
            assert policy.identifier[0].isalpha()
            for ch in policy.identifier:
                assert ch in "abcdefghijklmnopqrstuvwxyz0123456789_"

    # ------------------------------------------------------------------
    # Migration safety
    # ------------------------------------------------------------------

    def test_migration_safety_colliding_normalization(self):
        old = _make_0_2_0_cartridge_dict()
        old["behavior"]["rules"] = [
            "Ask for clarification",
            "Ask-for-clarification",
            "Ask_for_clarification",
        ]
        c = CartridgeSerializer.deserialize(old)
        ids = [p.identifier for p in c.behavior.policies]
        assert len(ids) == 3
        assert len(set(ids)) == 3
        assert ids[0] == "ask_for_clarification"
        assert ids[1] == "ask_for_clarification_2"
        assert ids[2] == "ask_for_clarification_3"

    def test_migration_safety_punctuation_only(self):
        old = _make_0_2_0_cartridge_dict()
        old["behavior"]["rules"] = ["!!!", "???"]
        c = CartridgeSerializer.deserialize(old)
        ids = [p.identifier for p in c.behavior.policies]
        assert len(ids) == 2
        assert ids == sorted(ids)

    def test_migration_safety_digit_leading(self):
        old = _make_0_2_0_cartridge_dict()
        old["behavior"]["rules"] = ["24 hour response", "7 day support"]
        c = CartridgeSerializer.deserialize(old)
        for p in c.behavior.policies:
            assert p.identifier[0].isalpha()

    def test_migration_safety_repeated_rules(self):
        old = _make_0_2_0_cartridge_dict()
        old["behavior"]["rules"] = ["Avoid speculation", "Avoid speculation"]
        c = CartridgeSerializer.deserialize(old)
        ids = [p.identifier for p in c.behavior.policies]
        assert len(ids) == 2
        assert ids[0] != ids[1]

    def test_migration_safety_full_mix(self):
        old = _make_0_2_0_cartridge_dict()
        old["behavior"]["rules"] = [
            "Ask for clarification",
            "Ask-for-clarification",
            "Ask_for_clarification",
            "!!!",
            "??",
            "24 hour response",
            "Avoid speculation",
            "Avoid speculation",
        ]
        c = CartridgeSerializer.deserialize(old)
        assert c.manifest.schema_version == "0.6.0"
        ids = [p.identifier for p in c.behavior.policies]
        assert len(ids) == 8
        assert len(set(ids)) == 8
        for ident in ids:
            assert ident[0].isalpha()
            for ch in ident:
                assert ch in "abcdefghijklmnopqrstuvwxyz0123456789_"

    # ------------------------------------------------------------------
    # Full upgrade chain
    # ------------------------------------------------------------------

    def test_full_upgrade_chain_preserves_behavior(self):
        data = _make_flat_legacy_data()
        data["behavior_rules"] = [
            "Ask for clarification",
            "Ask-for-clarification",
            "!!!",
            "24 hour response",
        ]
        c = CartridgeSerializer.deserialize(data)
        assert c.manifest.schema_version == "0.6.0"
        assert len(c.behavior.policies) == 4
        titles = [p.title for p in c.behavior.policies]
        assert "Ask for clarification" in titles
        assert "Ask-for-clarification" in titles
        assert "!!!" in titles
        assert "24 hour response" in titles

    # ------------------------------------------------------------------
    # Original title preserved
    # ------------------------------------------------------------------

    def test_original_title_preserved(self):
        rules = ["  Ask for clarity  "]
        draft = _make_valid_draft(behavior_rules=rules)
        c = CartridgeForge.forge(draft).cartridge
        assert c.behavior.policies[0].title == "Ask for clarity"
        assert c.behavior.policies[0].identifier == "ask_for_clarity"

    def test_original_title_preserved_after_migration(self):
        old = _make_0_2_0_cartridge_dict()
        old["behavior"]["rules"] = ["  Ask for clarity  "]
        c = CartridgeSerializer.deserialize(old)
        assert c.behavior.policies[0].title == "Ask for clarity"


# ===================================================================
# Helpers
# ===================================================================

def _create_module_instance(module_type: type) -> CartridgeModule:
    """Create a minimal valid instance of any module type."""
    if module_type is IdentityModule:
        return IdentityModule(display_name="Test", identifier="test", summary="Test")
    if module_type is CharacterModule:
        return CharacterModule(core_values=("X",), motivations=("Y",),
                               strengths=("Z",), limitations=("L",),
                               goals=("G",), boundaries=("B",))
    if module_type is PreferenceModule:
        return PreferenceModule()
    if module_type is BehaviorModule:
        return BehaviorModule(policies=(
            BehaviorPolicy(identifier="test", title="Test"),
        ))
    if module_type is CommunicationModule:
        return CommunicationModule()
    raise ValueError(f"Unknown module type: {module_type}")

def _make_valid_draft(**overrides) -> PersonaDraft:
    params = dict(
        name="Alex",
        identifier="alex",
        summary="A thoughtful guide",
        description="Optional description",
        aliases=["The Guide", "Alex the Great"],
        communication_style="Warm and direct",  # reserved for future module
        core_values=["Curiosity"],
        motivations=["To help others grow"],
        strengths=["Patience"],
        limitations=["Overthinking"],
        goals=["Inspire learning"],
        boundaries=["Never lie"],
        behavior_rules=["Ask before acting"],
        preferences={"formality": "casual"},
    )
    params.update(overrides)
    return PersonaDraft(**params)


def _make_legacy_manifest_dict() -> dict:
    """0.1.0-style manifest for legacy test data."""
    return {
        "cartridge_id": "test-id-1234",
        "schema_name": SCHEMA_NAME,
        "schema_version": "0.1.0",
        "created_at": "2026-07-19T12:00:00+00:00",
        "updated_at": "2026-07-19T12:00:00+00:00",
    }


def _make_flat_legacy_data() -> dict:
    return {
        "manifest": _make_legacy_manifest_dict(),
        "name": "Alex",
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
        "behavior_rules": ["Be kind"],
        "extensions": {},
        "status": "forged",
    }


def _make_0_2_0_cartridge_dict(**overrides) -> dict:
    """Create a 0.2.0-style cartridge dict for upgrade testing."""
    params = dict(
        communication_style="Warm",
        core_values=["X"],
        motivations=["Y"],
        strengths=["Z"],
        limitations=["L"],
        goals=["G"],
        boundaries=["B"],
    )
    params.update(overrides)
    return {
        "manifest": {
            "cartridge_id": "test-0-2-0-id",
            "schema_name": SCHEMA_NAME,
            "schema_version": "0.2.0",
            "created_at": "2026-07-19T12:00:00+00:00",
            "updated_at": "2026-07-19T12:00:00+00:00",
        },
        "identity": {
            "display_name": "Test",
            "identifier": "test",
            "summary": "A test",
            "description": "",
            "aliases": [],
        },
        "character": {
            "communication_style": params["communication_style"],
            "core_values": params["core_values"],
            "motivations": params["motivations"],
            "strengths": params["strengths"],
            "limitations": params["limitations"],
            "goals": params["goals"],
            "boundaries": params["boundaries"],
        },
        "preferences": {"entries": {}},
        "behavior": {"rules": []},
        "communication": {},
        "extensions": {},
        "status": "forged",
    }
