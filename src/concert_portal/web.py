from pathlib import Path

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"

templates = Jinja2Templates(
    directory=str(TEMPLATE_DIR),
)
