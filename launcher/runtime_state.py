from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "TrainingCenter"


def app_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or "."
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtime_state_path() -> Path:
    return app_data_dir() / "runtime_state.json"


def write_runtime_state(data: dict) -> Path:
    path = runtime_state_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_runtime_state() -> dict:
    path = runtime_state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def shutdown_request_path() -> Path:
    return app_data_dir() / "shutdown_requested.flag"


def request_shutdown() -> Path:
    path = shutdown_request_path()
    path.write_text("1", encoding="utf-8")
    return path


def clear_shutdown_request() -> None:
    shutdown_request_path().unlink(missing_ok=True)


def is_shutdown_requested() -> bool:
    return shutdown_request_path().exists()
