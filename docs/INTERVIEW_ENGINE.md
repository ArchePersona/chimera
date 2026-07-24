# Interview Engine

## Overview

The Interview Engine is CHIMERA's deterministic persona authoring workflow.

It owns **workflow**, not intelligence.  No AI, no prompt generation,
no conversational behaviour.  Every future interface — web app, CLI, API,
AI-assisted conversations — must build upon this engine rather than
implementing its own interview logic.

---

## Architecture

```
Template (optional)
        ↓
InterviewEngine
        ↓
InterviewSession
        ↓
PersonaDraft
        ↓
Validation (optional, external)
        ↓
CartridgeForge (external)
        ↓
PersonaCartridge
```

The engine never calls the forge automatically.

---

## Workflow states

```
Created → InProgress → ReadyToForge → Completed
                  ↘          ↙
                 Cancelled
```

| State           | Meaning                                  |
|-----------------|------------------------------------------|
| `CREATED`       | Session created, no answers yet           |
| `IN_PROGRESS`   | Answers are being collected               |
| `READY_TO_FORGE`| All required questions answered           |
| `COMPLETED`     | Session explicitly completed              |
| `CANCELLED`     | Session cancelled (terminal)              |

Transitions:
- `CREATED` → `IN_PROGRESS` — first answer submitted
- `IN_PROGRESS` → `READY_TO_FORGE` — auto when all required questions answered
- `READY_TO_FORGE` → `COMPLETED` — explicit `complete()`
- Any active state → `CANCELLED` — explicit `cancel()`

---

## Question model

Each `InterviewQuestion` contains:

| Field              | Type              | Purpose                              |
|--------------------|-------------------|--------------------------------------|
| `identifier`       | `str`             | Unique question key                   |
| `section`          | `str`             | Which domain this question belongs to |
| `title`            | `str`             | Short display heading                 |
| `description`      | `str`             | Help text for the author              |
| `answer_type`      | `str`             | `"str"`, `"str_list"`, or `"dict"`   |
| `required`         | `bool`            | Whether this question must be answered |
| `default_value`    | `Any`             | Value used when skipped               |
| `validation_rules` | `tuple[dict]`     | Per-answer validation rules           |
| `dependencies`     | `tuple[str]`      | Question IDs that must be answered first |

Questions contain **no UI code**.  Presentation is the consumer's
responsibility.

### Initial questions (18 total)

| Section       | Questions                                                     |
|---------------|---------------------------------------------------------------|
| Identity (5)  | name, identifier, summary, description, aliases               |
| Character (6) | core_values, motivations, strengths, limitations, goals, boundaries |
| Communication (5) | style, tone, vocabulary, response tendencies, formatting |
| Preferences (1)   | key-value preferences                                    |
| Behavior (1)      | behavior rules                                         |

---

## Section model

Each `InterviewSection` maps to one PersonaDraft domain.

| Section       | Questions | Required | Purpose                         |
|---------------|-----------|----------|---------------------------------|
| Identity      | 5         | 3        | Persona name, ID, summary       |
| Character     | 6         | 6        | Personality and boundaries      |
| Communication | 5         | 0        | Communication style and tone    |
| Preferences   | 1         | 0        | Key-value configuration         |
| Behavior      | 1         | 0        | Behavioural rules               |

---

## Draft ownership

The `PersonaDraft` is the **single source of truth** for authored values.

- `InterviewSession` owns one `PersonaDraft`
- Every answer updates the draft immediately
- `InterviewAnswer` objects are the audit trail only
- Answers must never diverge from the draft
- The draft can be passed directly to `CartridgeForge`

---

## Validation flow

### Immediate (per-answer)

Validated when submitted:

- Type checking (str / str_list / dict)
- Required field non-empty
- Min length (string)
- Identifier format (`^[a-z][a-z0-9_-]*$`)

### Draft-level (forge readiness)

Determined by checking all required questions are answered:

- `ForgeReadinessChecker.check()` returns a list of issues
- Empty list → ready to forge
- Does **not** invoke `CartridgeForge`

---

## Dependency resolution

Questions declare dependencies as a list of question identifiers.

A question is "available" only when all its dependencies have answers.

Current dependency graph:

```
identity_name
    ├── identity_identifier
    ├── identity_summary
    ├── identity_description
    └── identity_aliases
    └── character_* (all 6)
    └── preferences
    └── behavior_rules

identity_name + identity_identifier + identity_summary
    └── character_* (all 6 required)

character_core_values (any character question)
    └── communication_* (all 5)
```

The system supports arbitrary dependency DAGs for future conditional
questions.

---

## Serialization

Full session serialization to plain dict:

```python
{
    "session_id": "...",
    "state": "in_progress",
    "created_at": "2026-...",
    "updated_at": "2026-...",
    "completed_at": None,
    "last_question_id": "identity_name",
    "draft": { ... },       # complete PersonaDraft fields
    "answers": { ... },     # all InterviewAnswers keyed by question_id
}
```

`deserialize_session()` returns a fully functional `InterviewSession`
that can be resumed — `get_next_question()`, `submit_answer()`, and all
other operations work as expected.

---

## Future extension strategy

Explicit extension points (not yet implemented):

| Extension           | Mechanism                                 |
|---------------------|-------------------------------------------|
| AI-assisted         | `InterviewEngine` accepts answer generator |
| Template-based      | `create_session(template=PersonaDraft)`    |
| Adaptive interviews | Dynamic question registry                  |
| Collaborative       | Multiple sessions sharing one draft         |
| Enterprise          | Extended question sets                     |
| Localization        | Question titles/descriptions from locale   |
