from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings


BACKUP_DIR_NAME = "backups"


def get_backup_directory() -> Path:
    backup_dir = Path(settings.BASE_DIR) / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir



def get_database_path() -> Path:
    return Path(settings.DATABASES["default"]["NAME"])



def serialize_backup(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": path,
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime),
    }



def create_database_backup(*, prefix: str = "training_center_backup") -> Path:
    db_path = get_database_path()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = db_path.suffix or ".sqlite3"
    target = get_backup_directory() / f"{prefix}_{timestamp}{suffix}"
    shutil.copy2(db_path, target)
    return target



def list_backups(limit: int = 10) -> list[Path]:
    backup_dir = get_backup_directory()
    backups = [p for p in backup_dir.iterdir() if p.is_file()]
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[:limit]



def latest_backup() -> Path | None:
    backups = list_backups(limit=1)
    return backups[0] if backups else None



def get_backup_by_name(filename: str) -> Path | None:
    candidate = get_backup_directory() / Path(filename).name
    if candidate.exists() and candidate.is_file():
        return candidate
    return None



def restore_database_backup(filename: str) -> Path:
    backup_path = get_backup_by_name(filename)
    if not backup_path:
        raise FileNotFoundError("ملف النسخة الاحتياطية غير موجود.")

    db_path = get_database_path()
    if db_path.exists():
        create_database_backup(prefix="pre_restore_backup")
    shutil.copy2(backup_path, db_path)
    return backup_path
