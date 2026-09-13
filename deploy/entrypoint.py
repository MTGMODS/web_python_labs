"""Стартовий сценарій контейнера застосунку.

Спочатку схема (Alembic), потім демодані (скрипт ідемпотентний), далі uvicorn.
Окремий процес Python замість shell-скрипта, щоб не залежати від закінчень
рядків Windows (CRLF) у файлі entrypoint.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    subprocess.check_call(["alembic", "upgrade", "head"])

    if _truthy("RUN_SEED", "1"):
        subprocess.check_call([sys.executable, "-m", "scripts.seed"])

    command = [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    if _truthy("UVICORN_RELOAD"):
        command.append("--reload")

    os.execvp(command[0], command)


if __name__ == "__main__":
    raise SystemExit(main())
