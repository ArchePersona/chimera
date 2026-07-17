from jinja2 import Environment, FileSystemLoader

from app.config import TEMPLATES_DIR

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), auto_reload=True, cache_size=0)


def url_for(_name: str, *, path: str) -> str:
    return f"/static/{path}"


env.globals["url_for"] = url_for
