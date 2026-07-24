from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone

from app.models.cartridge import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    BehaviorModule,
    BehaviorPolicy,
    CartridgeManifest,
    CartridgeStatus,
    CartridgeValidationError,
    CartridgeValidationResult,
    CartridgeValidationWarning,
    CharacterModule,
    CommunicationModule,
    ForgeError,
    ForgeErrorCode,
    ForgeResult,
    IdentityModule,
    PersonaCartridge,
    PersonaDraft,
    PreferenceEntry,
    PreferenceModule,
    generate_behavior_identifiers,
)
from app.specification.validator import SpecificationValidator


class CartridgeForge:
    """Single authoritative forge path for CHIMERA cartridges."""

    @classmethod
    def validate(cls, draft: PersonaDraft) -> tuple[CartridgeValidationResult, PersonaDraft]:
        working = copy.deepcopy(draft)
        PersonaDraft.normalize(working)

        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []

        modules = cls._build_modules(working)
        for mod in modules:
            mod_errors, mod_warnings = mod.validate()
            errors.extend(mod_errors)
            warnings.extend(mod_warnings)

        if errors:
            return CartridgeValidationResult(valid=False, errors=errors, warnings=warnings), working

        working.status = CartridgeStatus.VALIDATED
        return CartridgeValidationResult(valid=True, warnings=warnings), working

    @classmethod
    def forge(cls, draft: PersonaDraft) -> ForgeResult:
        result, validated = cls.validate(draft)

        if not result.valid:
            return ForgeResult(
                success=False,
                error=ForgeError(
                    code=ForgeErrorCode.VALIDATION_FAILED,
                    message="Cartridge validation failed",
                    detail="; ".join(e.message for e in result.errors),
                ),
                warnings=result.warnings,
            )

        validated.updated_at = datetime.now(timezone.utc)

        manifest = CartridgeManifest(
            cartridge_id=str(uuid.uuid4()),
            schema_name=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            created_at=validated.created_at,
            updated_at=validated.updated_at,
        )

        identity = IdentityModule(
            display_name=validated.name,
            identifier=validated.identifier,
            summary=validated.summary,
            description=validated.description,
            aliases=tuple(validated.aliases),
        )

        character = CharacterModule(
            core_values=tuple(validated.core_values),
            motivations=tuple(validated.motivations),
            strengths=tuple(validated.strengths),
            limitations=tuple(validated.limitations),
            goals=tuple(validated.goals),
            boundaries=tuple(validated.boundaries),
        )

        preferences = PreferenceModule(
            entries=tuple(
                PreferenceEntry(key=k, value=v)
                for k, v in sorted(validated.preferences.items())
            ),
        )

        identifiers = generate_behavior_identifiers(validated.behavior_rules)
        behavior = BehaviorModule(
            policies=tuple(
                BehaviorPolicy(
                    identifier=identifiers[i],
                    title=r.strip(),
                )
                for i, r in enumerate(validated.behavior_rules)
            ),
        )

        communication = CommunicationModule(
            communication_style=validated.communication_style,
            tone=tuple(validated.tone),
            vocabulary_preferences=tuple(validated.vocabulary_preferences),
            response_tendencies=tuple(validated.response_tendencies),
            formatting_preferences=tuple(validated.formatting_preferences),
        )

        cartridge = PersonaCartridge(
            manifest=manifest,
            identity=identity,
            character=character,
            preferences=preferences,
            behavior=behavior,
            communication=communication,
            status=CartridgeStatus.FORGED,
        )

        spec_result = SpecificationValidator.validate(cartridge)
        if not spec_result.compliant:
            return ForgeResult(
                success=False,
                error=ForgeError(
                    code=ForgeErrorCode.VALIDATION_FAILED,
                    message="Cartridge specification validation failed",
                    detail="; ".join(f"{v.rule}: {v.reason}" for v in spec_result.violations),
                ),
                warnings=result.warnings,
            )

        return ForgeResult(
            success=True,
            cartridge=cartridge,
            warnings=result.warnings,
        )

    @classmethod
    def validate_cartridge(
        cls, cartridge: PersonaCartridge
    ) -> tuple[CartridgeValidationResult, dict]:
        """Validate an existing cartridge for re-validation in the inspector.

        Returns module-level validation and specification compliance.
        """
        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []

        modules = [
            IdentityModule(
                display_name=cartridge.identity.display_name,
                identifier=cartridge.identity.identifier,
                summary=cartridge.identity.summary,
                description=cartridge.identity.description,
                aliases=cartridge.identity.aliases,
            ),
            CharacterModule(
                core_values=cartridge.character.core_values,
                motivations=cartridge.character.motivations,
                strengths=cartridge.character.strengths,
                limitations=cartridge.character.limitations,
                goals=cartridge.character.goals,
                boundaries=cartridge.character.boundaries,
            ),
            PreferenceModule(entries=cartridge.preferences.entries),
            BehaviorModule(policies=cartridge.behavior.policies),
            CommunicationModule(
                communication_style=cartridge.communication.communication_style,
                tone=cartridge.communication.tone,
                vocabulary_preferences=cartridge.communication.vocabulary_preferences,
                response_tendencies=cartridge.communication.response_tendencies,
                formatting_preferences=cartridge.communication.formatting_preferences,
            ),
        ]
        for mod in modules:
            mod_errors, mod_warnings = mod.validate()
            errors.extend(mod_errors)
            warnings.extend(mod_warnings)

        result = CartridgeValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings
        )

        spec_result = SpecificationValidator.validate(cartridge)
        spec_dict = {
            "compliant": spec_result.compliant,
            "violations": [
                {
                    "rule": v.rule,
                    "location": v.location,
                    "reason": v.reason,
                    "recommendation": v.recommendation,
                }
                for v in spec_result.violations
            ],
        }

        return result, spec_dict

    @classmethod
    def _build_modules(cls, draft: PersonaDraft) -> list:
        return [
            IdentityModule(
                display_name=draft.name,
                identifier=draft.identifier,
                summary=draft.summary,
                description=draft.description,
                aliases=tuple(draft.aliases),
            ),
            CharacterModule(
                core_values=tuple(draft.core_values),
                motivations=tuple(draft.motivations),
                strengths=tuple(draft.strengths),
                limitations=tuple(draft.limitations),
                goals=tuple(draft.goals),
                boundaries=tuple(draft.boundaries),
            ),
            PreferenceModule(
                entries=tuple(
                    PreferenceEntry(key=k, value=v)
                    for k, v in sorted(draft.preferences.items())
                ),
            ),
            BehaviorModule(
                policies=tuple(
                    BehaviorPolicy(
                        identifier=_bid,
                        title=r.strip(),
                    )
                    for r, _bid in zip(
                        draft.behavior_rules,
                        generate_behavior_identifiers(draft.behavior_rules),
                    )
                ),
            ),
            CommunicationModule(
                communication_style=draft.communication_style,
                tone=tuple(draft.tone),
                vocabulary_preferences=tuple(draft.vocabulary_preferences),
                response_tendencies=tuple(draft.response_tendencies),
                formatting_preferences=tuple(draft.formatting_preferences),
            ),
        ]
