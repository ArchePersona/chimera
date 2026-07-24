"""CHIMERA Studio API Routes."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.interview.engine import InterviewEngine
from app.interview.exceptions import (
    InterviewError,
    InterviewStateError,
    InvalidAnswerError,
    QuestionNotAvailableError,
)
from app.models.cartridge import PersonaCartridge, PersonaDraft
from app.services.authoring_workflow import (
    AuthoringWorkflow,
    CartridgeCreationFailed,
    InterviewIncomplete,
    SessionNotFound,
    WorkflowStateError,
)
from app.services.cartridge_service import CartridgeNotFoundError, LifecycleState
from app.services.forge import CartridgeForge
from app.specification.compatibility import get_specification_compatibility_report

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class CreateSessionBody(BaseModel):
    template: Optional[dict[str, Any]] = None


class AnswerBody(BaseModel):
    question_id: str
    value: Any


class SkipBody(BaseModel):
    question_id: str


class DraftBody(BaseModel):
    name: str = ""
    identifier: str = ""
    summary: str = ""
    description: str = ""
    aliases: list[str] = []
    core_values: list[str] = []
    motivations: list[str] = []
    strengths: list[str] = []
    limitations: list[str] = []
    goals: list[str] = []
    boundaries: list[str] = []
    communication_style: str = ""
    tone: list[str] = []
    vocabulary_preferences: list[str] = []
    response_tendencies: list[str] = []
    formatting_preferences: list[str] = []
    preferences: dict[str, Any] = {}
    behavior_rules: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_workflow(request: Request) -> AuthoringWorkflow:
    return request.app.state.workflow


def _serialize_warnings(warnings):
    return [
        {"code": w.code.value, "field": w.field, "message": w.message}
        for w in warnings
    ]


def _serialize_question(q):
    return {
        "identifier": q.identifier,
        "section": q.section,
        "title": q.title,
        "description": q.description,
        "answer_type": q.answer_type,
        "required": q.required,
        "dependencies": list(q.dependencies),
    }


def _serialize_progress(prog):
    return {
        "total_questions": prog.total_questions,
        "answered_questions": prog.answered_questions,
        "remaining_questions": prog.remaining_questions,
        "percentage": prog.percentage,
        "completed_sections": list(prog.completed_sections),
        "remaining_sections": list(prog.remaining_sections),
        "section_progress": prog.section_progress,
        "all_required_answered": prog.all_required_answered,
        "forge_readiness_issues": list(prog.forge_readiness_issues),
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok", "app": "CHIMERA"}


# ---------------------------------------------------------------------------
# Legacy draft validation / forge (raw DraftBody, no session)
# ---------------------------------------------------------------------------

@router.post("/validate")
async def validate_draft(body: DraftBody):
    draft = PersonaDraft(**body.model_dump())
    result, _ = CartridgeForge.validate(draft)
    return {
        "valid": result.valid,
        "errors": [
            {"code": e.code.value, "field": e.field, "message": e.message}
            for e in result.errors
        ],
        "warnings": _serialize_warnings(result.warnings),
    }


@router.post("/forge")
async def forge_cartridge(body: DraftBody):
    draft = PersonaDraft(**body.model_dump())
    result = CartridgeForge.forge(draft)
    if result.success:
        return {
            "success": True,
            "cartridge": result.cartridge.to_dict(),
            "warnings": _serialize_warnings(result.warnings),
        }
    raise HTTPException(
        status_code=400,
        detail={
            "error": result.error.code.value if result.error else "UNKNOWN",
            "message": result.error.message if result.error else "Forge failed",
            "detail": result.error.detail if result.error else "",
            "warnings": _serialize_warnings(result.warnings),
        },
    )


@router.get("/schema")
async def cartridge_schema():
    return PersonaCartridge.schema()


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

@router.post("/sessions")
async def create_session(request: Request, body: CreateSessionBody = CreateSessionBody()):
    workflow = _get_workflow(request)
    template = None
    if body.template:
        template = PersonaDraft(**body.template)
    session = workflow.create_session(template=template)
    prog = workflow.progress(session.session_id)
    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "progress": _serialize_progress(prog),
    }


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str):
    workflow = _get_workflow(request)
    try:
        session = workflow.load_session(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    prog = workflow.progress(session_id)
    readiness = workflow.readiness(session_id)
    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "last_question_id": session.last_question_id,
        "progress": _serialize_progress(prog),
        "ready_to_forge": readiness.ready,
        "readiness_issues": list(readiness.issues),
    }


# ---------------------------------------------------------------------------
# Interview operations
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/questions")
async def get_questions(request: Request, session_id: str):
    workflow = _get_workflow(request)
    try:
        questions = workflow.available_questions(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    current = workflow.current_question(session_id)
    return {
        "available": [_serialize_question(q) for q in questions],
        "current": _serialize_question(current) if current else None,
    }


@router.get("/sessions/{session_id}/progress")
async def get_progress(request: Request, session_id: str):
    workflow = _get_workflow(request)
    try:
        prog = workflow.progress(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return _serialize_progress(prog)


@router.post("/sessions/{session_id}/answers")
async def submit_answer(request: Request, session_id: str, body: AnswerBody):
    workflow = _get_workflow(request)
    try:
        answer = workflow.answer_question(session_id, body.question_id, body.value)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    except QuestionNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidAnswerError as exc:
        raise HTTPException(status_code=422, detail={
            "error": "VALIDATION_ERROR",
            "question_id": exc.question_id,
            "message": exc.reason,
        })
    except InterviewStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    prog = workflow.progress(session_id)
    readiness = workflow.readiness(session_id)
    return {
        "accepted": True,
        "question_id": answer.question_id,
        "progress": _serialize_progress(prog),
        "ready_to_forge": readiness.ready,
        "readiness_issues": list(readiness.issues),
    }


@router.post("/sessions/{session_id}/skip")
async def skip_question(request: Request, session_id: str, body: SkipBody):
    workflow = _get_workflow(request)
    try:
        workflow.skip_question(session_id, body.question_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    except QuestionNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InterviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    prog = workflow.progress(session_id)
    readiness = workflow.readiness(session_id)
    return {
        "accepted": True,
        "question_id": body.question_id,
        "progress": _serialize_progress(prog),
        "ready_to_forge": readiness.ready,
        "readiness_issues": list(readiness.issues),
    }


@router.post("/sessions/{session_id}/complete")
async def complete_session(request: Request, session_id: str):
    workflow = _get_workflow(request)
    try:
        workflow.complete_session(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    except InterviewStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"completed": True, "session_id": session_id}


# ---------------------------------------------------------------------------
# Draft review
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/draft")
async def get_draft(request: Request, session_id: str):
    workflow = _get_workflow(request)
    try:
        session = workflow.load_session(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    draft = session.draft
    prog = workflow.progress(session_id)
    readiness = workflow.readiness(session_id)
    return {
        "session_id": session_id,
        "state": session.state.value,
        "draft": {
            "name": draft.name,
            "identifier": draft.identifier,
            "summary": draft.summary,
            "description": draft.description,
            "aliases": list(draft.aliases),
            "core_values": list(draft.core_values),
            "motivations": list(draft.motivations),
            "strengths": list(draft.strengths),
            "limitations": list(draft.limitations),
            "goals": list(draft.goals),
            "boundaries": list(draft.boundaries),
            "communication_style": draft.communication_style,
            "tone": list(draft.tone),
            "vocabulary_preferences": list(draft.vocabulary_preferences),
            "response_tendencies": list(draft.response_tendencies),
            "formatting_preferences": list(draft.formatting_preferences),
            "preferences": dict(draft.preferences),
            "behavior_rules": list(draft.behavior_rules),
        },
        "progress": _serialize_progress(prog),
        "ready_to_forge": readiness.ready,
        "readiness_issues": list(readiness.issues),
    }


@router.post("/sessions/{session_id}/validate")
async def validate_session_draft(request: Request, session_id: str):
    workflow = _get_workflow(request)
    try:
        session = workflow.load_session(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    result, _ = CartridgeForge.validate(session.draft)
    return {
        "valid": result.valid,
        "errors": [
            {"code": e.code.value, "field": e.field, "message": e.message}
            for e in result.errors
        ],
        "warnings": _serialize_warnings(result.warnings),
    }


@router.post("/sessions/{session_id}/forge")
async def forge_session_draft(request: Request, session_id: str):
    workflow = _get_workflow(request)
    try:
        result = workflow.forge(session_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    except InterviewIncomplete as exc:
        raise HTTPException(status_code=409, detail={
            "error": "INTERVIEW_INCOMPLETE",
            "message": str(exc),
        })
    except WorkflowStateError as exc:
        raise HTTPException(status_code=409, detail={
            "error": "WORKFLOW_STATE_ERROR",
            "message": str(exc),
        })
    except CartridgeCreationFailed as exc:
        raise HTTPException(status_code=400, detail={
            "error": "CARTRIDGE_CREATION_FAILED",
            "message": str(exc),
            "detail": exc.detail,
        })

    if result.success:
        return {
            "success": True,
            "cartridge": result.cartridge.to_dict(),
            "warnings": _serialize_warnings(result.warnings),
            "session_preserved": True,
        }

    raise HTTPException(
        status_code=400,
        detail={
            "error": result.error.code.value if result.error else "UNKNOWN",
            "message": result.error.message if result.error else "Forge failed",
            "detail": result.error.detail if result.error else "",
            "warnings": _serialize_warnings(result.warnings),
        },
    )


# ---------------------------------------------------------------------------
# Cartridge Inspector
# ---------------------------------------------------------------------------

@router.get("/cartridges/{cartridge_id}")
async def get_cartridge(request: Request, cartridge_id: str):
    workflow = _get_workflow(request)
    cartridge_service = workflow.cartridge_service
    try:
        cartridge = cartridge_service.get_by_uuid(cartridge_id)
    except CartridgeNotFoundError:
        raise HTTPException(status_code=404, detail=f"Cartridge '{cartridge_id}' not found")
    identifier = cartridge.identity.identifier
    lifecycle = cartridge_service.get_lifecycle_metadata(identifier)
    source = cartridge_service.get_source_info(identifier)
    return {
        "cartridge": cartridge.to_dict(),
        "lifecycle": {
            "state": lifecycle.lifecycle_state.value,
            "created_at": lifecycle.created_at.isoformat(),
            "updated_at": lifecycle.updated_at.isoformat(),
            "archived_at": lifecycle.archived_at.isoformat() if lifecycle.archived_at else None,
            "export_count": lifecycle.export_count,
            "tags": list(lifecycle.tags),
            "notes": lifecycle.notes,
        },
        "source": source,
    }


@router.get("/cartridges/{cartridge_id}/validation")
async def get_cartridge_validation(request: Request, cartridge_id: str):
    workflow = _get_workflow(request)
    cartridge_service = workflow.cartridge_service
    try:
        cartridge = cartridge_service.get_by_uuid(cartridge_id)
    except CartridgeNotFoundError:
        raise HTTPException(status_code=404, detail=f"Cartridge '{cartridge_id}' not found")
    validation_result, spec_validation = CartridgeForge.validate_cartridge(cartridge)
    return {
        "valid": validation_result.valid,
        "errors": [
            {"code": e.code.value, "field": e.field, "message": e.message}
            for e in validation_result.errors
        ],
        "warnings": _serialize_warnings(validation_result.warnings),
        "specification": spec_validation,
    }


@router.get("/cartridges/{cartridge_id}/versions")
async def get_cartridge_versions(request: Request, cartridge_id: str):
    workflow = _get_workflow(request)
    cartridge_service = workflow.cartridge_service
    try:
        cartridge = cartridge_service.get_by_uuid(cartridge_id)
    except CartridgeNotFoundError:
        raise HTTPException(status_code=404, detail=f"Cartridge '{cartridge_id}' not found")
    identifier = cartridge.identity.identifier
    versions = cartridge_service.versions(identifier)
    return {
        "identifier": identifier,
        "current_version_id": cartridge_id,
        "versions": versions,
        "total_versions": len(versions),
    }


@router.get("/cartridges/{cartridge_id}/source")
async def get_cartridge_source(request: Request, cartridge_id: str):
    workflow = _get_workflow(request)
    cartridge_service = workflow.cartridge_service
    try:
        source = cartridge_service.get_source_info_by_uuid(cartridge_id)
    except CartridgeNotFoundError:
        raise HTTPException(status_code=404, detail=f"Cartridge '{cartridge_id}' not found")
    return source


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@router.get("/cartridges/{cartridge_id}/export")
async def export_cartridge(request: Request, cartridge_id: str):
    workflow = _get_workflow(request)
    cartridge_service = workflow.cartridge_service
    try:
        cartridge = cartridge_service.get_by_uuid(cartridge_id)
    except CartridgeNotFoundError:
        raise HTTPException(status_code=404, detail=f"Cartridge '{cartridge_id}' not found")

    serialized = cartridge_service.export_canonical_by_uuid(cartridge_id)
    validation_result, spec_validation = CartridgeForge.validate_cartridge(cartridge)
    compatibility = get_specification_compatibility_report(cartridge)

    serialized_json = json.dumps(serialized, indent=2, sort_keys=False)
    import hashlib
    checksum = hashlib.sha256(serialized_json.encode("utf-8")).hexdigest()
    size_bytes = len(serialized_json.encode("utf-8"))

    identifier = cartridge.identity.identifier
    version = cartridge.manifest.schema_version
    filename = f"{identifier}_v{version}.json"

    return {
        "cartridge": serialized,
        "filename": filename,
        "checksum": {"algorithm": "sha256", "value": checksum},
        "size_bytes": size_bytes,
        "format": "json",
        "validation": {
            "valid": validation_result.valid,
            "warning_count": len(validation_result.warnings),
            "errors": [
                {"code": e.code.value, "field": e.field, "message": e.message}
                for e in validation_result.errors
            ],
        },
        "specification": spec_validation,
        "compatibility": compatibility,
        "lifecycle": {
            "export_count": cartridge_service.get_lifecycle_metadata(identifier).export_count,
        },
    }
