from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.integrations.archengine import CartridgeDescriptorPayload
from app.interview.engine import InterviewEngine, InterviewSession
from app.interview.exceptions import InterviewError, InterviewStateError
from app.interview.models import (
    InterviewAnswer,
    InterviewProgress,
    InterviewQuestion,
    InterviewState,
)
from app.interview.questions import question_registry as _default_registry
from app.models.cartridge import (
    ForgeResult,
    PersonaCartridge,
    PersonaDraft,
)
from app.services.archengine_export import (
    export_archengine_payload,
    export_archengine_payload_json,
)
from app.services.cartridge_service import (
    CartridgeNotFoundError,
    CartridgeService,
)

try:
    from app.repositories.session_repository import SessionRepository
except ImportError:
    SessionRepository = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Workflow-specific errors
# ---------------------------------------------------------------------------

class WorkflowError(Exception):
    """Base error for authoring workflow operations."""


class SessionNotFound(WorkflowError):
    """Raised when an interview session does not exist."""


class InterviewIncomplete(WorkflowError):
    """Raised when the interview is not yet ready to forge."""


class CartridgeCreationFailed(WorkflowError):
    """Raised when cartridge forging or registration fails."""

    def __init__(self, message: str, detail: str = "") -> None:
        self.detail = detail
        super().__init__(message)


class WorkflowStateError(WorkflowError):
    """Raised when an operation is invalid for the current workflow state."""


# ---------------------------------------------------------------------------
# Readiness result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    issues: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# AuthoringWorkflow — single canonical pipeline from interview to cartridge
# ---------------------------------------------------------------------------

