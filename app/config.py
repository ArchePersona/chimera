import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
DATA_DIR = BASE_DIR / "data"

# Identity HMAC secret — must be set via env var in production.
CHIMERA_ENV = os.environ.get("CHIMERA_ENV", "development")
IDENTITY_HMAC_SECRET: str | None = os.environ.get("CHIMERA_IDENTITY_SECRET")
