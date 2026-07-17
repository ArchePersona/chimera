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


@router.get("/build", response_class=HTMLResponse)
async def build(request: Request):
    return render("build.html", request=request)
