from __future__ import annotations

from app.interview.models import InterviewQuestion, InterviewSection


# ---------------------------------------------------------------------------
# Question definitions
# ---------------------------------------------------------------------------

def _q(
    identifier: str,
    section: str,
    title: str,
    description: str,
    answer_type: str,
    required: bool = True,
    default_value: object = None,
    validation_rules: tuple[dict, ...] = (),
    dependencies: tuple[str, ...] = (),
) -> InterviewQuestion:
    return InterviewQuestion(
        identifier=identifier,
        section=section,
        title=title,
        description=description,
        answer_type=answer_type,
        required=required,
        default_value=default_value,
        validation_rules=validation_rules,
        dependencies=dependencies,
    )


# Identity section: 5 questions
IDENTITY_NAME = _q(
    "identity_name", "identity",
    "Display Name",
    "What is the persona's display name?",
    "str",
    validation_rules=({"type": "required"}, {"type": "min_length", "value": 1}),
)
IDENTITY_IDENTIFIER = _q(
    "identity_identifier", "identity",
    "Identifier",
    "A unique identifier for the persona (lowercase, a-z, 0-9, -, _).",
    "str",
    validation_rules=({"type": "required"}, {"type": "identifier"}),
    dependencies=("identity_name",),
)
IDENTITY_SUMMARY = _q(
    "identity_summary", "identity",
    "Summary",
    "A one-sentence summary of the persona.",
    "str",
    validation_rules=({"type": "required"},),
    dependencies=("identity_name",),
)
IDENTITY_DESCRIPTION = _q(
    "identity_description", "identity",
    "Description",
    "A longer optional description of the persona.",
    "str",
    required=False,
    default_value="",
    dependencies=("identity_name",),
)
IDENTITY_ALIASES = _q(
    "identity_aliases", "identity",
    "Aliases",
    "Alternative names for the persona (one per line).",
    "str_list",
    required=False,
    default_value=[],
    dependencies=("identity_name",),
)

# Character section: 6 questions
CHARACTER_CORE_VALUES = _q(
    "character_core_values", "character",
    "Core Values",
    "What core values define this persona? (one per line)",
    "str_list",
    validation_rules=({"type": "required"},),
    dependencies=("identity_name", "identity_identifier", "identity_summary"),
)
CHARACTER_MOTIVATIONS = _q(
    "character_motivations", "character",
    "Motivations",
    "What motivates this persona? (one per line)",
    "str_list",
    validation_rules=({"type": "required"},),
    dependencies=("identity_name", "identity_identifier", "identity_summary"),
)
CHARACTER_STRENGTHS = _q(
    "character_strengths", "character",
    "Strengths",
    "What are the persona's strengths? (one per line)",
    "str_list",
    validation_rules=({"type": "required"},),
    dependencies=("identity_name", "identity_identifier", "identity_summary"),
)
CHARACTER_LIMITATIONS = _q(
    "character_limitations", "character",
    "Limitations",
    "What are the persona's limitations? (one per line)",
    "str_list",
    validation_rules=({"type": "required"},),
    dependencies=("identity_name", "identity_identifier", "identity_summary"),
)
CHARACTER_GOALS = _q(
    "character_goals", "character",
    "Goals",
    "What goals does the persona have? (one per line)",
    "str_list",
    validation_rules=({"type": "required"},),
    dependencies=("identity_name", "identity_identifier", "identity_summary"),
)
CHARACTER_BOUNDARIES = _q(
    "character_boundaries", "character",
    "Boundaries",
    "What boundaries does the persona observe? (one per line)",
    "str_list",
    validation_rules=({"type": "required"},),
    dependencies=("identity_name", "identity_identifier", "identity_summary"),
)

# Communication section: 6 questions
COMMUNICATION_STYLE = _q(
    "communication_style", "communication",
    "Communication Style",
    "Describe the persona's communication style (e.g. warm, formal).",
    "str",
    required=False,
    default_value="",
    dependencies=("character_core_values",),
)
COMMUNICATION_TONE = _q(
    "communication_tone", "communication",
    "Tone",
    "What tone should the persona use? (one per line)",
    "str_list",
    required=False,
    default_value=[],
    dependencies=("character_core_values",),
)
COMMUNICATION_VOCABULARY = _q(
    "communication_vocabulary", "communication",
    "Vocabulary Preferences",
    "Preferred vocabulary or phrasing patterns. (one per line)",
    "str_list",
    required=False,
    default_value=[],
    dependencies=("character_core_values",),
)
COMMUNICATION_RESPONSE = _q(
    "communication_response", "communication",
    "Response Tendencies",
    "How tends to respond? (e.g. concise, thorough) (one per line)",
    "str_list",
    required=False,
    default_value=[],
    dependencies=("character_core_values",),
)
COMMUNICATION_FORMATTING = _q(
    "communication_formatting", "communication",
    "Formatting Preferences",
    "Preferred formatting (e.g. Markdown, plain text). (one per line)",
    "str_list",
    required=False,
    default_value=[],
    dependencies=("character_core_values",),
)

