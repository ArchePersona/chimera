from __future__ import annotations

import abc
import copy
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Centralized schema constants
# ---------------------------------------------------------------------------

SCHEMA_NAME = "archepersona.chimera.persona-cartridge"
SCHEMA_VERSION = "0.6.0"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CartridgeStatus(Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    FORGED = "forged"


class ValidationCode(Enum):
    REQUIRED_FIELD_EMPTY = "REQUIRED_FIELD_EMPTY"
    REQUIRED_LIST_EMPTY = "REQUIRED_LIST_EMPTY"
    INVALID_TYPE = "INVALID_TYPE"
    EMPTY_PREFERENCE_KEY = "EMPTY_PREFERENCE_KEY"
    INVALID_PREFERENCE_KEY_SYNTAX = "INVALID_PREFERENCE_KEY_SYNTAX"
    DUPLICATE_PREFERENCE_KEY = "DUPLICATE_PREFERENCE_KEY"
    INVALID_PREFERENCE_VALUE_TYPE = "INVALID_PREFERENCE_VALUE_TYPE"
    INVALID_PREFERENCE_SCOPE = "INVALID_PREFERENCE_SCOPE"
    INVALID_PREFERENCE_PRIORITY = "INVALID_PREFERENCE_PRIORITY"
    INVALID_BEHAVIOR_IDENTIFIER = "INVALID_BEHAVIOR_IDENTIFIER"
    DUPLICATE_BEHAVIOR_IDENTIFIER = "DUPLICATE_BEHAVIOR_IDENTIFIER"
    INVALID_BEHAVIOR_CATEGORY = "INVALID_BEHAVIOR_CATEGORY"
    INVALID_BEHAVIOR_POLICY_TYPE = "INVALID_BEHAVIOR_POLICY_TYPE"
    NO_BEHAVIOR_RULES = "NO_BEHAVIOR_RULES"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"


class ForgeErrorCode(Enum):
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_STATE = "INVALID_STATE"


# ---------------------------------------------------------------------------
# Version utilities
# ---------------------------------------------------------------------------

class UnsupportedVersionError(Exception):
    def __init__(self, version: str, supported: frozenset[str]) -> None:
        self.version = version
        self.supported = supported
        super().__init__(
            f"Unsupported cartridge version '{version}'. "
            f"Supported: {', '.join(sorted(supported))}"
        )


def parse_version(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version string: '{version}'")
    return tuple(int(p) for p in parts)


def is_version_supported(version: str, supported: frozenset[str]) -> bool:
    return version in supported


# ---------------------------------------------------------------------------
# Validation types
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# PreferenceEntry — immutable authored preference record
# ---------------------------------------------------------------------------

_VALID_SCOPES = frozenset({"global", "contextual"})
_VALID_PRIORITIES = frozenset({"low", "normal", "high"})
_PREFERENCE_KEY_ALLOWED = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")
_ALLOWED_VALUE_TYPES = (str, int, float, bool)


@dataclass(frozen=True)
class PreferenceEntry:
    key: str
    value: str | int | float | bool
    scope: str = "global"
    priority: str = "normal"
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "scope": self.scope,
            "priority": self.priority,
            "description": self.description,
        }

    def validate_entry(
        self,
        prefix: str = "preferences.entries",
    ) -> list[CartridgeValidationError]:
        errors: list[CartridgeValidationError] = []
        if not self.key:
            errors.append(CartridgeValidationError(
                code=ValidationCode.EMPTY_PREFERENCE_KEY,
                field=f"{prefix}.key",
                message="Preference key must not be empty",
            ))
        elif not self.key[0].isalpha():
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_PREFERENCE_KEY_SYNTAX,
                field=f"{prefix}.{self.key}.key",
                message=f"Preference key '{self.key}' must begin with a letter",
            ))
        else:
            for ch in self.key:
                if ch not in _PREFERENCE_KEY_ALLOWED:
                    errors.append(CartridgeValidationError(
                        code=ValidationCode.INVALID_PREFERENCE_KEY_SYNTAX,
                        field=f"{prefix}.{self.key}.key",
                        message=f"Preference key '{self.key}' contains invalid character '{ch}' — allowed: a-z, 0-9, _",
                    ))
                    break
        if not isinstance(self.value, _ALLOWED_VALUE_TYPES):
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_PREFERENCE_VALUE_TYPE,
                field=f"{prefix}.{self.key}.value",
                message=f"Preference value for '{self.key}' must be str, int, float, or bool",
            ))
        if self.scope not in _VALID_SCOPES:
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_PREFERENCE_SCOPE,
                field=f"{prefix}.{self.key}.scope",
                message=f"Preference scope for '{self.key}' must be 'global' or 'contextual'",
            ))
        if self.priority not in _VALID_PRIORITIES:
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_PREFERENCE_PRIORITY,
                field=f"{prefix}.{self.key}.priority",
                message=f"Preference priority for '{self.key}' must be 'low', 'normal', or 'high'",
            ))
        return errors


