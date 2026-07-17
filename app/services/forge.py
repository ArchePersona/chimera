from __future__ import annotations

from datetime import datetime, timezone

from app.models.cartridge import (
    CartridgeStatus,
    CartridgeValidationError,
    CartridgeValidationResult,
    CartridgeValidationWarning,
    ForgeError,
    ForgeErrorCode,
    ForgeResult,
    PersonaCartridge,
    PersonaDraft,
    ValidationCode,
)


class CartridgeForge:
    """Single authoritative forge path for CHIMERA cartridges."""

    _REQUIRED_TEXT_FIELDS = ["name", "summary", "communication_style"]
    _REQUIRED_LIST_FIELDS = [
        "core_values",
        "motivations",
        "strengths",
        "limitations",
        "goals",
        "boundaries",
    ]

    @classmethod
    def validate(cls, draft: PersonaDraft) -> CartridgeValidationResult:
        PersonaDraft.normalize(draft)

        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []

        for field_name in cls._REQUIRED_TEXT_FIELDS:
            val = getattr(draft, field_name, "")
            if not val:
                errors.append(
                    CartridgeValidationError(
                        code=ValidationCode.REQUIRED_FIELD_EMPTY,
                        field=field_name,
                        message=f"'{field_name}' must not be empty",
                    )
                )

        for field_name in cls._REQUIRED_LIST_FIELDS:
            val = getattr(draft, field_name, [])
            if not isinstance(val, list) or len(val) == 0:
                errors.append(
                    CartridgeValidationError(
                        code=ValidationCode.REQUIRED_LIST_EMPTY,
                        field=field_name,
                        message=f"'{field_name}' must contain at least one item",
                    )
                )

        if not isinstance(draft.preferences, dict):
            errors.append(
                CartridgeValidationError(
                    code=ValidationCode.INVALID_TYPE,
                    field="preferences",
                    message="'preferences' must be a dict",
                )
            )

        if len(draft.behavior_rules) == 0:
            warnings.append(
                CartridgeValidationWarning(
                    code=ValidationCode.NO_BEHAVIOR_RULES,
                    field="behavior_rules",
                    message="No behavior rules defined. Consider adding at least one rule.",
                )
            )

        return CartridgeValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def forge(cls, draft: PersonaDraft) -> ForgeResult:
        validation = cls.validate(draft)
        if not validation.valid:
            return ForgeResult(
                success=False,
                error=ForgeError(
                    code=ForgeErrorCode.VALIDATION_FAILED,
                    message="Cartridge validation failed",
                    detail="; ".join(e.message for e in validation.errors),
                ),
            )

        draft.updated_at = datetime.now(timezone.utc)

        cartridge = PersonaCartridge(
            name=draft.name,
            summary=draft.summary,
            communication_style=draft.communication_style,
            core_values=tuple(draft.core_values),
            motivations=tuple(draft.motivations),
            strengths=tuple(draft.strengths),
            limitations=tuple(draft.limitations),
            goals=tuple(draft.goals),
            boundaries=tuple(draft.boundaries),
            preferences=tuple(sorted(draft.preferences.items())),
            behavior_rules=tuple(draft.behavior_rules),
            cartridge_id=draft.cartridge_id,
            schema_name=draft.schema_name,
            schema_version=draft.schema_version,
            status=CartridgeStatus.FORGED,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

        return ForgeResult(success=True, cartridge=cartridge)
