from __future__ import annotations


class InterviewError(Exception):
    """Base error for interview engine operations."""


class InvalidAnswerError(InterviewError):
    """Raised when an answer value fails per-question validation."""

    def __init__(self, question_id: str, reason: str) -> None:
        self.question_id = question_id
        self.reason = reason
        super().__init__(f"Invalid answer for '{question_id}': {reason}")


class QuestionNotAvailableError(InterviewError):
    """Raised when a question cannot be answered yet (dependencies unmet)."""

    def __init__(self, question_id: str, unmet: list[str]) -> None:
        self.question_id = question_id
        self.unmet = unmet
        deps = ", ".join(unmet)
        super().__init__(
            f"Question '{question_id}' is not yet available. "
            f"Unmet dependencies: {deps}"
        )


class InterviewStateError(InterviewError):
    """Raised when an operation is invalid for the current workflow state."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
