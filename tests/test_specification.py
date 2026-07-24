"""Test suite for Assignment 016 — Persona Cartridge Specification v1.0.0."""

import copy
import pytest
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
    PersonaDraft,
    PreferenceEntry,
    PreferenceModule,
)
from app.models.projection import RuntimeProjectionBuilder
from app.services.archengine_export import export_archengine_payload
from app.services.forge import CartridgeForge
from app.specification import (
    PROHIBITED_RUNTIME_KEYS,
    REQUIRED_MODULES,
    SPECIFICATION_NAME,
    SPECIFICATION_SCHEMA_URI,
    SPECIFICATION_VERSION,
    SpecificationError,
    SpecificationValidationError,
    SpecificationValidationResult,
    SpecificationValidator,
    SpecificationVersionError,
    SpecificationViolation,
    get_canonical_json_schema,
    get_specification_compatibility_report,
    is_specification_deprecated,
    is_specification_supported,
    validate_json_schema,
)
from tests.fixtures.archengine.fixtures import (
    aliases_and_metadata_cartridge,
    complete_cartridge,
    disabled_policies_cartridge,
    legacy_upgraded_cartridge,
    minimal_cartridge,
)


def _make_valid_draft() -> PersonaDraft:
    return PersonaDraft(
        name="Athena",
        identifier="athena",
        summary="Strategic intelligence persona",
        description="A clear and logical advisor",
        aliases=["Minerva", "Goddess of Wisdom"],
        communication_style="Direct and precise",
        tone=["objective", "thoughtful"],
        core_values=["Truth", "Wisdom"],
        motivations=["Understanding"],
        strengths=["Analysis", "Strategy"],
        limitations=["Overly analytical"],
        goals=["Provide clarity"],
        boundaries=["Never deceive"],
        behavior_rules=["Verify facts before answering", "Provide structured output"],
        preferences={"verbosity": "high", "formality": "high"},
    )


class TestSpecificationVersionConstants:
    """Verify specification version constants."""

    def test_version_constants(self):
        assert SPECIFICATION_NAME == "Persona Cartridge Specification"
        assert SPECIFICATION_VERSION == "1.0.0"
        assert SPECIFICATION_SCHEMA_URI.endswith("persona-cartridge-1.0.0.json")


class TestSpecificationValidationSuccess:
    """Verify valid forged cartridges pass specification validation."""

    def test_valid_forged_cartridge_conforms(self):
        draft = _make_valid_draft()
        result = CartridgeForge.forge(draft)
        assert result.success is True
        cartridge = result.cartridge
        assert cartridge is not None

        val_res = SpecificationValidator.validate(cartridge)
        assert val_res.compliant is True
        assert val_res.specification_version == "1.0.0"
        assert len(val_res.violations) == 0

    def test_validate_or_raise_passes(self):
        draft = _make_valid_draft()
        cartridge = CartridgeForge.forge(draft).cartridge
        # Should not raise exception
        SpecificationValidator.validate_or_raise(cartridge)


class TestSpecificationMissingModules:
    """Verify rejection when required modules or fields are missing."""

    def test_missing_required_module(self):
        draft = _make_valid_draft()
        cartridge = CartridgeForge.forge(draft).cartridge
        data = cartridge.to_dict()
        del data["character"]

        val_res = SpecificationValidator.validate(data)
        assert val_res.compliant is False
        assert any(v.rule == "SPEC-002:REQUIRED_MODULES" for v in val_res.violations)

    def test_missing_manifest(self):
        draft = _make_valid_draft()
        cartridge = CartridgeForge.forge(draft).cartridge
        data = cartridge.to_dict()
        del data["manifest"]

        val_res = SpecificationValidator.validate(data)
        assert val_res.compliant is False
        assert any(v.rule == "SPEC-001:REQUIRED_MANIFEST" for v in val_res.violations)


class TestSpecificationProhibitedRuntimeData:
    """Verify strict rejection of prohibited runtime data fields."""

    @pytest.mark.parametrize("prohibited_key", sorted(list(PROHIBITED_RUNTIME_KEYS)))
    def test_prohibited_key_rejection_at_top_level(self, prohibited_key):
        draft = _make_valid_draft()
        data = CartridgeForge.forge(draft).cartridge.to_dict()
        data[prohibited_key] = {"some": "state"}

        val_res = SpecificationValidator.validate(data)
        assert val_res.compliant is False
        assert any(
            v.rule == "SPEC-003:PROHIBITED_RUNTIME_DATA" and prohibited_key in v.location
            for v in val_res.violations
        )

    def test_prohibited_key_rejection_inside_extensions(self):
        draft = _make_valid_draft()
        data = CartridgeForge.forge(draft).cartridge.to_dict()
        data["extensions"] = {"sub_key": {"communication_state": "ST3"}}

        val_res = SpecificationValidator.validate(data)
        assert val_res.compliant is False
        assert any(v.rule == "SPEC-003:PROHIBITED_RUNTIME_DATA" for v in val_res.violations)