# ---------------------------------------------------------------------------
# BehaviorPolicy — immutable authored behavior policy record
# ---------------------------------------------------------------------------

_VALID_CATEGORIES = frozenset({"interaction", "reasoning", "safety", "workflow", "presentation"})
_VALID_POLICY_TYPES = frozenset({"required", "preferred", "prohibited"})
_BEHAVIOR_IDENTIFIER_ALLOWED = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")


@dataclass(frozen=True)
class BehaviorPolicy:
    identifier: str
    title: str
    description: str = ""
    category: str = "interaction"
    policy_type: str = "preferred"
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "policy_type": self.policy_type,
            "enabled": self.enabled,
        }

    def validate_policy(
        self,
        prefix: str = "behavior.policies",
    ) -> list[CartridgeValidationError]:
        errors: list[CartridgeValidationError] = []
        if not self.identifier:
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_BEHAVIOR_IDENTIFIER,
                field=f"{prefix}.identifier",
                message="Behavior policy identifier must not be empty",
            ))
        elif not self.identifier[0].isalpha():
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_BEHAVIOR_IDENTIFIER,
                field=f"{prefix}.{self.identifier}.identifier",
                message=f"Behavior policy identifier '{self.identifier}' must begin with a letter",
            ))
        else:
            for ch in self.identifier:
                if ch not in _BEHAVIOR_IDENTIFIER_ALLOWED:
                    errors.append(CartridgeValidationError(
                        code=ValidationCode.INVALID_BEHAVIOR_IDENTIFIER,
                        field=f"{prefix}.{self.identifier}.identifier",
                        message=f"Behavior policy identifier '{self.identifier}' contains invalid character '{ch}' — allowed: a-z, 0-9, _",
                    ))
                    break
        if not self.title:
            errors.append(CartridgeValidationError(
                code=ValidationCode.REQUIRED_FIELD_EMPTY,
                field=f"{prefix}.{self.identifier}.title",
                message=f"Behavior policy '{self.identifier}' title must not be empty",
            ))
        if self.category not in _VALID_CATEGORIES:
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_BEHAVIOR_CATEGORY,
                field=f"{prefix}.{self.identifier}.category",
                message=f"Behavior policy '{self.identifier}' category must be one of: interaction, reasoning, safety, workflow, presentation",
            ))
        if self.policy_type not in _VALID_POLICY_TYPES:
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_BEHAVIOR_POLICY_TYPE,
                field=f"{prefix}.{self.identifier}.policy_type",
                message=f"Behavior policy '{self.identifier}' policy_type must be one of: required, preferred, prohibited",
            ))
        return errors


# ---------------------------------------------------------------------------
# CartridgeManifest — immutable metadata separate from persona content
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CartridgeManifest:
    cartridge_id: str
    schema_name: str = SCHEMA_NAME
    schema_version: str = SCHEMA_VERSION
    specification_version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return d


# ---------------------------------------------------------------------------
# PersonaDraft (flat user input)
# ---------------------------------------------------------------------------

def _dedup_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


