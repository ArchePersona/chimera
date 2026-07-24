# Authoring Workflow

## Overview

`AuthoringWorkflow` is the single canonical application pipeline that
transforms an interview session into a managed `PersonaCartridge`.

It owns **orchestration only**.  Every operation delegates to the
appropriate existing component — interview engine, cartridge service,
or export service.  No interview logic, validation rules, forge logic,
lifecycle logic, or export logic lives here.

---

## Architecture

```
AuthoringWorkflow
    │
    ├── InterviewEngine      (interview sessions)
    ├── CartridgeService     (lifecycle management)
    └── Export Service       (ARCHEngine export)
```

---

## Ownership boundaries

| Concern                 | Owner                  |
|-------------------------|------------------------|
| Interview logic         | `InterviewEngine`      |
| Answer validation       | `AnswerValidator`      |
| Draft readiness         | `ForgeReadinessChecker`|
| Cartridge creation      | `CartridgeForge`       |
| Cartridge lifecycle     | `CartridgeService`     |
| Runtime projection      | `RuntimeProjectionBuilder`|
| ARCHEngine export       | `archengine_export`    |
| **Orchestration**       | **`AuthoringWorkflow`**|

`AuthoringWorkflow` must **never** contain:
- Interview logic (question ordering, dependencies, state transitions)
- Validation rules
- Forge logic
- Lifecycle transitions
- Export payload construction

---

## Pipeline

```
create_session()
    │
    ▼
answer_question() / skip_question()
    │
    ▼
progress() / readiness()
    │
    ▼
forge()
    │
    ├── CartridgeService.create()
    │       ├── CartridgeForge.validate()
    │       └── CartridgeForge.forge()
    │
    ▼
export() / export_json()
    │
    └── archengine_export.export_archengine_payload()
```

---

## Public API

| Method                | Delegates to                 | Purpose                              |
|-----------------------|------------------------------|--------------------------------------|
| `create_session()`    | `InterviewEngine`            | Start a new interview                |
| `load_session()`      | — (lookup)                   | Resume an existing session           |
| `answer_question()`   | `InterviewEngine`            | Submit an answer                     |
| `skip_question()`     | `InterviewEngine`            | Skip a non-required question         |
| `current_question()`  | `InterviewEngine`            | Next unanswered question             |
| `available_questions()`| `InterviewEngine`           | Questions with dependencies met      |
| `progress()`          | `InterviewEngine`            | Deterministic progress report        |
| `readiness()`         | `InterviewEngine`            | Forge readiness check                |
| `forge()`             | `CartridgeService`           | Forge + register cartridge           |
| `export()`            | `archengine_export`          | ARCHEngine payload                   |
| `export_json()`       | `archengine_export`          | ARCHEngine JSON dict                 |
| `complete_session()`  | `InterviewEngine`            | Mark session completed               |
| `cancel_session()`    | `InterviewEngine`            | Cancel session                       |
| `serialize_session()` | `InterviewEngine`            | Serialize to plain dict              |
| `deserialize_session()`| `InterviewEngine`           | Restore from serialized data         |

---

## Forge process

```
forge(session_id)
    │
    ├── 1. Check session exists
    ├── 2. Check session not completed/cancelled
    ├── 3. Check all required questions answered
    ├── 4. CartridgeService.create(draft)
    │       ├── CartridgeForge.validate(draft)
    │       ├── CartridgeForge.forge(draft)
    │       └── Register in lifecycle store
    └── 5. Return ForgeResult
```

If the draft fails validation, `CartridgeService.create` returns a
`ForgeResult` with `success=False`, and the workflow raises
`CartridgeCreationFailed`.

---

## Error model

| Exception                 | When raised                                   |
|---------------------------|-----------------------------------------------|
| `SessionNotFound`         | Session ID not found                          |
| `InterviewIncomplete`     | Required questions remain unanswered          |
| `CartridgeCreationFailed` | Forge validation failed                       |
| `WorkflowStateError`      | Invalid state for the operation               |

---

## Session vs Cartridge ownership

- `AuthoringWorkflow` owns interview sessions (in-memory dict).
- `CartridgeService` owns managed cartridges (lifecycle store).

These responsibilities are **never merged**.  Sessions exist before a
cartridge is forged; cartridges exist after.  The workflow bridges
the two but keeps them separate.

---

## Serialization boundary

Sessions are serialized using `InterviewEngine.serialize_session()`.
The workflow does not introduce a second persistence format.

`deserialize_session()` restores a fully functional session into the
workflow's session store.

---

## Future integration

Extension points prepared (not yet implemented):

| Integration         | Mechanism                                    |
|---------------------|----------------------------------------------|
| AI-assisted         | Plugs into `answer_question()`               |
| Collaborative       | Shared session store                         |
| Autosave            | Periodic `serialize_session()`               |
| Undo/redo           | Answer history in session                    |
| Template selection  | `create_session(template=...)`               |
| Marketplace imports | Pre-built `PersonaDraft` as template         |
| Cloud sync          | Replace in-memory session store              |
