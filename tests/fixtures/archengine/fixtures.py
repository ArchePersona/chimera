"""Canonical integration fixtures for ARCHEngine compatibility testing."""

from app.integrations.archengine import CartridgeDescriptorPayload
from app.models.cartridge import (
    BehaviorModule,
    BehaviorPolicy,
    CartridgeStatus,
    PersonaCartridge,
    PersonaDraft,
)
from app.services.archengine_export import export_archengine_payload
from app.services.forge import CartridgeForge
from app.services.serializer import CartridgeSerializer


def minimal_cartridge() -> PersonaCartridge:
    draft = PersonaDraft(
        name="Min",
        identifier="min",
        summary="A minimal persona",
        core_values=["X"],
        motivations=["Y"],
        strengths=["Z"],
        limitations=["L"],
        goals=["G"],
        boundaries=["B"],
    )
    result = CartridgeForge.forge(draft)
    assert result.success is True
    assert result.cartridge is not None
    return result.cartridge


def complete_cartridge() -> PersonaCartridge:
    draft = PersonaDraft(
        name="Alex",
        identifier="alex",
        summary="A thoughtful guide",
        description="Optional description",
        aliases=["The Guide", "Alex the Great"],
        communication_style="Warm and direct",
        core_values=["Curiosity", "Empathy"],
        motivations=["To help others grow", "To explore"],
        strengths=["Patience", "Listening"],
        limitations=["Overthinking", "Shyness"],
        goals=["Inspire learning", "Build community"],
        boundaries=["Never lie", "Respect privacy"],
        behavior_rules=[
            "Ask before acting",
            "Cite sources",
            "Avoid speculation",
        ],
        preferences={
            "formality": "casual",
            "verbosity": "medium",
            "temperature": 0.7,
        },
    )
    result = CartridgeForge.forge(draft)
    assert result.success is True
    assert result.cartridge is not None
    return result.cartridge


def legacy_upgraded_cartridge() -> PersonaCartridge:
    data = {
        "manifest": {
            "cartridge_id": "legacy-fixture-id",
            "schema_name": "archepersona.chimera.persona-cartridge",
            "schema_version": "0.1.0",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        },
        "name": "Legacy",
        "identifier": "legacy",
        "summary": "Upgraded from 0.1.0",
        "description": "Test legacy upgrade",
        "communication_style": "Formal",
        "core_values": ["Integrity"],
        "motivations": ["Truth"],
        "strengths": ["Precision"],
        "limitations": ["Rigidity"],
        "goals": ["Accuracy"],
        "boundaries": ["Never guess"],
        "preferences": {"style": "formal"},
        "behavior_rules": ["Verify facts", "Be precise"],
        "extensions": {},
        "status": "forged",
    }
    return CartridgeSerializer.deserialize(data)


def disabled_policies_cartridge() -> PersonaCartridge:
    draft = PersonaDraft(
        name="Filtered",
        identifier="filtered",
        summary="Has disabled policies",
        core_values=["X"],
        motivations=["Y"],
        strengths=["Z"],
        limitations=["L"],
        goals=["G"],
        boundaries=["B"],
        behavior_rules=["Active rule", "Inactive rule"],
    )
    result = CartridgeForge.forge(draft)
    assert result.success is True
    assert result.cartridge is not None
    c = result.cartridge
    policies = list(c.behavior.policies)
    modified = BehaviorModule(
        policies=(
            policies[0],
            BehaviorPolicy(
                identifier=policies[1].identifier,
                title=policies[1].title,
                enabled=False,
            ),
        )
    )
    return PersonaCartridge(
        manifest=c.manifest,
        identity=c.identity,
        character=c.character,
        preferences=c.preferences,
        behavior=modified,
        communication=c.communication,
        status=CartridgeStatus.FORGED,
    )


def aliases_and_metadata_cartridge() -> PersonaCartridge:
    draft = PersonaDraft(
        name="Multi-Alias",
        identifier="multi_alias",
        summary="Persona with many aliases",
        description="Has aliases and rich metadata",
        aliases=["Alpha", "Beta", "Gamma"],
        communication_style="Adaptive",
        tone=["Friendly", "Professional"],
        vocabulary_preferences=["Plain language"],
        response_tendencies=["Concise", "Thorough"],
        formatting_preferences=["Markdown"],
        core_values=["Versatility"],
        motivations=["Adaptation"],
        strengths=["Flexibility"],
        limitations=["Inconsistency"],
        goals=["Coverage"],
        boundaries=["Stay on topic"],
        behavior_rules=["Adapt to context"],
        preferences={"mode": "adaptive"},
    )
    result = CartridgeForge.forge(draft)
    assert result.success is True
    assert result.cartridge is not None
    return result.cartridge


def generate_all_payloads() -> dict[str, CartridgeDescriptorPayload]:
    """Generate and return all canonical ARCHEngine export payloads.

    Returns a dict keyed by fixture name for use in tests.
    """
    fixtures: dict[str, CartridgeDescriptorPayload] = {
        "minimal": export_archengine_payload(minimal_cartridge()),
        "complete": export_archengine_payload(complete_cartridge()),
        "legacy_upgraded": export_archengine_payload(legacy_upgraded_cartridge()),
        "disabled_policies": export_archengine_payload(disabled_policies_cartridge()),
        "aliases_and_metadata": export_archengine_payload(aliases_and_metadata_cartridge()),
    }
    return fixtures