class AuthoringWorkflow:
    """Canonical application workflow from interview session to managed cartridge.

    Owns orchestration only.  Delegates to InterviewEngine, CartridgeService,
    and the export service.  Contains no interview logic, validation rules,
    forge logic, lifecycle logic, or export logic.

    Every public method requires an ``owner_user_id`` to enforce
    user isolation.  When a SessionRepository is provided, sessions
    are persisted to disk.  Otherwise, an in-memory dict (keyed by
    owner_user_id + session_id) is used.
    """

    def __init__(
        self,
        interview_engine: Optional[InterviewEngine] = None,
        cartridge_service: Optional[CartridgeService] = None,
        session_repo: "SessionRepository | None" = None,
    ) -> None:
        self._engine = interview_engine or InterviewEngine()
        self._cartridge_service = cartridge_service or CartridgeService()
        self._session_repo = session_repo
        # In-memory fallback (used when no repo is provided)
        self._sessions: dict[tuple[str, str], InterviewSession] = {}

    @property
    def cartridge_service(self) -> CartridgeService:
        """Expose the cartridge service for inspector and management routes."""
        return self._cartridge_service

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        owner_user_id: str,
        template: Optional[PersonaDraft] = None,
    ) -> InterviewSession:
        """Create a new interview session, optionally seeded from a template."""
        session = self._engine.create_session(template=template)
        if self._session_repo is not None:
            self._session_repo.save(session, owner_user_id)
        else:
            self._sessions[(owner_user_id, session.session_id)] = session
        return session

    def load_session(self, session_id: str, owner_user_id: str) -> InterviewSession:
        """Retrieve an existing interview session."""
        return self._get_session(session_id, owner_user_id)

    def complete_session(self, session_id: str, owner_user_id: str) -> None:
        """Mark the interview session as completed."""
        session = self._get_session(session_id, owner_user_id)
        self._engine.complete(session)
        self._persist_session(session, owner_user_id)

    def cancel_session(self, session_id: str, owner_user_id: str) -> None:
        """Cancel the interview session."""
        session = self._get_session(session_id, owner_user_id)
        self._engine.cancel(session)
        self._persist_session(session, owner_user_id)

    # ------------------------------------------------------------------
    # Interview operations
    # ------------------------------------------------------------------

    def answer_question(
        self,
        session_id: str,
        question_id: str,
        value: Any,
        owner_user_id: str,
    ) -> InterviewAnswer:
        """Submit an answer, validate, and update the session draft."""
        session = self._get_session(session_id, owner_user_id)
        result = self._engine.submit_answer(session, question_id, value)
        self._persist_session(session, owner_user_id)
        return result

    def skip_question(
        self, session_id: str, question_id: str, owner_user_id: str
    ) -> None:
        """Skip a non-required question."""
        session = self._get_session(session_id, owner_user_id)
        self._engine.skip_question(session, question_id)
        self._persist_session(session, owner_user_id)

    def current_question(
        self, session_id: str, owner_user_id: str
    ) -> Optional[InterviewQuestion]:
        """Return the next unanswered available question, or None."""
        session = self._get_session(session_id, owner_user_id)
        return self._engine.get_next_question(session)

    def available_questions(
        self, session_id: str, owner_user_id: str
    ) -> list[InterviewQuestion]:
        """Return all questions whose dependencies are satisfied."""
        session = self._get_session(session_id, owner_user_id)
        return self._engine.get_available_questions(session)

    # ------------------------------------------------------------------
    # Progress and readiness
    # ------------------------------------------------------------------

    def progress(self, session_id: str, owner_user_id: str) -> InterviewProgress:
        """Compute deterministic progress for the session."""
        session = self._get_session(session_id, owner_user_id)
        return self._engine.get_progress(session)

    def readiness(self, session_id: str, owner_user_id: str) -> ReadinessResult:
        """Determine whether the session is ready to forge."""
        session = self._get_session(session_id, owner_user_id)
        prog = self._engine.get_progress(session)
        return ReadinessResult(
            ready=prog.all_required_answered,
            issues=prog.forge_readiness_issues,
        )

    # ------------------------------------------------------------------
    # Forge — creates and registers a cartridge through CartridgeService
    # ------------------------------------------------------------------

    def forge(self, session_id: str, owner_user_id: str) -> ForgeResult:
        """Forge a cartridge from the session draft and register it."""
        session = self._get_session(session_id, owner_user_id)

        if session.state in (InterviewState.COMPLETED, InterviewState.CANCELLED):
            raise WorkflowStateError(
                f"Cannot forge: session is in {session.state.value} state"
            )

        prog = self._engine.get_progress(session)
        if not prog.all_required_answered:
            raise InterviewIncomplete(
                f"Cannot forge session '{session_id}': "
                f"not all required questions are answered"
            )

        result = self._cartridge_service.create(
            session.draft,
            owner_user_id=owner_user_id,
            source_session_id=session_id,
        )

        if not result.success:
            detail = result.error.detail if result.error else ""
            raise CartridgeCreationFailed(
                result.error.message if result.error else "Forge failed",
                detail=detail,
            )

        return result

    # ------------------------------------------------------------------
    # Export — delegates to the existing export service
    # ------------------------------------------------------------------

    def export(self, session_id: str, owner_user_id: str) -> CartridgeDescriptorPayload:
        """Export the managed cartridge to an ARCHEngine payload."""
        cartridge = self._get_managed_cartridge(session_id, owner_user_id)
        return export_archengine_payload(cartridge)

    def export_json(self, session_id: str, owner_user_id: str) -> dict:
        """Export the managed cartridge as an ARCHEngine-compatible JSON dict."""
        cartridge = self._get_managed_cartridge(session_id, owner_user_id)
        return export_archengine_payload_json(cartridge)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize_session(self, session_id: str, owner_user_id: str) -> dict:
        """Serialize the session using the existing interview session format."""
        session = self._get_session(session_id, owner_user_id)
        return self._engine.serialize_session(session)

    def deserialize_session(self, data: dict, owner_user_id: str) -> InterviewSession:
        """Restore a session from serialized data and register it."""
        session = self._engine.deserialize_session(data)
        if self._session_repo is not None:
            self._session_repo.save(session, owner_user_id)
        else:
            self._sessions[(owner_user_id, session.session_id)] = session
        return session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(
        self, session_id: str, owner_user_id: str
    ) -> InterviewSession:
        if self._session_repo is not None:
            session = self._session_repo.load(session_id, owner_user_id)
            if session is None:
                raise SessionNotFound(
                    f"Interview session '{session_id}' not found"
                )
            return session
        key = (owner_user_id, session_id)
        if key not in self._sessions:
            raise SessionNotFound(
                f"Interview session '{session_id}' not found"
            )
        return self._sessions[key]

    def _persist_session(
        self, session: InterviewSession, owner_user_id: str
    ) -> None:
        if self._session_repo is not None:
            self._session_repo.save(session, owner_user_id)
        else:
            self._sessions[(owner_user_id, session.session_id)] = session

    def _get_managed_cartridge(
        self, session_id: str, owner_user_id: str
    ) -> PersonaCartridge:
        session = self._get_session(session_id, owner_user_id)
        identifier = session.draft.identifier
        if not identifier:
            raise WorkflowStateError(
                "Cannot export: session draft has no identifier"
            )
        try:
            return self._cartridge_service.get(identifier, owner_user_id)
        except CartridgeNotFoundError:
            raise WorkflowStateError(
                f"No cartridge registered for identifier '{identifier}'. "
                f"Call forge() first."
            )
