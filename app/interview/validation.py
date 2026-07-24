from __future__ import annotations

import re
from typing import Any

from app.interview.exceptions import InvalidAnswerError
from app.interview.models import InterviewQuestion


# ---------------------------------------------------------------------------
# Per-answer validation
# ---------------------------------------------------------------------------

class AnswerValidator:
    """Immediate per-answer validation for a single question."""

    VALIDATORS: dict[str, callable] = {}

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    @staticmethod
    def validate(
        question: InterviewQuestion,
        value: Any,
    ) -> None:
        """Validate a single answer value against the question's rules.

        Raises InvalidAnswerError on first violation.
        """
        if value is None and not question.required:
            return

        _check_type(question, value)

        for rule in question.validation_rules:
            rule_type = rule.get("type", "")
            if rule_type == "required":
                _check_required(question, value)
            elif rule_type == "min_length":
                _check_min_length(question, value, rule.get("value", 0))
            elif rule_type == "identifier":
                _check_identifier(question, value)

    @staticmethod
    def normalize(question: InterviewQuestion, value: Any) -> Any:
        """Normalize a value for the given question's answer_type."""
        if value is None:
            return value
        if question.answer_type == "str":
            return value.strip() if isinstance(value, str) else value
        if question.answer_type == "str_list":
            if not isinstance(value, list):
                return value
            stripped = [v.strip() for v in value if isinstance(v, str) and v.strip()]
            seen: set[str] = set()
            result: list[str] = []
            for item in stripped:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
            return result
        if question.answer_type == "dict":
            if not isinstance(value, dict):
                return value
            cleaned: dict[str, Any] = {}
            for k, v in value.items():
                kk = k.strip() if isinstance(k, str) else k
                if isinstance(v, str):
                    vv = v.strip()
                else:
                    vv = v
                cleaned[kk] = vv
            return cleaned
        return value


def _check_type(question: InterviewQuestion, value: Any) -> None:
    if question.answer_type == "str":
        if not isinstance(value, str):
            raise InvalidAnswerError(
                question.identifier,
                f"Expected str, got {type(value).__name__}",
            )
    elif question.answer_type == "str_list":
        if not isinstance(value, list):
            raise InvalidAnswerError(
                question.identifier,
                f"Expected list, got {type(value).__name__}",
            )
        for i, item in enumerate(value):
            if not isinstance(item, str):
                raise InvalidAnswerError(
                    question.identifier,
                    f"Expected str at index {i}, got {type(item).__name__}",
                )
    elif question.answer_type == "dict":
        if not isinstance(value, dict):
            raise InvalidAnswerError(
                question.identifier,
                f"Expected dict, got {type(value).__name__}",
            )


def _check_required(question: InterviewQuestion, value: Any) -> None:
    if not question.required:
        return
    if question.answer_type == "str" and not value.strip():
        raise InvalidAnswerError(
            question.identifier,
            "Value must not be empty",
        )
    if question.answer_type == "str_list" and not value:
        raise InvalidAnswerError(
            question.identifier,
            "Must provide at least one item",
        )
    if question.answer_type == "dict" and not value:
        raise InvalidAnswerError(
            question.identifier,
            "Must provide at least one entry",
        )


def _check_min_length(question: InterviewQuestion, value: Any, min_len: int) -> None:
    if question.answer_type == "str" and len(value.strip()) < min_len:
        raise InvalidAnswerError(
            question.identifier,
            f"Value must be at least {min_len} character(s)",
        )


def _check_identifier(question: InterviewQuestion, value: Any) -> None:
    if not isinstance(value, str):
        return
    if not re.match(r"^[a-z][a-z0-9_-]*$", value.strip()):
        raise InvalidAnswerError(
            question.identifier,
            "Must begin with a letter and contain only a-z, 0-9, -, _",
        )


# ---------------------------------------------------------------------------
# Forge readiness
# ---------------------------------------------------------------------------

class ForgeReadinessChecker:
    """Determine whether a draft satisfies forge requirements.

    Does not invoke the forge.  Checks only whether required questions
    have been answered.
    """

    @staticmethod
    def check(
        questions: list[InterviewQuestion],
        answered: set[str],
    ) -> list[str]:
        """Return a list of issues preventing forge readiness.

        Returns an empty list when the draft is ready to forge.
        """
        issues: list[str] = []
        for q in questions:
            if q.required and q.identifier not in answered:
                issues.append(
                    f"Required question '{q.identifier}' not answered"
                )
        return issues
