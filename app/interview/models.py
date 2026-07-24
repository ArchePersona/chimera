from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# InterviewState — workflow state, never affects persona behaviour
# ---------------------------------------------------------------------------

class InterviewState(Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    READY_TO_FORGE = "ready_to_forge"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# InterviewQuestion — one deterministic authoring prompt
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InterviewQuestion:
    """One deterministic authoring prompt.

    Contains no UI code.  All presentation is the consumer's responsibility.
    """

    identifier: str
    section: str
    title: str
    description: str
    answer_type: str  # "str", "str_list", "dict"
    required: bool = True
    default_value: Any = None
    validation_rules: tuple[dict, ...] = ()
    dependencies: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# InterviewAnswer — one validated answer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InterviewAnswer:
    question_id: str
    value: Any
    normalized_value: Any
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# InterviewSection — one authoring domain
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InterviewSection:
    identifier: str
    title: str
    description: str
    question_ids: tuple[str, ...]


# ---------------------------------------------------------------------------
# InterviewProgress — deterministic reporting
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InterviewProgress:
    total_questions: int
    answered_questions: int
    remaining_questions: int
    percentage: float
    completed_sections: tuple[str, ...]
    remaining_sections: tuple[str, ...]
    section_progress: dict[str, float]
    all_required_answered: bool
    forge_readiness_issues: tuple[str, ...]
