import os
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


def static_version(path):
    normalized_path = path.replace("\\", "/")
    if normalized_path.startswith("static/"):
        normalized_path = normalized_path[len("static/") :]

    resolved_path = os.path.join(STATIC_DIR, normalized_path)
    try:
        return os.path.getmtime(resolved_path)
    except OSError:
        return 0


templates.env.globals["static_version"] = static_version
