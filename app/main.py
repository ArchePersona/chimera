from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import STATIC_DIR
from app.routes import api, web
from app.services.authoring_workflow import AuthoringWorkflow
from app.templating import env

app = FastAPI(title="CHIMERA Studio", version="1.0.0")
app.state.workflow = AuthoringWorkflow()
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
    import traceback
    traceback.print_exc()
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
