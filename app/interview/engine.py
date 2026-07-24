from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.interview.exceptions import (
    InterviewError,
    InterviewStateError,
    InvalidAnswerError,
    QuestionNotAvailableError,
)
from app.interview.models import (
    InterviewAnswer,
    InterviewProgress,
    InterviewQuestion,
    InterviewState,
)
from app.interview.questions import (
    QuestionRegistry,
    question_field_map,
    question_registry as _default_registry,
    section_order,
    sections,
)
from app.interview.validation import AnswerValidator, ForgeReadinessChecker
from app.models.cartridge import PersonaDraft


# ---------------------------------------------------------------------------
# InterviewSession — owns the draft, answers, and workflow state
# ---------------------------------------------------------------------------

@dataclass
class InterviewSession:
    """One interview session.

    The PersonaDraft is the single source of truth for authored values.
    InterviewAnswers are the audit trail; they are never the source of
    truth for authored content.
    """

    session_id: str
    draft: PersonaDraft
    answers: dict[str, InterviewAnswer]
    state: InterviewState
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    last_question_id: Optional[str]


# ---------------------------------------------------------------------------
# InterviewEngine — deterministic workflow orchestrator
# ---------------------------------------------------------------------------

class InterviewEngine:
    """Deterministic interview engine for incremental PersonaDraft authoring.

    Owns workflow only.  No AI, no prompt generation, no conversational
    behaviour.  The engine accepts answers, validates them, and updates
    the PersonaDraft.  It is the canonical authoring workflow for every
    future CHIMERA interface.
    """

    def __init__(
        self,
        registry: QuestionRegistry | None = None,
    ) -> None:
        self._registry = registry or _default_registry
        self._validator = AnswerValidator()
        self._readiness = ForgeReadinessChecker()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        template: PersonaDraft | None = None,
    ) -> InterviewSession:
        """Create a new interview session, optionally seeded from a template.

        The template draft is deep-copied so the original is never mutated.
        """
        if template is not None:
            draft = copy.deepcopy(template)
        else:
            draft = PersonaDraft()

        now = datetime.now(timezone.utc)
        return InterviewSession(
            session_id=str(uuid.uuid4()),
            draft=draft,
            answers={},
            state=InterviewState.CREATED,
            created_at=now,
            updated_at=now,
            completed_at=None,
            last_question_id=None,
        )

    # ------------------------------------------------------------------
    # Question navigation
    # ------------------------------------------------------------------

    def get_available_questions(
        self,
        session: InterviewSession,
    ) -> list[InterviewQuestion]:
        """Return all questions whose dependencies are satisfied.

        A dependency is satisfied when the dependent question has an
        answer recorded in the session.
        """
        answered: set[str] = set(session.answers)
        available: list[InterviewQuestion] = []
        for q in self._registry.questions:
            if all(dep in answered for dep in q.dependencies):
                available.append(q)
        return available

    def get_next_question(
        self,
        session: InterviewSession,
    ) -> InterviewQuestion | None:
        """Return the next unanswered available question, or None.

        Ordering:
          1. Section order (identity → character → communication → preferences → behaviour)
          2. Position within the section definition
        """
        answered: set[str] = set(session.answers)
        available = self.get_available_questions(session)
        unanswered = [q for q in available if q.identifier not in answered]
        if not unanswered:
            return None

        # Build ordering key: (section_index, question_index)
        section_index = {s: i for i, s in enumerate(section_order)}
        all_questions = self._registry.questions
        q_index = {q.identifier: i for i, q in enumerate(all_questions)}

        def sort_key(q: InterviewQuestion) -> tuple[int, int]:
            return (
                section_index.get(q.section, 999),
                q_index.get(q.identifier, 999),
            )

        unanswered.sort(key=sort_key)
        return unanswered[0]

    # ------------------------------------------------------------------
    # Answer submission
    # ------------------------------------------------------------------

    def submit_answer(
        self,
        session: InterviewSession,
        question_id: str,
        value: Any,
    ) -> InterviewAnswer:
        """Validate, normalize, record an answer, and update the draft.

        Raises QuestionNotAvailableError if dependencies are unmet.
        Raises InvalidAnswerError if the value fails validation.
        """
        question = self._registry.get(question_id)
        self._check_available(session, question)
        self._check_state(session)

        normalized = self._validator.normalize(question, value)
        self._validator.validate(question, normalized)

        answer = InterviewAnswer(
            question_id=question_id,
            value=value,
            normalized_value=normalized,
        )
        session.answers[question_id] = answer

        _update_draft(session.draft, question_id, normalized)
        session.updated_at = datetime.now(timezone.utc)
        session.last_question_id = question_id

        if session.state == InterviewState.CREATED:
            session.state = InterviewState.IN_PROGRESS

        self._auto_transition(session)

        return answer

    def skip_question(
        self,
        session: InterviewSession,
        question_id: str,
    ) -> None:
        """Skip a non-required question, applying its default value.

        Raises InterviewError if the question is required.
        """
        question = self._registry.get(question_id)
        self._check_available(session, question)
        self._check_state(session)

        if question.required:
            raise InterviewError(
                f"Cannot skip required question '{question_id}'"
            )

        default = question.default_value
        normalized = self._validator.normalize(question, default) if default is not None else default
        answer = InterviewAnswer(
            question_id=question_id,
            value=None,
            normalized_value=normalized,
        )
        session.answers[question_id] = answer
        if normalized is not None:
            _update_draft(session.draft, question_id, normalized)

        session.updated_at = datetime.now(timezone.utc)
        session.last_question_id = question_id

        if session.state == InterviewState.CREATED:
            session.state = InterviewState.IN_PROGRESS

        self._auto_transition(session)

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def get_progress(self, session: InterviewSession) -> InterviewProgress:
        """Compute deterministic progress for the session."""
        all_questions = self._registry.questions
        answered_ids: set[str] = set(session.answers)
        total = len(all_questions)
        answered_count = len(answered_ids)
        remaining = total - answered_count
        pct = (answered_count / total * 100) if total > 0 else 0.0

        completed_sections: list[str] = []
        remaining_sections: list[str] = []
        section_progress: dict[str, float] = {}

        for sec in sections:
            sec_qs = [q for q in all_questions if q.section == sec.identifier]
            sec_total = len(sec_qs)
            sec_answered = sum(1 for q in sec_qs if q.identifier in answered_ids)
            sec_pct = (sec_answered / sec_total * 100) if sec_total > 0 else 100.0
            section_progress[sec.identifier] = sec_pct
            if sec_total > 0 and sec_answered >= sec_total:
                completed_sections.append(sec.identifier)
            elif sec_answered > 0 or sec_total == 0:
                pass  # partially complete — neither completed nor remaining
            else:
                remaining_sections.append(sec.identifier)

        # A section is "remaining" if none of its questions are answered
        # (recalculated above to avoid listing partially-complete sections)
        remaining_sections = [
            sec.identifier for sec in sections
            if section_progress.get(sec.identifier, 0) == 0.0
        ]

        forge_issues = self._readiness.check(all_questions, answered_ids)
        all_required = len(forge_issues) == 0

        # Auto-transition to ready-to-forge when all required questions answered
        if all_required and session.state == InterviewState.IN_PROGRESS:
            session.state = InterviewState.READY_TO_FORGE
            session.updated_at = datetime.now(timezone.utc)

        return InterviewProgress(
            total_questions=total,
            answered_questions=answered_count,
            remaining_questions=remaining,
            percentage=round(pct, 1),
            completed_sections=tuple(completed_sections),
            remaining_sections=tuple(remaining_sections),
            section_progress=section_progress,
            all_required_answered=all_required,
            forge_readiness_issues=tuple(forge_issues),
        )

    # ------------------------------------------------------------------
    # Forge readiness
    # ------------------------------------------------------------------

    def is_ready_to_forge(self, session: InterviewSession) -> bool:
        """Return True when all required questions have been answered."""
        all_qs = self._registry.questions
        answered: set[str] = set(session.answers)
        issues = self._readiness.check(all_qs, answered)
        return len(issues) == 0

    # ------------------------------------------------------------------
    # Workflow transitions
    # ------------------------------------------------------------------

    def complete(self, session: InterviewSession) -> None:
        """Mark the session as completed."""
        if session.state in (InterviewState.CANCELLED,):
            raise InterviewStateError(
                f"Cannot complete a {session.state.value} session"
            )
        session.state = InterviewState.COMPLETED
        session.completed_at = datetime.now(timezone.utc)
        session.updated_at = datetime.now(timezone.utc)

    def cancel(self, session: InterviewSession) -> None:
        """Cancel the session."""
        if session.state in (InterviewState.COMPLETED, InterviewState.CANCELLED):
            raise InterviewStateError(
                f"Cannot cancel a {session.state.value} session"
            )
        session.state = InterviewState.CANCELLED
        session.updated_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize_session(self, session: InterviewSession) -> dict:
        """Serialize the full session to a plain dict.

        Includes draft, answers, workflow state, timestamps, and progress.
        Future persistence requires no additional interview logic.
        """
        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "last_question_id": session.last_question_id,
            "draft": {
                "name": session.draft.name,
                "identifier": session.draft.identifier,
                "summary": session.draft.summary,
                "description": session.draft.description,
                "aliases": list(session.draft.aliases),
                "core_values": list(session.draft.core_values),
                "motivations": list(session.draft.motivations),
                "strengths": list(session.draft.strengths),
                "limitations": list(session.draft.limitations),
                "goals": list(session.draft.goals),
                "boundaries": list(session.draft.boundaries),
                "communication_style": session.draft.communication_style,
                "tone": list(session.draft.tone),
                "vocabulary_preferences": list(session.draft.vocabulary_preferences),
                "response_tendencies": list(session.draft.response_tendencies),
                "formatting_preferences": list(session.draft.formatting_preferences),
                "preferences": dict(session.draft.preferences),
                "behavior_rules": list(session.draft.behavior_rules),
            },
            "answers": {
                qid: {
                    "question_id": a.question_id,
                    "value": a.value,
                    "normalized_value": a.normalized_value,
                    "timestamp": a.timestamp.isoformat(),
                }
                for qid, a in session.answers.items()
            },
        }

    def deserialize_session(self, data: dict) -> InterviewSession:
        """Restore a session from a serialized dict.

        Returns a fully functional InterviewSession that can be resumed.
        """
        draft = PersonaDraft(
            name=data["draft"]["name"],
            identifier=data["draft"]["identifier"],
            summary=data["draft"]["summary"],
            description=data["draft"].get("description", ""),
            aliases=list(data["draft"].get("aliases", [])),
            core_values=list(data["draft"].get("core_values", [])),
            motivations=list(data["draft"].get("motivations", [])),
            strengths=list(data["draft"].get("strengths", [])),
            limitations=list(data["draft"].get("limitations", [])),
            goals=list(data["draft"].get("goals", [])),
            boundaries=list(data["draft"].get("boundaries", [])),
            communication_style=data["draft"].get("communication_style", ""),
            tone=list(data["draft"].get("tone", [])),
            vocabulary_preferences=list(data["draft"].get("vocabulary_preferences", [])),
            response_tendencies=list(data["draft"].get("response_tendencies", [])),
            formatting_preferences=list(data["draft"].get("formatting_preferences", [])),
            preferences=dict(data["draft"].get("preferences", {})),
            behavior_rules=list(data["draft"].get("behavior_rules", [])),
        )

        answers: dict[str, InterviewAnswer] = {}
        for qid, adata in data.get("answers", {}).items():
            ts = datetime.fromisoformat(adata["timestamp"]) if "timestamp" in adata else datetime.now(timezone.utc)
            answers[qid] = InterviewAnswer(
                question_id=adata["question_id"],
                value=adata["value"],
                normalized_value=adata.get("normalized_value", adata["value"]),
                timestamp=ts,
            )

        state = InterviewState(data["state"])

        return InterviewSession(
            session_id=data["session_id"],
            draft=draft,
            answers=answers,
            state=state,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            last_question_id=data.get("last_question_id"),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_available(
        self,
        session: InterviewSession,
        question: InterviewQuestion,
    ) -> None:
        answered: set[str] = set(session.answers)
        unmet = [dep for dep in question.dependencies if dep not in answered]
        if unmet:
            raise QuestionNotAvailableError(question.identifier, unmet)

    def _check_state(self, session: InterviewSession) -> None:
        if session.state in (
            InterviewState.COMPLETED,
            InterviewState.CANCELLED,
        ):
            raise InterviewStateError(
                f"Cannot submit answers in {session.state.value} state"
            )

    def _auto_transition(self, session: InterviewSession) -> None:
        """Transition to READY_TO_FORGE when all required questions answered."""
        if session.state != InterviewState.IN_PROGRESS:
            return
        all_qs = self._registry.questions
        answered: set[str] = set(session.answers)
        issues = self._readiness.check(all_qs, answered)
        if len(issues) == 0:
            session.state = InterviewState.READY_TO_FORGE
            session.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Draft update helper
# ---------------------------------------------------------------------------

def _update_draft(draft: PersonaDraft, question_id: str, value: Any) -> None:
    """Apply a normalized answer value to the corresponding draft field."""
    field = question_field_map.get(question_id)
    if field is None:
        raise InterviewError(f"No draft field mapped for question '{question_id}'")
    setattr(draft, field, value)
