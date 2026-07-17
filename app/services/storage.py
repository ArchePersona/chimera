from datetime import datetime, timezone
from typing import Optional

from app.models.interview import InterviewSession, InterviewTurn
from app.models.persona import PersonaDraft

_sessions: dict[str, InterviewSession] = {}
_drafts: dict[str, PersonaDraft] = {}


def create_session(persona_name: str = "") -> InterviewSession:
    import uuid

    session = InterviewSession(
        id=str(uuid.uuid4()),
        persona_name=persona_name,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _sessions[session.id] = session
    _drafts[session.id] = PersonaDraft(name=persona_name)
    return session


def get_session(session_id: str) -> Optional[InterviewSession]:
    return _sessions.get(session_id)


def get_draft(session_id: str) -> Optional[PersonaDraft]:
    return _drafts.get(session_id)


def add_turn(session_id: str, turn: InterviewTurn) -> Optional[InterviewSession]:
    session = _sessions.get(session_id)
    if not session:
        return None
    session.turns.append(turn)
    session.updated_at = turn.timestamp
    return session


def update_draft(session_id: str, draft: PersonaDraft) -> None:
    _drafts[session_id] = draft
