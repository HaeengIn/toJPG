from fastapi.templating import Jinja2Templates
import os

templates = Jinja2Templates(directory="templates")


def static_version(path):
    return os.path.getmtime(path)


templates.env.globals["static_version"] = static_version