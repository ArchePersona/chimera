from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class PersonaCartridge:
    name: str
    summary: str
    communication_style: str
    core_values: list[str]
    motivations: list[str]
    strengths: list[str]
    weaknesses: list[str]
    goals: list[str]
    boundaries: list[str]
    preferences: dict[str, str]
    behavior_rules: list[str] = field(default_factory=list)
    version: str = "1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
