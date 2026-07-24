import json
from datetime import datetime, timezone

from app.integrations.archengine import (
    CartridgeDescriptorPayload,
    TranslationError,
)
from app.models.cartridge import PersonaCartridge, PersonaDraft
from app.services.archengine_export import (
    export_archengine_payload,
    export_archengine_payload_json,
)
from app.services.forge import CartridgeForge
from tests.fixtures.archengine.fixtures import (
    aliases_and_metadata_cartridge,
    complete_cartridge,
    disabled_policies_cartridge,
    generate_all_payloads,
    legacy_upgraded_cartridge,
    minimal_cartridge,
)


# ===================================================================
# Successful export
# ===================================================================

class TestExportBasic:
    def test_export_returns_payload(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        assert isinstance(payload, CartridgeDescriptorPayload)

    def test_export_json_returns_dict(self):
        c = complete_cartridge()
        d = export_archengine_payload_json(c)
        assert isinstance(d, dict)

    def test_json_round_trip(self):
        c = complete_cartridge()
        d = export_archengine_payload_json(c)
        text = json.dumps(d, ensure_ascii=False)
        restored = json.loads(text)
        assert restored["name"] == "Alex"
        assert restored["id"] is not None


# ===================================================================
# Determinism
# ===================================================================

class TestExportDeterminism:
    def test_repeated_export_identical_modulo_timestamp(self):
        c = complete_cartridge()
        p1 = export_archengine_payload(c)
        p2 = export_archengine_payload(c)
        # Remove timestamp-dependent fields before comparing metadata
        m1 = dict(p1.metadata)
        m2 = dict(p2.metadata)
        for m in (m1, m2):
            m["chimera"] = {k: v for k, v in m["chimera"].items() if k != "exported_at"}
        assert m1 == m2
        assert p1.id == p2.id
        assert p1.name == p2.name
        assert p1.values == p2.values
        assert p1.disposition == p2.disposition

    def test_json_deterministic_modulo_timestamp(self):
        c = complete_cartridge()
        j1 = export_archengine_payload_json(c)
        j2 = export_archengine_payload_json(c)
        for j in (j1, j2):
            j["metadata"]["chimera"] = {
                k: v for k, v in j["metadata"]["chimera"].items() if k != "exported_at"
            }
        assert j1 == j2


# ===================================================================
# Immutability — cartridge and projection unchanged
# ===================================================================

class TestExportImmutability:
    def test_cartridge_unchanged(self):
        c = complete_cartridge()
        original_id = c.manifest.cartridge_id
        export_archengine_payload(c)
        assert c.manifest.cartridge_id == original_id

    def test_payload_isolation(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        d = payload.to_dict()
        d["name"] = "MUTATED"
        assert payload.name != "MUTATED"

    def test_payload_not_cartridge(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        assert not isinstance(payload, PersonaCartridge)


# ===================================================================
# Metadata
# ===================================================================

class TestExportMetadata:
    def test_schema_version_in_metadata(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        assert payload.metadata["chimera"]["schema_version"] == c.manifest.schema_version

    def test_compatibility_version_in_metadata(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        assert payload.metadata["chimera"]["compatibility_version"] == "1.0"

    def test_export_timestamp_in_metadata(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        ts = payload.metadata["chimera"]["exported_at"]
        assert isinstance(ts, str)
        # Verify ISO-8601 parseable
        datetime.fromisoformat(ts)

    def test_exporter_in_metadata(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        assert payload.metadata["chimera"]["exporter"] == "CHIMERA"

    def test_target_in_metadata(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        assert payload.metadata["chimera"]["target"] == "ARCHEngine"


# ===================================================================
# Version
# ===================================================================

class TestExportVersion:
    def test_version_from_cartridge(self):
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        assert payload.version == c.manifest.schema_version

    def test_json_has_version(self):
        c = complete_cartridge()
        d = export_archengine_payload_json(c)
        assert d["version"] == c.manifest.schema_version


# ===================================================================
# Disabled policies excluded
# ===================================================================

class TestExportDisabledPolicies:
    def test_disabled_policies_excluded(self):
        c = disabled_policies_cartridge()
        payload = export_archengine_payload(c)
        ids = [p["identifier"] for p in payload.boundaries["policies"]]
        # Only the enabled policy should appear
        active = [p for p in c.behavior.policies if p.enabled]
        assert len(payload.boundaries["policies"]) == len(active)

    def test_json_disabled_policies_absent(self):
        c = disabled_policies_cartridge()
        d = export_archengine_payload_json(c)
        ids = [p["identifier"] for p in d["boundaries"]["policies"]]
        inactive = [p.identifier for p in c.behavior.policies if not p.enabled]
        for id_ in inactive:
            assert id_ not in ids


# ===================================================================
# Aliases preserved
# ===================================================================

class TestExportAliases:
    def test_aliases_in_chimera_metadata(self):
        c = aliases_and_metadata_cartridge()
        payload = export_archengine_payload(c)
        assert payload.metadata["chimera"]["aliases"] == list(c.identity.aliases)

    def test_json_aliases_preserved(self):
        c = aliases_and_metadata_cartridge()
        d = export_archengine_payload_json(c)
        assert d["metadata"]["chimera"]["aliases"] == list(c.identity.aliases)


# ===================================================================
# Fixtures validate
# ===================================================================

class TestExportFixtures:
    def test_all_fixtures_generate_successfully(self):
        payloads = generate_all_payloads()
        assert len(payloads) == 5
        for name, payload in payloads.items():
            assert payload.id is not None, f"{name} has no id"
            assert payload.name is not None, f"{name} has no name"
            assert payload.version is not None, f"{name} has no version"

    def test_minimal_fixture_has_required_fields(self):
        payloads = generate_all_payloads()
        p = payloads["minimal"]
        assert p.name == "Min"
        assert p.id is not None
        assert p.version is not None

    def test_complete_fixture_has_all_fields(self):
        payloads = generate_all_payloads()
        p = payloads["complete"]
        assert len(p.values["core_values"]) == 2
        assert len(p.disposition["strengths"]) == 2
        assert len(p.preferences) == 3
        assert len(p.boundaries["policies"]) == 3

    def test_legacy_fixture_matches_forged(self):
        payloads = generate_all_payloads()
        legacy = payloads["legacy_upgraded"]
        draft = PersonaDraft(
            name="Legacy",
            identifier="legacy",
            summary="Upgraded from 0.1.0",
            description="Test legacy upgrade",
            communication_style="Formal",
            core_values=["Integrity"],
            motivations=["Truth"],
            strengths=["Precision"],
            limitations=["Rigidity"],
            goals=["Accuracy"],
            boundaries=["Never guess"],
            preferences={"style": "formal"},
            behavior_rules=["Verify facts", "Be precise"],
        )
        forged = CartridgeForge.forge(draft)
        assert forged.success is True
        forged_payload = export_archengine_payload(forged.cartridge)
        assert legacy.name == forged_payload.name
        assert legacy.values == forged_payload.values

    def test_disabled_policies_fixture(self):
        payloads = generate_all_payloads()
        p = payloads["disabled_policies"]
        assert len(p.boundaries["policies"]) == 1

    def test_aliases_fixture(self):
        payloads = generate_all_payloads()
        p = payloads["aliases_and_metadata"]
        assert len(p.metadata["chimera"]["aliases"]) == 3
        assert p.metadata["chimera"]["tone"] == ["Friendly", "Professional"]

    def test_fixture_json_round_trips(self):
        payloads = generate_all_payloads()
        for name, payload in payloads.items():
            d = payload.to_dict()
            text = json.dumps(d, ensure_ascii=False)
            restored = json.loads(text)
            assert restored["id"] == payload.id, f"{name} round-trip failed"
            assert restored["name"] == payload.name, f"{name} round-trip failed"


# ===================================================================
# Delegation — export service delegates to compatibility shim
# ===================================================================

class TestExportDelegation:
    def test_export_uses_projection_and_shim(self):
        # Indirectly verified: the payload contains expected shim fields
        c = complete_cartridge()
        payload = export_archengine_payload(c)
        # Values come from the shim's mapping
        assert "core_values" in payload.values
        assert "motivations" in payload.values
        assert "strengths" in payload.disposition
        assert "limitations" in payload.disposition
        # Preferences are flat key-value from shim
        assert "formality" in payload.preferences
        assert "verbosity" in payload.preferences


# ===================================================================
# Newly forged vs upgraded produce identical exports
# ===================================================================

class TestExportUpgradeParity:
    def test_legacy_and_forged_export_identical(self):
        legacy = legacy_upgraded_cartridge()
        legacy_payload = export_archengine_payload(legacy)

        draft = PersonaDraft(
            name="Legacy",
            identifier="legacy",
            summary="Upgraded from 0.1.0",
            description="Test legacy upgrade",
            communication_style="Formal",
            core_values=["Integrity"],
            motivations=["Truth"],
            strengths=["Precision"],
            limitations=["Rigidity"],
            goals=["Accuracy"],
            boundaries=["Never guess"],
            preferences={"style": "formal"},
            behavior_rules=["Verify facts", "Be precise"],
        )
        forged = CartridgeForge.forge(draft)
        assert forged.success is True
        forged_payload = export_archengine_payload(forged.cartridge)

        # Compare ignoring cartridge_id (different by design) and export timestamp
        def normalize(p):
            d = p.to_dict()
            d.pop("id")
            d["metadata"]["chimera"].pop("exported_at", None)
            d["metadata"]["chimera"].pop("schema_version", None)
            return d

        assert normalize(legacy_payload) == normalize(forged_payload)
