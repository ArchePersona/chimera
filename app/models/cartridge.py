from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class CartridgeStatus(Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    FORGED = "forged"


class ValidationCode(Enum):
    REQUIRED_FIELD_EMPTY = "REQUIRED_FIELD_EMPTY"
    REQUIRED_LIST_EMPTY = "REQUIRED_LIST_EMPTY"
    INVALID_TYPE = "INVALID_TYPE"
    NO_BEHAVIOR_RULES = "NO_BEHAVIOR_RULES"


class ForgeErrorCode(Enum):
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_STATE = "INVALID_STATE"


@dataclass(frozen=True)
class CartridgeValidationError:
    code: ValidationCode
    field: str
    message: str


@dataclass(frozen=True)
class CartridgeValidationWarning:
    code: ValidationCode
    field: str
    message: str


@dataclass(frozen=True)
class CartridgeValidationResult:
    valid: bool
    errors: list[CartridgeValidationError] = field(default_factory=list)
    warnings: list[CartridgeValidationWarning] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


@dataclass
class PersonaDraft:
    name: str = ""
    summary: str = ""
    communication_style: str = ""
    core_values: list[str] = field(default_factory=list)
    motivations: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    preferences: dict[str, str] = field(default_factory=dict)
    behavior_rules: list[str] = field(default_factory=list)

    cartridge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_name: str = "archepersona.chimera.persona-cartridge"
    schema_version: str = "0.1.0"
    status: CartridgeStatus = CartridgeStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def normalize(draft: PersonaDraft) -> PersonaDraft:
        draft.name = draft.name.strip()
        draft.summary = draft.summary.strip()
        draft.communication_style = draft.communication_style.strip()
        draft.core_values = [v.strip() for v in draft.core_values if v.strip()]
        draft.motivations = [v.strip() for v in draft.motivations if v.strip()]
        draft.strengths = [v.strip() for v in draft.strengths if v.strip()]
        draft.limitations = [v.strip() for v in draft.limitations if v.strip()]
        draft.goals = [v.strip() for v in draft.goals if v.strip()]
        draft.boundaries = [v.strip() for v in draft.boundaries if v.strip()]
        draft.behavior_rules = [v.strip() for v in draft.behavior_rules if v.strip()]
        draft.preferences = {k.strip(): v.strip() for k, v in draft.preferences.items() if k.strip()}
        return draft


@dataclass(frozen=True)
class PersonaCartridge:
    name: str
    summary: str
    communication_style: str
    core_values: tuple[str, ...]
    motivations: tuple[str, ...]
    strengths: tuple[str, ...]
    limitations: tuple[str, ...]
    goals: tuple[str, ...]
    boundaries: tuple[str, ...]
    preferences: tuple[tuple[str, str], ...]
    behavior_rules: tuple[str, ...]

    cartridge_id: str
    schema_name: str
    schema_version: str
    status: CartridgeStatus
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        d["preferences"] = dict(self.preferences)
        return d

    @staticmethod
    def schema() -> dict:
        return {
            "name": "archepersona.chimera.persona-cartridge",
            "version": "0.1.0",
            "description": "Canonical CHIMERA Persona Cartridge",
        }


@dataclass(frozen=True)
class ForgeError:
    code: ForgeErrorCode
    message: str
    detail: str = ""


@dataclass(frozen=True)
class ForgeResult:
    success: bool
    cartridge: Optional[PersonaCartridge] = None
    error: Optional[ForgeError] = None

    def __bool__(self) -> bool:
        return self.success