@dataclass
class PersonaDraft:
    # identity
    name: str = ""
    identifier: str = ""
    summary: str = ""
    description: str = ""
    aliases: list[str] = field(default_factory=list)

    # character
    core_values: list[str] = field(default_factory=list)
    motivations: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)

    # communication
    communication_style: str = ""
    tone: list[str] = field(default_factory=list)
    vocabulary_preferences: list[str] = field(default_factory=list)
    response_tendencies: list[str] = field(default_factory=list)
    formatting_preferences: list[str] = field(default_factory=list)

    # preferences
    preferences: dict[str, Any] = field(default_factory=dict)

    # behavior (reserved)
    behavior_rules: list[str] = field(default_factory=list)

    status: CartridgeStatus = CartridgeStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def normalize(draft: PersonaDraft) -> PersonaDraft:
        draft.name = draft.name.strip()
        draft.identifier = draft.identifier.strip().lower()
        draft.summary = draft.summary.strip()
        draft.description = draft.description.strip()
        _normalize_list(draft.aliases)

        _normalize_list(draft.core_values)
        _normalize_list(draft.motivations)
        _normalize_list(draft.strengths)
        _normalize_list(draft.limitations)
        _normalize_list(draft.goals)
        _normalize_list(draft.boundaries)

        draft.communication_style = draft.communication_style.strip()
        _normalize_list(draft.tone)
        _normalize_list(draft.vocabulary_preferences)
        _normalize_list(draft.response_tendencies)
        _normalize_list(draft.formatting_preferences)

        _normalize_list(draft.behavior_rules)

        cleaned: dict[str, Any] = {}
        for k, v in draft.preferences.items():
            kk = k.strip()
            if isinstance(v, str):
                vv = v.strip()
                if not vv:
                    vv = ""
            else:
                vv = v
            cleaned[kk] = vv
        draft.preferences = cleaned

        return draft


def _normalize_list(lst: list[str]) -> None:
    stripped = [item.strip() for item in lst if item.strip()]
    lst.clear()
    lst.extend(_dedup_ordered(stripped))


# ---------------------------------------------------------------------------
# CartridgeModule — abstract base contract
# ---------------------------------------------------------------------------

class CartridgeModule(abc.ABC):
    """Contract every cartridge module must satisfy."""

    @classmethod
    @abc.abstractmethod
    def module_name(cls) -> str:
        ...

    @classmethod
    @abc.abstractmethod
    def module_schema_version(cls) -> int:
        ...

    @abc.abstractmethod
    def to_dict(self) -> dict:
        ...

    @abc.abstractmethod
    def validate(
        self,
    ) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
        ...


# ---------------------------------------------------------------------------
# Module Registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModuleRegistryEntry:
    module_type: type[CartridgeModule]
    module_schema_version: int


_MODULE_REGISTRY: dict[str, ModuleRegistryEntry] = {}


def register_module(module_type: type[CartridgeModule]) -> ModuleRegistryEntry:
    name = module_type.module_name()
    entry = ModuleRegistryEntry(
        module_type=module_type,
        module_schema_version=module_type.module_schema_version(),
    )
    _MODULE_REGISTRY[name] = entry
    return entry


class ModuleRegistry:
    """Immutable view of the module registry."""

    @classmethod
    def lookup(cls, name: str) -> ModuleRegistryEntry:
        if name not in _MODULE_REGISTRY:
            raise KeyError(f"Unknown module: '{name}'")
        return _MODULE_REGISTRY[name]

    @classmethod
    def entries(cls) -> dict[str, ModuleRegistryEntry]:
        return dict(_MODULE_REGISTRY)

    @classmethod
    def names(cls) -> list[str]:
        return sorted(_MODULE_REGISTRY)


# ---------------------------------------------------------------------------
# Modules (immutable, single-responsibility)
# ---------------------------------------------------------------------------

_IDENTIFIER_ALLOWED = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")
_BEHAVIOR_IDENTIFIER_ALLOWED_SET = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")


