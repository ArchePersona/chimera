from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import env

router = APIRouter()


def render(name: str, **context) -> HTMLResponse:
    template = env.get_template(name)
    html = template.render(**context)
    return HTMLResponse(html)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return render("index.html", request=request)


@router.get("/how-it-works", response_class=HTMLResponse)
async def how_it_works(request: Request):
    return render("how-it-works.html", request=request)


@router.get("/templates", response_class=HTMLResponse)
async def templates_list(request: Request):
    return render("templates/list.html", request=request)


@router.get("/interview", response_class=HTMLResponse)
async def interview(request: Request):
    return render("interview/chat.html", request=request)


@router.get("/interview/{session_id}", response_class=HTMLResponse)
async def interview_session(request: Request, session_id: str):
    return render("interview/chat.html", request=request, session_id=session_id)


@router.get("/preview/{session_id}", response_class=HTMLResponse)
async def preview(request: Request, session_id: str):
    return render("persona/preview.html", request=request, session_id=session_id)
