from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class InterviewTurn:
    question: str
    answer: str
    reasoning: str
    hypothesis: str
    clarification: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InterviewSession:
    id: str
    persona_name: str = ""
    turns: list[InterviewTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    draft: Optional[dict] = None
