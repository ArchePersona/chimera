from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import CHIMERA_ENV, DATA_DIR, IDENTITY_HMAC_SECRET, STATIC_DIR
from app.identity.dev_provider import DevIdentityProvider
from app.identity.middleware import IdentityMiddleware
from app.interview.engine import InterviewEngine
from app.repositories.cartridge_repository import CartridgeRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.storage import FilesystemStorage
from app.routes import api, web
from app.services.authoring_workflow import AuthoringWorkflow
from app.services.cartridge_service import CartridgeService
from app.templating import env

# --- Bootstrap persistence layer ---
_storage = FilesystemStorage(DATA_DIR)
_engine = InterviewEngine()
_session_repo = SessionRepository(_storage, _engine)
_cartridge_repo = CartridgeRepository(_storage)
_cartridge_svc = CartridgeService(repo=_cartridge_repo)
_workflow = AuthoringWorkflow(
    interview_engine=_engine,
    cartridge_service=_cartridge_svc,
    session_repo=_session_repo,
)

# --- App setup ---
app = FastAPI(title="CHIMERA Studio", version="1.0.0")
app.state.workflow = _workflow

# --- Identity middleware ---
_provider = DevIdentityProvider(secret=IDENTITY_HMAC_SECRET)
app.add_middleware(IdentityMiddleware, provider=_provider)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(web.router)
app.include_router(api.router)


def _is_api_path(path: str) -> bool:
    return "/api/" in path


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if _is_api_path(request.url.path):
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content=detail)
    template = env.get_template("studio/error.html")
    html = template.render(
        request=request,
        status_code=exc.status_code,
        message=str(exc.detail),
        current_route=request.url.path,
    )
    return HTMLResponse(html, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if _is_api_path(request.url.path):
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
        )
    template = env.get_template("studio/error.html")
    html = template.render(
        request=request,
        status_code=500,
        message="An unexpected system error occurred. Please try again.",
        current_route=request.url.path,
    )
    return HTMLResponse(html, status_code=500)