class TestSpecificationDeterminism:
    """Verify deterministic ordering and serialization rules."""

    def test_deterministic_preference_ordering(self):
        draft = _make_valid_draft()
        cartridge = CartridgeForge.forge(draft).cartridge
        data = cartridge.to_dict()

        # Artificially unsort preferences
        data["preferences"]["entries"] = [
            {"key": "z_pref", "value": "1", "scope": "global", "priority": "normal", "description": ""},
            {"key": "a_pref", "value": "2", "scope": "global", "priority": "normal", "description": ""},
        ]

        val_res = SpecificationValidator.validate(data)
        assert val_res.compliant is False
        assert any(v.rule == "SPEC-004:DETERMINISTIC_ORDERING" for v in val_res.violations)

    def test_two_equivalent_cartridges_produce_identical_dict(self):
        draft1 = _make_valid_draft()
        draft2 = _make_valid_draft()

        c1 = CartridgeForge.forge(draft1).cartridge
        c2 = CartridgeForge.forge(draft2).cartridge

        d1 = c1.to_dict()
        d2 = c2.to_dict()

        # Ignore non-deterministic metadata like cartridge_id and timestamps
        d1["manifest"]["cartridge_id"] = "fixed-id"
        d2["manifest"]["cartridge_id"] = "fixed-id"
        d1["manifest"]["created_at"] = "fixed-time"
        d2["manifest"]["created_at"] = "fixed-time"
        d1["manifest"]["updated_at"] = "fixed-time"
        d2["manifest"]["updated_at"] = "fixed-time"

        assert d1 == d2


class TestSpecificationImmutabilityAndIdentifiers:
    """Verify invariant checks on cartridge manifest and identifier formats."""

    def test_empty_cartridge_id(self):
        draft = _make_valid_draft()
        data = CartridgeForge.forge(draft).cartridge.to_dict()
        data["manifest"]["cartridge_id"] = ""

        val_res = SpecificationValidator.validate(data)
        assert val_res.compliant is False
        assert any(v.rule == "SPEC-005:IMMUTABLE_IDENTIFIERS" for v in val_res.violations)

    def test_invalid_persona_identifier_syntax(self):
        draft = _make_valid_draft()
        data = CartridgeForge.forge(draft).cartridge.to_dict()
        data["identity"]["identifier"] = "123_invalid_start"

        val_res = SpecificationValidator.validate(data)
        assert val_res.compliant is False
        assert any(v.rule == "SPEC-005:IMMUTABLE_IDENTIFIERS" for v in val_res.violations)


class TestSpecificationVersionMismatch:
    """Verify specification version mismatch reporting."""

    def test_mismatched_specification_version(self):
        draft = _make_valid_draft()
        data = CartridgeForge.forge(draft).cartridge.to_dict()
        data["manifest"]["specification_version"] = "9.9.9"

        val_res = SpecificationValidator.validate(data)
        assert val_res.compliant is False
        assert any(v.rule == "SPEC-006:SPECIFICATION_VERSION" for v in val_res.violations)


class TestSpecificationCompatibility:
    """Verify compatibility module functions."""

    def test_supported_versions(self):
        assert is_specification_supported("1.0.0") is True
        assert is_specification_supported("2.0.0") is False

    def test_deprecated_versions(self):
        assert is_specification_deprecated("1.0.0") is False

    def test_compatibility_report(self):
        report = get_specification_compatibility_report("1.0.0")
        assert report["specification_version"] == "1.0.0"
        assert report["supported"] is True
        assert report["deprecated"] is False
        assert "negotiation_strategy" in report


class TestSpecificationJSONSchema:
    """Verify canonical JSON schema interface."""

    def test_load_canonical_json_schema(self):
        schema = get_canonical_json_schema()
        assert schema["title"] == "Persona Cartridge Specification v1.0.0"
        assert "$schema" in schema

    def test_validate_json_schema_directly(self):
        draft = _make_valid_draft()
        cartridge = CartridgeForge.forge(draft).cartridge
        violations = validate_json_schema(cartridge.to_dict())
        assert len(violations) == 0


class TestSpecificationFixtureConformance:
    """Verify that all canonical integration test fixtures conform to Specification v1.0.0."""

    @pytest.mark.parametrize(
        "fixture_fn",
        [
            minimal_cartridge,
            complete_cartridge,
            legacy_upgraded_cartridge,
            disabled_policies_cartridge,
            aliases_and_metadata_cartridge,
        ],
    )
    def test_fixture_conforms_to_specification(self, fixture_fn):
        cartridge = fixture_fn()
        val_res = SpecificationValidator.validate(cartridge)
        assert val_res.compliant is True, f"Fixture {fixture_fn.__name__} failed specification validation: {val_res.violations}"


class TestSpecificationExportAndProjectionConformance:
    """Verify runtime projection and export payload conformance."""

    def test_runtime_projection_preserves_authored_specification_data(self):
        draft = _make_valid_draft()
        cartridge = CartridgeForge.forge(draft).cartridge
        projection = RuntimeProjectionBuilder.build(cartridge)

        # Projection contains same identity, character, and preferences
        assert projection.identifier == cartridge.identity.identifier
        assert projection.display_name == cartridge.identity.display_name

    def test_exported_payload_preserves_specification_provenance(self):
        draft = _make_valid_draft()
        cartridge = CartridgeForge.forge(draft).cartridge
        payload = export_archengine_payload(cartridge)

        data = payload.to_dict()
        assert data["id"] == cartridge.manifest.cartridge_id
        assert data["metadata"]["chimera"]["schema_version"] == cartridge.manifest.schema_version


class TestSpecificationValidationErrorHandling:
    """Verify structured error reporting on validation failure."""

    def test_validate_or_raise_raises_structured_exception(self):
        draft = _make_valid_draft()
        data = CartridgeForge.forge(draft).cartridge.to_dict()
        data["manifest"]["cartridge_id"] = ""

        with pytest.raises(SpecificationValidationError) as exc_info:
            SpecificationValidator.validate_or_raise(data)

        err_dict = exc_info.value.to_dict()
        assert err_dict["error"] == "SpecificationValidationError"
        assert len(err_dict["violations"]) > 0
        v0 = err_dict["violations"][0]
        assert "rule" in v0
        assert "location" in v0
        assert "reason" in v0
        assert "recommendation" in v0
