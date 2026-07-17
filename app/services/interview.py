import random
from datetime import datetime, timezone

from app.models.interview import InterviewTurn
from app.models.persona import PersonaDraft

QUESTION_POOL = [
    {
        "field": "name",
        "question": "What is this persona's name?",
        "reasoning": "A name anchors identity and sets expectations for tone and origin.",
        "on_answer": lambda draft, answer: setattr(draft, "name", answer),
    },
    {
        "field": "summary",
        "question": "How would you describe this persona in a few sentences?",
        "reasoning": "A summary captures the essence of who this character is at a glance.",
        "on_answer": lambda draft, answer: setattr(draft, "summary", answer),
    },
    {
        "field": "communication_style",
        "question": "How does this persona communicate? Formal, casual, poetic, direct?",
        "reasoning": "Communication style defines how the persona will express itself in every interaction.",
        "on_answer": lambda draft, answer: setattr(draft, "communication_style", answer),
    },
    {
        "field": "core_values",
        "question": "What core values drive this persona?",
        "reasoning": "Values are the foundation of consistent behavior and decision-making.",
        "on_answer": lambda draft, answer: draft.core_values.append(answer),
    },
    {
        "field": "motivations",
        "question": "What motivates this persona? What does it want most?",
        "reasoning": "Motivation reveals purpose and gives the persona direction.",
        "on_answer": lambda draft, answer: draft.motivations.append(answer),
    },
    {
        "field": "strengths",
        "question": "What are this persona's greatest strengths?",
        "reasoning": "Strengths define what the persona excels at and how it provides value.",
        "on_answer": lambda draft, answer: draft.strengths.append(answer),
    },
    {
        "field": "weaknesses",
        "question": "What are this persona's weaknesses or limitations?",
        "reasoning": "Weaknesses create depth, vulnerability, and realistic boundaries.",
        "on_answer": lambda draft, answer: draft.weaknesses.append(answer),
    },
    {
        "field": "goals",
        "question": "What goals does this persona pursue?",
        "reasoning": "Goals give the persona direction and something to work toward.",
        "on_answer": lambda draft, answer: draft.goals.append(answer),
    },
    {
        "field": "boundaries",
        "question": "What boundaries or rules should this persona follow?",
        "reasoning": "Boundaries ensure the persona operates safely and consistently.",
        "on_answer": lambda draft, answer: draft.boundaries.append(answer),
    },
]


def estimate_completeness(draft: PersonaDraft) -> float:
    checks = [
        bool(draft.name),
        bool(draft.summary),
        bool(draft.communication_style),
        len(draft.core_values) > 0,
        len(draft.motivations) > 0,
        len(draft.strengths) > 0,
        len(draft.weaknesses) > 0,
        len(draft.goals) > 0,
        len(draft.boundaries) > 0,
    ]
    return sum(checks) / len(checks) if checks else 0.0


def field_is_answered(draft: PersonaDraft, field: str) -> bool:
    if hasattr(draft, field):
        val = getattr(draft, field)
        if isinstance(val, list):
            return len(val) > 0
        return bool(val)
    return False


def find_unknowns(draft: PersonaDraft) -> list[str]:
    fields = [
        "name",
        "summary",
        "communication_style",
        "core_values",
        "motivations",
        "strengths",
        "weaknesses",
        "goals",
        "boundaries",
    ]
    return [f for f in fields if not field_is_answered(draft, f)]


def next_question(draft: PersonaDraft) -> dict | None:
    unknowns = find_unknowns(draft)
    if not unknowns:
        return None
    field = random.choice(unknowns)
    for q in QUESTION_POOL:
        if q["field"] == field:
            return q
    return None


def apply_answer(draft: PersonaDraft, question: dict, answer: str) -> InterviewTurn:
    question["on_answer"](draft, answer)
    draft.unknowns = find_unknowns(draft)
    draft.completeness = estimate_completeness(draft)
    return InterviewTurn(
        question=question["question"],
        answer=answer,
        reasoning=question["reasoning"],
        hypothesis=f"Based on the answer, this persona values {answer[:50].lower()}.",
        clarification=f"To clarify: does this mean {answer[:60].lower()} is central to who they are?",
        timestamp=datetime.now(timezone.utc),
    )
