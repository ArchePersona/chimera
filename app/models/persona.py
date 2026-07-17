from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Persona:
    name: str
    summary: str
    communication_style: str
    core_values: list[str] = field(default_factory=list)
    motivations: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    preferences: dict[str, str] = field(default_factory=dict)


@dataclass
class PersonaDraft:
    name: str = ""
    summary: str = ""
    communication_style: str = ""
    core_values: list[str] = field(default_factory=list)
    motivations: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)
    preferences: dict[str, str] = field(default_factory=dict)
    unknowns: list[str] = field(default_factory=list)
    completeness: float = 0.0
