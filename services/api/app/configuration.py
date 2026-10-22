from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# FastAPI does not automatically read .env. Keep this tiny loader dependency-free.
ENV_FILE = ROOT / ".env"
if ENV_FILE.is_file():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def from_project_root(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


STORAGE_ROOT = from_project_root(os.getenv("PETFORGE_STORAGE_ROOT", "storage"))
DATABASE_PATH = from_project_root(os.getenv("PETFORGE_DATABASE_PATH", STORAGE_ROOT / "petforge.sqlite3"))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
