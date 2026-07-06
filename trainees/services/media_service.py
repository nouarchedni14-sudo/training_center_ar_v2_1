from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from django.conf import settings

PROGRAM_MEDIA_FOLDERS = {
    "initial": ["الحضوري أولي", "حضوري أولي", "الحضوري_أولي"],
    "apprentice": ["التمهين", "تمهين"],
    "evening": ["الدروس المسائية", "الدروس المسائيةوالمعابر", "الدروس المسائية والمعابر", "المسائية والمعابر", "مسائي ومعابر"],
    "crossing": ["المعابر", "الدروس المسائيةوالمعابر", "الدروس المسائية والمعابر", "المسائية والمعابر", "مسائي ومعابر"],
}

IMAGE_EXTENSIONS: tuple[str, ...] = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')


def media_program_folder(program: str) -> str:
    folders = PROGRAM_MEDIA_FOLDERS.get(program, ["عام"])
    return folders[0] if isinstance(folders, (list, tuple)) else folders


def safe_media_part(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "بدون_اسم"
    forbidden = '<>:"/\\|?*'
    for ch in forbidden:
        value = value.replace(ch, ' ')
    value = ' '.join(value.split())
    return value[:180] or "بدون_اسم"


def specialty_folder_candidates(value: str) -> list[str]:
    base = safe_media_part(value or "بدون تخصص")
    variants = [base]
    compact = base.replace(" ", "")
    underscored = base.replace(" ", "_")
    for candidate in (compact, underscored):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def media_root_candidates() -> list[Path]:
    root = Path(settings.MEDIA_ROOT)
    candidates = [root / "trainees", root]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def trainee_media_base_name(obj) -> str:
    return safe_media_part(f"{obj.اللقب} {obj.الاسم}")


def trainee_media_folder(obj, program: str, subfolder: str) -> Path:
    return (
        media_root_candidates()[0]
        / media_program_folder(program)
        / specialty_folder_candidates(getattr(obj, 'التخصص', '') or 'بدون تخصص')[0]
        / subfolder
    )


def remove_existing_media_variants(folder: Path, base_name: str, extensions: Iterable[str] = IMAGE_EXTENSIONS) -> None:
    for old_ext in extensions:
        old_path = folder / f'{base_name}{old_ext}'
        if old_path.exists():
            old_path.unlink()


def save_uploaded_media(obj, program: str, uploaded_file, subfolder: str) -> Path | None:
    if not uploaded_file:
        return None
    folder = trainee_media_folder(obj, program, subfolder)
    folder.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1].lower() or '.jpg'
    base_name = trainee_media_base_name(obj)
    remove_existing_media_variants(folder, base_name)
    target = folder / f'{base_name}{ext}'
    with target.open('wb+') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)
    return target
