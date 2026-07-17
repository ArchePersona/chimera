from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR
from app.routes import web, api

app = FastAPI(title="CHIMERA", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(web.router)
app.include_router(api.router)
