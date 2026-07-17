import pytest
from datetime import datetime, timezone

from app.models.cartridge import (
    CartridgeStatus,
    CartridgeValidationError,
    CartridgeValidationWarning,
    CartridgeValidationResult,
    ForgeErrorCode,
    ForgeError,
    ForgeResult,
    PersonaCartridge,
    PersonaDraft,
    ValidationCode,
)
from app.services.forge import CartridgeForge


# ---------------------------------------------------------------------------
# Schema identity
# ---------------------------------------------------------------------------

class TestSchemaIdentity:
    def test_schema_name_is_correct(self):
        assert PersonaCartridge.schema()["name"] == "archepersona.chimera.persona-cartridge"

    def test_schema_version_is_correct(self):
        assert PersonaCartridge.schema()["version"] == "0.1.0"

    def test_schema_description_present(self):
        assert "description" in PersonaCartridge.schema()

    def test_draft_uses_correct_schema_identity(self):
        draft = PersonaDraft()
        assert draft.schema_name == "archepersona.chimera.persona-cartridge"
        assert draft.schema_version == "0.1.0"

    def test_cartridge_uses_correct_schema_identity(self):
        draft = _make_valid_draft()
        result = CartridgeForge.forge(draft)
        c = result.cartridge
        assert c.schema_name == "archepersona.chimera.persona-cartridge"
        assert c.schema_version == "0.1.0"


# ---------------------------------------------------------------------------
# CartridgeStatus
# ---------------------------------------------------------------------------

class TestCartridgeStatus:
    def test_status_values(self):
        assert CartridgeStatus.DRAFT.value == "draft"
        assert CartridgeStatus.VALIDATED.value == "validated"
        assert CartridgeStatus.FORGED.value == "forged"

    def test_status_order(self):
        assert list(CartridgeStatus) == [CartridgeStatus.DRAFT, CartridgeStatus.VALIDATED, CartridgeStatus.FORGED]

    def test_draft_starts_as_draft(self):
        assert PersonaDraft().status == CartridgeStatus.DRAFT

    def test_forged_cartridge_has_forged_status(self):
        draft = _make_valid_draft()
        result = CartridgeForge.forge(draft)
        assert result.cartridge.status == CartridgeStatus.FORGED


# ---------------------------------------------------------------------------
# CartridgeValidationResult / Error / Warning
# ---------------------------------------------------------------------------

class TestCartridgeValidationResult:
    def test_valid_result_is_truthy(self):
        assert bool(CartridgeValidationResult(valid=True)) is True

    def test_invalid_result_is_falsy(self):
        result = CartridgeValidationResult(valid=False, errors=[
            CartridgeValidationError(code=ValidationCode.REQUIRED_FIELD_EMPTY, field="name", message="x"),
        ])
        assert bool(result) is False

    def test_invalid_with_no_errors_still_falsy(self):
        assert bool(CartridgeValidationResult(valid=False)) is False

    def test_result_carries_warnings(self):
        result = CartridgeValidationResult(valid=True, warnings=[
            CartridgeValidationWarning(code=ValidationCode.NO_BEHAVIOR_RULES, field="behavior_rules", message="no rules"),
        ])
        assert len(result.warnings) == 1
        assert result.warnings[0].code == ValidationCode.NO_BEHAVIOR_RULES

    def test_validation_error_has_code_field_message(self):
        err = CartridgeValidationError(code=ValidationCode.REQUIRED_FIELD_EMPTY, field="name", message="Name is required")
        assert err.code == ValidationCode.REQUIRED_FIELD_EMPTY
        assert err.field == "name"
        assert err.message == "Name is required"

    def test_validation_warning_has_code_field_message(self):
        warn = CartridgeValidationWarning(code=ValidationCode.NO_BEHAVIOR_RULES, field="behavior_rules", message="add rules")
        assert warn.code == ValidationCode.NO_BEHAVIOR_RULES
        assert warn.field == "behavior_rules"


