from app.models.persona import PersonaDraft
from app.models.interview import InterviewSession


def estimate_completeness(draft: PersonaDraft) -> float:
    fields = [
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
    return sum(fields) / len(fields) if fields else 0.0


def build_draft_from_session(session: InterviewSession) -> PersonaDraft:
    draft = PersonaDraft()
    draft.completeness = estimate_completeness(draft)
    return draft
