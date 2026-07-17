from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.cartridge import CartridgeValidationError, PersonaCartridge, PersonaDraft
from app.services.forge import CartridgeForge

router = APIRouter(prefix="/api")


class DraftBody(BaseModel):
    name: str = ""
    summary: str = ""
    communication_style: str = ""
    core_values: list[str] = []
    motivations: list[str] = []
    strengths: list[str] = []
    limitations: list[str] = []
    goals: list[str] = []
    boundaries: list[str] = []
    preferences: dict[str, str] = {}
    behavior_rules: list[str] = []


@router.get("/health")
async def health():
    return {"status": "ok", "app": "CHIMERA"}


@router.post("/validate")
async def validate_draft(body: DraftBody):
    draft = PersonaDraft(**body.model_dump())
    result = CartridgeForge.validate(draft)
    return {
        "valid": result.valid,
        "errors": [
            {"code": e.code.value, "field": e.field, "message": e.message}
            for e in result.errors
        ],
        "warnings": [
            {"code": w.code.value, "field": w.field, "message": w.message}
            for w in result.warnings
        ],
    }


@router.post("/forge")
async def forge_cartridge(body: DraftBody):
    draft = PersonaDraft(**body.model_dump())
    result = CartridgeForge.forge(draft)
    if result.success:
        return {"success": True, "cartridge": result.cartridge.to_dict()}
    raise HTTPException(
        status_code=400,
        detail={
            "error": result.error.code.value if result.error else "UNKNOWN",
            "message": result.error.message if result.error else "Forge failed",
            "detail": result.error.detail if result.error else "",
        },
    )


@router.get("/schema")
async def cartridge_schema():
    return PersonaCartridge.schema()