# ---------------------------------------------------------------------------
# ForgeResult / ForgeError
# ---------------------------------------------------------------------------

class TestForgeResult:
    def test_successful_forge_result_is_truthy(self):
        draft = _make_valid_draft()
        result = CartridgeForge.forge(draft)
        assert bool(result) is True
        assert result.success is True

    def test_failed_forge_result_is_falsy(self):
        result = CartridgeForge.forge(PersonaDraft())
        assert bool(result) is False
        assert result.success is False

    def test_failed_forge_has_error_code(self):
        result = CartridgeForge.forge(PersonaDraft())
        assert result.error is not None
        assert result.error.code == ForgeErrorCode.VALIDATION_FAILED

    def test_failed_forge_has_message(self):
        result = CartridgeForge.forge(PersonaDraft())
        assert result.error is not None
        assert len(result.error.message) > 0

    def test_failed_forge_has_detail(self):
        result = CartridgeForge.forge(PersonaDraft())
        assert result.error is not None
        assert len(result.error.detail) > 0

    def test_successful_forge_has_no_error(self):
        draft = _make_valid_draft()
        result = CartridgeForge.forge(draft)
        assert result.error is None

    def test_successful_forge_returns_cartridge(self):
        draft = _make_valid_draft()
        result = CartridgeForge.forge(draft)
        assert result.cartridge is not None
        assert isinstance(result.cartridge, PersonaCartridge)


# ---------------------------------------------------------------------------
# PersonaDraft
# ---------------------------------------------------------------------------

class TestPersonaDraft:
    def test_default_draft_has_draft_status(self):
        draft = PersonaDraft()
        assert draft.status == CartridgeStatus.DRAFT

    def test_default_draft_is_empty(self):
        draft = PersonaDraft()
        assert draft.name == ""
        assert draft.core_values == []
        assert draft.preferences == {}
        assert draft.behavior_rules == []

    def test_draft_has_unique_cartridge_id(self):
        assert PersonaDraft().cartridge_id != PersonaDraft().cartridge_id


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

