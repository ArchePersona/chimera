"""CHIMERA Studio Web Routes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.templating import env

router = APIRouter()

BASE_PATH = "/chimera"


def render(name: str, **context) -> HTMLResponse:
    template = env.get_template(name)
    context.setdefault("base_path", BASE_PATH)
    html = template.render(**context)
    return HTMLResponse(html)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Studio home screen — presents the Cartridge Dashboard."""
    return render("studio/dashboard.html", request=request, current_route="/")


@router.get("/cartridges", response_class=HTMLResponse)
async def cartridges_dashboard(request: Request):
    """Cartridge Dashboard listing all managed persona cartridges."""
    return render("studio/dashboard.html", request=request, current_route="/cartridges")


@router.get("/cartridges/new", response_class=HTMLResponse)
async def new_persona(request: Request):
    """New Persona authoring entry screen."""
    return render("studio/new_persona.html", request=request, current_route="/cartridges/new")


@router.get("/interviews/{session_id}", response_class=HTMLResponse)
async def interview_workspace(request: Request, session_id: str):
    """Guided Interview Workspace for an active authoring session."""
    return render(
        "studio/interview.html",
        request=request,
        session_id=session_id,
        current_route=f"/interviews/{session_id}",
    )


@router.get("/drafts/{session_id}/review", response_class=HTMLResponse)
async def draft_review(request: Request, session_id: str):
    """Draft Review experience before cartridge forging."""
    return render(
        "studio/draft_review.html",
        request=request,
        session_id=session_id,
        current_route=f"/drafts/{session_id}/review",
    )


@router.get("/cartridges/{cartridge_id}", response_class=HTMLResponse)
async def cartridge_inspector(request: Request, cartridge_id: str):
    """Canonical Cartridge Inspector for forged cartridges."""
    return render(
        "studio/inspector.html",
        request=request,
        cartridge_id=cartridge_id,
        current_route=f"/cartridges/{cartridge_id}",
    )


@router.get("/how-it-works", response_class=HTMLResponse)
async def how_it_works(request: Request):
    """Informational overview of CHIMERA architecture and workflow."""
    return render("how-it-works.html", request=request, current_route="/how-it-works")