def _rule_to_base_identifier(rule: str, position: int) -> str:
    """Normalize a rule string to a valid base identifier (may still collide)."""
    text = rule.strip().lower()
    chars: list[str] = []
    for ch in text:
        if 'a' <= ch <= 'z' or '0' <= ch <= '9':
            chars.append(ch)
        elif ch == '_':
            if chars and chars[-1] != '_':
                chars.append('_')
        else:
            if chars and chars[-1] != '_':
                chars.append('_')
    while chars and chars[-1] == '_':
        chars.pop()
    if chars and chars[0] == '_':
        chars.pop(0)
    ident = ''.join(chars)
    if not ident:
        return f"policy_{position + 1}"
    if not ident[0].isalpha():
        return f"policy_{ident}"
    return ident


def generate_behavior_identifiers(rules: list[str]) -> list[str]:
    """Generate valid, unique identifiers for an ordered list of behavior rules.

    Deterministic, stable, handles collisions (numeric suffix), repeated rules,
    punctuation-only (positional fallback), digit-leading (policy_ prefix),
    and empty/invalid identifiers.
    """
    identifiers: list[str] = []
    used: set[str] = set()
    for i, rule in enumerate(rules):
        base = _rule_to_base_identifier(rule, i)
        if base not in used:
            ident = base
        else:
            suffix = 2
            ident = f"{base}_{suffix}"
            while ident in used:
                suffix += 1
                ident = f"{base}_{suffix}"
        used.add(ident)
        identifiers.append(ident)
    return identifiers


def _validate_identifier(value: str) -> str | None:
    """Return an error message if *value* is not a valid identifier, else None."""
    if not value:
        return "must not be empty"
    if not value[0].isalpha():
        return "must begin with a letter"
    for ch in value:
        if ch not in _IDENTIFIER_ALLOWED:
            return f"invalid character '{ch}' — allowed: a-z, 0-9, -, _"
    return None


@dataclass(frozen=True)
class IdentityModule(CartridgeModule):
    display_name: str
    identifier: str
    summary: str
    description: str = ""
    aliases: tuple[str, ...] = ()

    @classmethod
    def module_name(cls) -> str:
        return "identity"

    @classmethod
    def module_schema_version(cls) -> int:
        return 2

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "identifier": self.identifier,
            "summary": self.summary,
            "description": self.description,
            "aliases": list(self.aliases),
        }

    def validate(self) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []
        if not self.display_name:
            errors.append(CartridgeValidationError(
                code=ValidationCode.REQUIRED_FIELD_EMPTY,
                field="identity.display_name",
                message="'display_name' must not be empty",
            ))
        id_err = _validate_identifier(self.identifier)
        if id_err:
            errors.append(CartridgeValidationError(
                code=ValidationCode.INVALID_IDENTIFIER,
                field="identity.identifier",
                message=f"'identifier' {id_err}",
            ))
        if not self.summary:
            errors.append(CartridgeValidationError(
                code=ValidationCode.REQUIRED_FIELD_EMPTY,
                field="identity.summary",
                message="'summary' must not be empty",
            ))
        return errors, warnings


@dataclass(frozen=True)
class CharacterModule(CartridgeModule):
    core_values: tuple[str, ...] = ()
    motivations: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    goals: tuple[str, ...] = ()
    boundaries: tuple[str, ...] = ()

    @classmethod
    def module_name(cls) -> str:
        return "character"

    @classmethod
    def module_schema_version(cls) -> int:
        return 2

    def to_dict(self) -> dict:
        return {
            "core_values": list(self.core_values),
            "motivations": list(self.motivations),
            "strengths": list(self.strengths),
            "limitations": list(self.limitations),
            "goals": list(self.goals),
            "boundaries": list(self.boundaries),
        }

    def validate(self) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []
        for name, val in [
            ("core_values", self.core_values),
            ("motivations", self.motivations),
            ("strengths", self.strengths),
            ("limitations", self.limitations),
            ("goals", self.goals),
            ("boundaries", self.boundaries),
        ]:
            if not val:
                errors.append(CartridgeValidationError(
                    code=ValidationCode.REQUIRED_LIST_EMPTY,
                    field=f"character.{name}",
                    message=f"'{name}' must contain at least one item",
                ))
        return errors, warnings