class TestNormalization:
    def test_normalize_strips_whitespace_from_text_fields(self):
        draft = PersonaDraft(name="  Alex  ", summary="  Guide  ", communication_style="  Warm  ")
        PersonaDraft.normalize(draft)
        assert draft.name == "Alex"
        assert draft.summary == "Guide"
        assert draft.communication_style == "Warm"

    def test_normalize_prunes_empty_list_entries(self):
        draft = PersonaDraft(core_values=["Honesty", "", "  ", "Courage"])
        PersonaDraft.normalize(draft)
        assert draft.core_values == ["Honesty", "Courage"]

    def test_normalize_strips_list_entries(self):
        draft = PersonaDraft(core_values=["  Honesty  ", "Courage  "])
        PersonaDraft.normalize(draft)
        assert draft.core_values == ["Honesty", "Courage"]

    def test_normalize_prunes_empty_preference_keys(self):
        draft = PersonaDraft(preferences={"": "val", "  ": "val2", "tone": "warm"})
        PersonaDraft.normalize(draft)
        assert "tone" in draft.preferences
        assert "" not in draft.preferences

    def test_normalize_strips_preference_keys_and_values(self):
        draft = PersonaDraft(preferences={"  tone  ": "  warm  "})
        PersonaDraft.normalize(draft)
        assert draft.preferences == {"tone": "warm"}

    def test_normalize_coercion_does_not_raise(self):
        draft = PersonaDraft()
        PersonaDraft.normalize(draft)  # should not raise


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_draft_passes(self):
        draft = _make_valid_draft()
        result = CartridgeForge.validate(draft)
        assert result.valid is True
        assert result.errors == []

    def test_empty_draft_fails_all_required_fields(self):
        result = CartridgeForge.validate(PersonaDraft())
        assert result.valid is False
        # 3 text fields + 6 list fields = 9 errors
        assert len(result.errors) == 9

    def test_partial_draft_returns_only_relevant_errors(self):
        draft = PersonaDraft(name="Test", core_values=["X"], motivations=["Y"])
        result = CartridgeForge.validate(draft)
        fields = {e.field for e in result.errors}
        assert "name" not in fields
        assert "core_values" not in fields
        assert "motivations" not in fields
        assert "summary" in fields
        assert "communication_style" in fields
        assert "strengths" in fields
        assert "limitations" in fields
        assert "goals" in fields
        assert "boundaries" in fields

    def test_blank_text_after_normalization_fails(self):
        draft = PersonaDraft(name="  ", summary="  ", communication_style="  ")
        result = CartridgeForge.validate(draft)
        fields = {e.field for e in result.errors}
        assert "name" in fields
        assert "summary" in fields

    def test_validation_error_has_stable_code(self):
        result = CartridgeForge.validate(PersonaDraft())
        for err in result.errors:
            assert isinstance(err.code, ValidationCode)
            assert err.code in (ValidationCode.REQUIRED_FIELD_EMPTY, ValidationCode.REQUIRED_LIST_EMPTY)

    def test_behavior_rules_optional_no_error(self):
        draft = _make_valid_draft()
        draft.behavior_rules = []
        result = CartridgeForge.validate(draft)
        assert result.valid is True

    def test_no_behavior_rules_emits_warning(self):
        draft = _make_valid_draft()
        draft.behavior_rules = []
        result = CartridgeForge.validate(draft)
        assert len(result.warnings) == 1
        assert result.warnings[0].code == ValidationCode.NO_BEHAVIOR_RULES

    def test_behavior_rules_present_no_warning(self):
        draft = _make_valid_draft(behavior_rules=["Be kind"])
        result = CartridgeForge.validate(draft)
        warnings = [w for w in result.warnings if w.code == ValidationCode.NO_BEHAVIOR_RULES]
        assert len(warnings) == 0

    def test_normalization_runs_before_validation(self):
        draft = PersonaDraft(
            name="  Alex  ",
            summary="  Guide  ",
            communication_style="  Warm  ",
            core_values=["", "Honesty  "],
            motivations=["  Help  "],
            strengths=["  Patience  "],
            limitations=["  None  "],
            goals=["  Teach  "],
            boundaries=["  Safety  "],
        )
        result = CartridgeForge.validate(draft)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Forge
# ---------------------------------------------------------------------------