# Preferences section: 1 question
PREFERENCES = _q(
    "preferences", "preferences",
    "Preferences",
    "Key-value preferences (e.g. formality: casual, verbosity: medium).",
    "dict",
    required=False,
    default_value={},
    dependencies=("identity_name",),
)

# Behavior section: 1 question
BEHAVIOR_RULES = _q(
    "behavior_rules", "behavior",
    "Behavior Rules",
    "Rules the persona should follow (one per line).",
    "str_list",
    required=False,
    default_value=[],
    dependencies=("identity_name",),
)


# ---------------------------------------------------------------------------
# Question order within each section
# ---------------------------------------------------------------------------

_QUESTIONS: list[InterviewQuestion] = [
    # Identity (section order = 0)
    IDENTITY_NAME,
    IDENTITY_IDENTIFIER,
    IDENTITY_SUMMARY,
    IDENTITY_DESCRIPTION,
    IDENTITY_ALIASES,
    # Character (section order = 1)
    CHARACTER_CORE_VALUES,
    CHARACTER_MOTIVATIONS,
    CHARACTER_STRENGTHS,
    CHARACTER_LIMITATIONS,
    CHARACTER_GOALS,
    CHARACTER_BOUNDARIES,
    # Communication (section order = 2)
    COMMUNICATION_STYLE,
    COMMUNICATION_TONE,
    COMMUNICATION_VOCABULARY,
    COMMUNICATION_RESPONSE,
    COMMUNICATION_FORMATTING,
    # Preferences (section order = 3)
    PREFERENCES,
    # Behavior (section order = 4)
    BEHAVIOR_RULES,
]

# ---------------------------------------------------------------------------
# Section definitions
# ---------------------------------------------------------------------------

_SECTIONS: list[InterviewSection] = [
    InterviewSection(
        identifier="identity",
        title="Identity",
        description="Who is this persona?  Define the persona's name, identifier, and summary.",
        question_ids=(
            "identity_name",
            "identity_identifier",
            "identity_summary",
            "identity_description",
            "identity_aliases",
        ),
    ),
    InterviewSection(
        identifier="character",
        title="Character",
        description="What defines the persona's personality and boundaries?",
        question_ids=(
            "character_core_values",
            "character_motivations",
            "character_strengths",
            "character_limitations",
            "character_goals",
            "character_boundaries",
        ),
    ),
    InterviewSection(
        identifier="communication",
        title="Communication",
        description="How does the persona communicate?",
        question_ids=(
            "communication_style",
            "communication_tone",
            "communication_vocabulary",
            "communication_response",
            "communication_formatting",
        ),
    ),
    InterviewSection(
        identifier="preferences",
        title="Preferences",
        description="What preferences does the persona have?",
        question_ids=(
            "preferences",
        ),
    ),
    InterviewSection(
        identifier="behavior",
        title="Behavior",
        description="What rules govern the persona's behavior?",
        question_ids=(
            "behavior_rules",
        ),
    ),
]

# ---------------------------------------------------------------------------
# Question → draft field mapping
# ---------------------------------------------------------------------------

QUESTION_FIELD_MAP: dict[str, str] = {
    "identity_name": "name",
    "identity_identifier": "identifier",
    "identity_summary": "summary",
    "identity_description": "description",
    "identity_aliases": "aliases",
    "character_core_values": "core_values",
    "character_motivations": "motivations",
    "character_strengths": "strengths",
    "character_limitations": "limitations",
    "character_goals": "goals",
    "character_boundaries": "boundaries",
    "communication_style": "communication_style",
    "communication_tone": "tone",
    "communication_vocabulary": "vocabulary_preferences",
    "communication_response": "response_tendencies",
    "communication_formatting": "formatting_preferences",
    "preferences": "preferences",
    "behavior_rules": "behavior_rules",
}

# ---------------------------------------------------------------------------
# Section order — determines which section is "next"
# ---------------------------------------------------------------------------

_SECTION_ORDER: tuple[str, ...] = (
    "identity",
    "character",
    "communication",
    "preferences",
    "behavior",
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class QuestionRegistry:
    """Holds all known questions and provides lookup by identifier."""

    def __init__(self, questions: list[InterviewQuestion]) -> None:
        self._questions = list(questions)
        self._by_id: dict[str, InterviewQuestion] = {
            q.identifier: q for q in questions
        }

    @property
    def questions(self) -> list[InterviewQuestion]:
        return list(self._questions)

    def get(self, identifier: str) -> InterviewQuestion:
        if identifier not in self._by_id:
            raise KeyError(f"Unknown question: '{identifier}'")
        return self._by_id[identifier]

    def by_section(self, section: str) -> list[InterviewQuestion]:
        return [q for q in self._questions if q.section == section]

    def section_questions(self, section_id: str) -> list[InterviewQuestion]:
        return [q for q in self._questions if q.section == section_id]


# ---------------------------------------------------------------------------
# Default registry instance
# ---------------------------------------------------------------------------

question_registry = QuestionRegistry(_QUESTIONS)
sections = list(_SECTIONS)
section_order = _SECTION_ORDER
question_field_map = dict(QUESTION_FIELD_MAP)