@dataclass(frozen=True)
class PreferenceModule(CartridgeModule):
    entries: tuple[PreferenceEntry, ...] = ()

    @classmethod
    def module_name(cls) -> str:
        return "preferences"

    @classmethod
    def module_schema_version(cls) -> int:
        return 2

    def to_dict(self) -> dict:
        return {
            "entries": [
                e.to_dict() for e in sorted(self.entries, key=lambda x: x.key)
            ],
        }

    def validate(self) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []
        seen: set[str] = set()
        for entry in self.entries:
            errors.extend(entry.validate_entry())
            if entry.key in seen:
                errors.append(CartridgeValidationError(
                    code=ValidationCode.DUPLICATE_PREFERENCE_KEY,
                    field=f"preferences.entries.{entry.key}",
                    message=f"Duplicate preference key '{entry.key}'",
                ))
            seen.add(entry.key)
        return errors, warnings


@dataclass(frozen=True)
class BehaviorModule(CartridgeModule):
    policies: tuple[BehaviorPolicy, ...] = ()

    @classmethod
    def module_name(cls) -> str:
        return "behavior"

    @classmethod
    def module_schema_version(cls) -> int:
        return 2

    def to_dict(self) -> dict:
        return {
            "policies": [
                p.to_dict() for p in sorted(self.policies, key=lambda x: x.identifier)
            ],
        }

    def validate(self) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []
        seen: set[str] = set()
        for policy in self.policies:
            errors.extend(policy.validate_policy())
            if policy.identifier in seen:
                errors.append(CartridgeValidationError(
                    code=ValidationCode.DUPLICATE_BEHAVIOR_IDENTIFIER,
                    field=f"behavior.policies.{policy.identifier}",
                    message=f"Duplicate behavior policy identifier '{policy.identifier}'",
                ))
            seen.add(policy.identifier)
        if not self.policies:
            warnings.append(CartridgeValidationWarning(
                code=ValidationCode.NO_BEHAVIOR_RULES,
                field="behavior.policies",
                message="No behavior policies defined. Consider adding at least one policy.",
            ))
        return errors, warnings


@dataclass(frozen=True)
class PersonaStateModulation:
    """Persona-owned biases and boundaries applied while inhabiting a state.

    Mirror of ARCHEngine's PersonaStateModulation shape.
    Zero ARCHEngine imports.
    """

    voice_texture: tuple[str, ...] = ()
    signature_phrasing: tuple[str, ...] = ()
    preferred_moves: tuple[str, ...] = ()
    forbidden_moves: tuple[str, ...] = ()
    lexical_bias: tuple[str, ...] = ()
    metaphor_bias: tuple[str, ...] = ()
    humor_boundary: str | None = None
    warmth_boundary: str | None = None

    def to_dict(self) -> dict:
        d: dict = {}
        if self.voice_texture:
            d["voice_texture"] = list(self.voice_texture)
        if self.signature_phrasing:
            d["signature_phrasing"] = list(self.signature_phrasing)
        if self.preferred_moves:
            d["preferred_moves"] = list(self.preferred_moves)
        if self.forbidden_moves:
            d["forbidden_moves"] = list(self.forbidden_moves)
        if self.lexical_bias:
            d["lexical_bias"] = list(self.lexical_bias)
        if self.metaphor_bias:
            d["metaphor_bias"] = list(self.metaphor_bias)
        if self.humor_boundary is not None:
            d["humor_boundary"] = self.humor_boundary
        if self.warmth_boundary is not None:
            d["warmth_boundary"] = self.warmth_boundary
        return d

    def validate(
        self,
        prefix: str = "state_modulations",
    ) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []
        tuple_fields = (
            "voice_texture",
            "signature_phrasing",
            "preferred_moves",
            "forbidden_moves",
            "lexical_bias",
            "metaphor_bias",
        )
        for fname in tuple_fields:
            val = getattr(self, fname)
            if not isinstance(val, tuple):
                errors.append(CartridgeValidationError(
                    code=ValidationCode.INVALID_TYPE,
                    field=f"{prefix}.{fname}",
                    message=f"'{fname}' must be a tuple",
                ))
            elif not all(isinstance(item, str) for item in val):
                errors.append(CartridgeValidationError(
                    code=ValidationCode.INVALID_TYPE,
                    field=f"{prefix}.{fname}",
                    message=f"'{fname}' items must be strings",
                ))
        for fname in ("humor_boundary", "warmth_boundary"):
            val = getattr(self, fname)
            if val is not None and not isinstance(val, str):
                errors.append(CartridgeValidationError(
                    code=ValidationCode.INVALID_TYPE,
                    field=f"{prefix}.{fname}",
                    message=f"'{fname}' must be a string or None",
                ))
        return errors, warnings