class TestForge:
    def test_forge_returns_forged_cartridge(self):
        result = CartridgeForge.forge(_make_valid_draft())
        assert result.success is True
        assert result.cartridge.status == CartridgeStatus.FORGED

    def test_forge_preserves_all_fields(self):
        draft = _make_valid_draft(
            name="Alex", summary="Guide", communication_style="Warm",
            core_values=["Honesty"], motivations=["Help"],
            strengths=["Patience"], limitations=["Impatience"],
            goals=["Teach"], boundaries=["Safety"],
            behavior_rules=["Listen"], preferences={"tone": "warm"},
        )
        c = CartridgeForge.forge(draft).cartridge
        assert c.name == "Alex"
        assert c.summary == "Guide"
        assert c.communication_style == "Warm"
        assert c.core_values == ("Honesty",)
        assert c.motivations == ("Help",)
        assert c.strengths == ("Patience",)
        assert c.limitations == ("Impatience",)
        assert c.goals == ("Teach",)
        assert c.boundaries == ("Safety",)
        assert c.behavior_rules == ("Listen",)
        assert dict(c.preferences) == {"tone": "warm"}

    def test_forge_preserves_metadata(self):
        draft = _make_valid_draft()
        c = CartridgeForge.forge(draft).cartridge
        assert c.cartridge_id == draft.cartridge_id
        assert c.schema_name == draft.schema_name
        assert c.schema_version == draft.schema_version
        assert c.created_at == draft.created_at

    def test_forge_updates_timestamp(self):
        draft = _make_valid_draft()
        original = draft.updated_at
        result = CartridgeForge.forge(draft)
        assert result.cartridge.updated_at >= original

    def test_forge_normalizes_whitespace(self):
        draft = _make_valid_draft(name="  Alex  ", summary="  Guide  ")
        c = CartridgeForge.forge(draft).cartridge
        assert c.name == "Alex"
        assert c.summary == "Guide"

    def test_forge_fails_on_empty_draft(self):
        result = CartridgeForge.forge(PersonaDraft())
        assert result.success is False
        assert result.cartridge is None

    def test_forge_failure_is_structured_not_exception(self):
        result = CartridgeForge.forge(PersonaDraft())
        assert isinstance(result, ForgeResult)
        assert result.error is not None
        assert result.error.code == ForgeErrorCode.VALIDATION_FAILED

    def test_forge_accepts_missing_behavior_rules(self):
        draft = _make_valid_draft(behavior_rules=[])
        result = CartridgeForge.forge(draft)
        assert result.success is True
        assert result.cartridge.behavior_rules == ()

    def test_forged_cartridge_is_frozen(self):
        c = CartridgeForge.forge(_make_valid_draft()).cartridge
        with pytest.raises((AttributeError, TypeError, Exception)):
            c.name = "Changed"

    def test_forge_normalizes_before_freeze(self):
        draft = _make_valid_draft(core_values=["", "Honesty  "])
        c = CartridgeForge.forge(draft).cartridge
        assert c.core_values == ("Honesty",)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_contains_all_fields(self):
        draft = _make_valid_draft(name="Alex")
        d = CartridgeForge.forge(draft).cartridge.to_dict()
        assert d["name"] == "Alex"
        assert d["status"] == "forged"
        assert d["schema_name"] == "archepersona.chimera.persona-cartridge"
        assert d["schema_version"] == "0.1.0"

    def test_to_dict_serializes_timestamps_as_strings(self):
        d = CartridgeForge.forge(_make_valid_draft()).cartridge.to_dict()
        assert isinstance(d["created_at"], str)
        assert isinstance(d["updated_at"], str)

    def test_to_dict_flattens_preferences(self):
        draft = _make_valid_draft(preferences={"a": "1", "b": "2"})
        d = CartridgeForge.forge(draft).cartridge.to_dict()
        assert d["preferences"] == {"a": "1", "b": "2"}

    def test_to_dict_converts_lists_to_tuples_internal(self):
        c = CartridgeForge.forge(_make_valid_draft(core_values=["A", "B"])).cartridge
        assert isinstance(c.core_values, tuple)

    def test_to_dict_round_trip(self):
        draft = _make_valid_draft()
        c = CartridgeForge.forge(draft).cartridge
        d = c.to_dict()
        assert d["cartridge_id"] == draft.cartridge_id
        assert d["name"] == draft.name


# ---------------------------------------------------------------------------
# ValidationCode enum
# ---------------------------------------------------------------------------

class TestValidationCode:
    def test_all_codes_defined(self):
        codes = {e.value for e in ValidationCode}
        assert "REQUIRED_FIELD_EMPTY" in codes
        assert "REQUIRED_LIST_EMPTY" in codes
        assert "INVALID_TYPE" in codes
        assert "NO_BEHAVIOR_RULES" in codes


# ---------------------------------------------------------------------------
# ForgeErrorCode enum
# ---------------------------------------------------------------------------

class TestForgeErrorCode:
    def test_all_codes_defined(self):
        codes = {e.value for e in ForgeErrorCode}
        assert "VALIDATION_FAILED" in codes
        assert "INVALID_STATE" in codes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_draft(**overrides) -> PersonaDraft:
    params = dict(
        name="Alex",
        summary="A thoughtful guide",
        communication_style="Warm and direct",
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
