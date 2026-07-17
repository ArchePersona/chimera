from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import storage
from app.services.interview import apply_answer, estimate_completeness, find_unknowns, next_question

router = APIRouter(prefix="/api")


class StartSessionBody(BaseModel):
    persona_name: str = ""


class AnswerBody(BaseModel):
    answer: str


@router.get("/health")
async def health():
    return {"status": "ok", "app": "CHIMERA"}


@router.post("/interview")
async def start_interview(body: StartSessionBody):
    session = storage.create_session(body.persona_name)
    draft = storage.get_draft(session.id)
    q = next_question(draft)
    return {
        "session_id": session.id,
        "question": q["question"] if q else None,
        "reasoning": q["reasoning"] if q else None,
        "completeness": draft.completeness,
        "unknowns": draft.unknowns,
    }


@router.get("/interview/{session_id}")
async def get_interview_state(session_id: str):
    session = storage.get_session(session_id)
    draft = storage.get_draft(session_id)
    if not session or not draft:
        raise HTTPException(404, "Session not found")
    q = next_question(draft)
    return {
        "session_id": session.id,
        "persona_name": draft.name,
        "turns": [
            {
                "question": t.question,
                "answer": t.answer,
                "reasoning": t.reasoning,
                "hypothesis": t.hypothesis,
                "clarification": t.clarification,
            }
            for t in session.turns
        ],
        "next_question": q["question"] if q else None,
        "next_reasoning": q["reasoning"] if q else None,
        "completeness": draft.completeness,
        "unknowns": draft.unknowns,
        "complete": q is None,
    }


@router.post("/interview/{session_id}/answer")
async def submit_answer(session_id: str, body: AnswerBody):
    session = storage.get_session(session_id)
    draft = storage.get_draft(session_id)
    if not session or not draft:
        raise HTTPException(404, "Session not found")
    q = next_question(draft)
    if not q:
        raise HTTPException(400, "Interview is complete")
    turn = apply_answer(draft, q, body.answer)
    storage.add_turn(session_id, turn)
    storage.update_draft(session_id, draft)
    next_q = next_question(draft)
    return {
        "turn": {
            "question": turn.question,
            "answer": turn.answer,
            "reasoning": turn.reasoning,
            "hypothesis": turn.hypothesis,
            "clarification": turn.clarification,
        },
        "next_question": next_q["question"] if next_q else None,
        "next_reasoning": next_q["reasoning"] if next_q else None,
        "completeness": draft.completeness,
        "unknowns": draft.unknowns,
        "complete": next_q is None,
    }


@router.get("/interview/{session_id}/preview")
async def get_preview(session_id: str):
    draft = storage.get_draft(session_id)
    if not draft:
        raise HTTPException(404, "Session not found")
    return {
        "name": draft.name,
        "summary": draft.summary,
        "communication_style": draft.communication_style,
        "core_values": draft.core_values,
        "motivations": draft.motivations,
        "strengths": draft.strengths,
        "weaknesses": draft.weaknesses,
        "goals": draft.goals,
        "boundaries": draft.boundaries,
        "unknowns": draft.unknowns,
        "completeness": round(draft.completeness * 100),
    }


@router.post("/interview/{session_id}/cartridge")
async def forge_cartridge(session_id: str):
    draft = storage.get_draft(session_id)
    if not draft:
        raise HTTPException(404, "Session not found")
    unknowns = find_unknowns(draft)
    if unknowns:
        raise HTTPException(400, f"Cannot forge cartridge. Missing: {', '.join(unknowns)}")
    return {
        "name": draft.name,
        "summary": draft.summary,
        "communication_style": draft.communication_style,
        "core_values": draft.core_values,
        "motivations": draft.motivations,
        "strengths": draft.strengths,
        "weaknesses": draft.weaknesses,
        "goals": draft.goals,
        "boundaries": draft.boundaries,
        "format": "CHIMERA Persona Cartridge v1.0",
        "model_independent": True,
        "status": "forged",
    }