@dataclass(frozen=True)
class CommunicationModule(CartridgeModule):
    communication_style: str = ""
    tone: tuple[str, ...] = ()
    vocabulary_preferences: tuple[str, ...] = ()
    response_tendencies: tuple[str, ...] = ()
    formatting_preferences: tuple[str, ...] = ()
    reserved: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def module_name(cls) -> str:
        return "communication"

    @classmethod
    def module_schema_version(cls) -> int:
        return 2

    def to_dict(self) -> dict:
        d: dict = {}
        if self.communication_style:
            d["communication_style"] = self.communication_style
        if self.tone:
            d["tone"] = list(self.tone)
        if self.vocabulary_preferences:
            d["vocabulary_preferences"] = list(self.vocabulary_preferences)
        if self.response_tendencies:
            d["response_tendencies"] = list(self.response_tendencies)
        if self.formatting_preferences:
            d["formatting_preferences"] = list(self.formatting_preferences)
        if self.reserved:
            d["reserved"] = dict(self.reserved)
        return d

    def validate(self) -> tuple[list[CartridgeValidationError], list[CartridgeValidationWarning]]:
        errors: list[CartridgeValidationError] = []
        warnings: list[CartridgeValidationWarning] = []
        return errors, warnings


# ---------------------------------------------------------------------------
# Register modules
# ---------------------------------------------------------------------------

register_module(IdentityModule)
register_module(CharacterModule)
register_module(PreferenceModule)
register_module(BehaviorModule)
register_module(CommunicationModule)


# ---------------------------------------------------------------------------
# PersonaCartridge — composition of modules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PersonaCartridge:
    manifest: CartridgeManifest
    identity: IdentityModule
    character: CharacterModule
    preferences: PreferenceModule
    behavior: BehaviorModule
    communication: CommunicationModule
    state_modulations: dict[str, PersonaStateModulation] = field(default_factory=dict)
    extensions: dict[str, dict] = field(default_factory=dict)

    status: CartridgeStatus = CartridgeStatus.FORGED

    def to_dict(self) -> dict:
        d: dict = {
            "manifest": self.manifest.to_dict(),
            "identity": self.identity.to_dict(),
            "character": self.character.to_dict(),
            "preferences": self.preferences.to_dict(),
            "behavior": self.behavior.to_dict(),
            "communication": self.communication.to_dict(),
        }
        if self.state_modulations:
            d["state_modulations"] = {
                state_id: mod.to_dict()
                for state_id, mod in sorted(self.state_modulations.items())
            }
        d["extensions"] = dict(self.extensions)
        d["status"] = self.status.value
        return d

    @staticmethod
    def schema() -> dict:
        return {
            "name": SCHEMA_NAME,
            "version": SCHEMA_VERSION,
            "description": "Canonical CHIMERA Persona Cartridge",
        }


# ---------------------------------------------------------------------------
# Forge types
# ---------------------------------------------------------------------------

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
    warnings: list[CartridgeValidationWarning] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.success
