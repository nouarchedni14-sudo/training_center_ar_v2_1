#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def normalize_ar(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ؤ": "و",
        "ئ": "ي",
        "ى": "ي",
        "ة": "ه",
        "ـ": "",
        "\u200f": "",
        "\u200e": "",
        "\u200d": "",
        "\ufeff": "",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    return " ".join(text.split()).strip().lower()


def safe_media_name(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "بدون_اسم"
    for ch in '<>:"/\\|?*':
        value = value.replace(ch, " ")
    return (" ".join(value.split())[:180] or "بدون_اسم")


def is_qr_file(path: Path) -> bool:
    joined = " | ".join(normalize_ar(p) for p in path.parts)
    return ("qr code" in joined) or ("qr_code" in joined) or ("qrcode" in joined)


def relative_under(child: Path, parent: Path) -> Optional[Path]:
    try:
        return child.relative_to(parent)
    except Exception:
        return None


def bootstrap_django(project_root: Path):
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "training_center.settings_lan")

    import django
    django.setup()

    from django.conf import settings
    from trainees.models import حضوري_أولي, تمهين, مسائي_ومعابر

    return settings, حضوري_أولي, تمهين, مسائي_ومعابر


@dataclass
class TraineeInfo:
    model_label: str
    pk: int
    full_name: str
    full_name_alt: str
    program_folder: str
    specialty_folder: str


def program_folder_for_model_name(model_name: str) -> str:
    if model_name == "حضوري_أولي":
        return "الحضوري أولي"
    if model_name == "تمهين":
        return "التمهين"
    if model_name == "مسائي_ومعابر":
        return "الدروس المسائيةوالمعابر"
    return "عام"


def build_trainee_index(models: Iterable[object]) -> Tuple[Dict[str, List[TraineeInfo]], List[TraineeInfo]]:
    index: Dict[str, List[TraineeInfo]] = defaultdict(list)
    all_rows: List[TraineeInfo] = []

    for model in models:
        model_name = model.__name__
        program_folder = program_folder_for_model_name(model_name)

        for obj in model.objects.all().only("id", "اللقب", "الاسم", "التخصص"):
            last_name = safe_media_name(getattr(obj, "اللقب", "") or "")
            first_name = safe_media_name(getattr(obj, "الاسم", "") or "")
            full_name = safe_media_name(f"{last_name} {first_name}")
            full_name_alt = safe_media_name(f"{first_name} {last_name}")
            specialty_folder = safe_media_name(getattr(obj, "التخصص", "") or "بدون تخصص")

            info = TraineeInfo(
                model_label=model_name,
                pk=obj.pk,
                full_name=full_name,
                full_name_alt=full_name_alt,
                program_folder=program_folder,
                specialty_folder=specialty_folder,
            )

            all_rows.append(info)

            for key in {
                normalize_ar(full_name),
                normalize_ar(full_name_alt),
                normalize_ar(last_name),
                normalize_ar(first_name),
            }:
                if key:
                    index[key].append(info)

    return index, all_rows


def choose_best_candidate(file_path: Path, candidates: List[TraineeInfo]) -> Tuple[Optional[TraineeInfo], str]:
    if not candidates:
        return None, "no_match"

    if len(candidates) == 1:
        return candidates[0], "single_match"

    norm_path = normalize_ar(str(file_path))
    scored: List[Tuple[int, TraineeInfo]] = []

    for c in candidates:
        score = 0
        if normalize_ar(c.program_folder) in norm_path:
            score += 20
        if normalize_ar(c.specialty_folder) in norm_path:
            score += 50
        if normalize_ar(c.full_name) in norm_path:
            score += 10
        if normalize_ar(c.full_name_alt) in norm_path:
            score += 5
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_score = scored[0][0]
    top = [c for s, c in scored if s == top_score]

    if top_score <= 0:
        return None, "ambiguous_no_context"

    if len(top) == 1:
        return top[0], "disambiguated_by_path"

    return None, "ambiguous_multiple_candidates"


def gather_source_files(media_root: Path) -> List[Path]:
    files: List[Path] = []
    canonical_root = media_root / "trainees"

    for path in media_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS and relative_under(path, canonical_root) is None:
            files.append(path)

    return files


def dest_path_for(media_root: Path, trainee: TraineeInfo, src: Path) -> Path:
    subfolder = "QR_Code" if is_qr_file(src) else "صور"
    file_name = safe_media_name(trainee.full_name) + src.suffix.lower()
    return media_root / "trainees" / trainee.program_folder / trainee.specialty_folder / subfolder / file_name


def reorganize(project_root: Path, mode: str = "copy") -> int:
    settings, حضوري_أولي, تمهين, مسائي_ومعابر = bootstrap_django(project_root)

    media_root = Path(settings.MEDIA_ROOT)
    app_data_dir = Path(getattr(settings, "APP_DATA_DIR", media_root.parent))
    logs_dir = app_data_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_txt = logs_dir / f"media_reorganizer_report_{run_id}.txt"
    report_csv = logs_dir / f"media_reorganizer_report_{run_id}.csv"

    index, all_rows = build_trainee_index([حضوري_أولي, تمهين, مسائي_ومعابر])
    source_files = gather_source_files(media_root)

    moved = 0
    copied = 0
    skipped_existing = 0
    unmatched = 0
    ambiguous = 0
    errors = 0

    csv_rows = []
    lines: List[str] = [
        "=== تقرير إعادة تنظيم media ===",
        f"وقت التشغيل: {datetime.now().isoformat(sep=' ', timespec='seconds')}",
        f"MEDIA_ROOT: {media_root}",
        f"عدد المتكوّنين المفهرسين: {len(all_rows)}",
        f"عدد ملفات الصور المصدرية: {len(source_files)}",
        "",
    ]

    for src in source_files:
        candidates = list(index.get(normalize_ar(src.stem), []))
        trainee, reason = choose_best_candidate(src, candidates)

        if trainee is None:
            status = "UNMATCHED" if reason == "no_match" else "AMBIGUOUS"
            unmatched += (status == "UNMATCHED")
            ambiguous += (status == "AMBIGUOUS")
            lines += [
                f"[{status}] {src}",
                f"  السبب: {reason}",
                "",
            ]
            csv_rows.append([status, str(src), "", "", "", reason])
            continue

        dst = dest_path_for(media_root, trainee, src)
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            if dst.exists() and dst.stat().st_size == src.stat().st_size:
                skipped_existing += 1
                lines.append(f"[SKIP_EXISTS] {src} -> {dst}")
                csv_rows.append([
                    "SKIP_EXISTS",
                    str(src),
                    str(dst),
                    trainee.full_name,
                    trainee.program_folder,
                    trainee.specialty_folder,
                ])
                continue

            if mode == "dry-run":
                action = "DRY_RUN"
            elif mode == "move":
                shutil.move(str(src), str(dst))
                action = "MOVED"
                moved += 1
            else:
                shutil.copy2(str(src), str(dst))
                action = "COPIED"
                copied += 1

            lines.append(f"[{action}] {src} -> {dst}")
            csv_rows.append([
                action,
                str(src),
                str(dst),
                trainee.full_name,
                trainee.program_folder,
                trainee.specialty_folder,
            ])

        except Exception as exc:
            errors += 1
            lines += [
                f"[ERROR] {src}",
                f"  {exc}",
            ]
            csv_rows.append(["ERROR", str(src), "", "", "", str(exc)])

    lines += [
        "",
        "=== الملخّص ===",
        f"copied={copied}",
        f"moved={moved}",
        f"skipped_existing={skipped_existing}",
        f"unmatched={unmatched}",
        f"ambiguous={ambiguous}",
        f"errors={errors}",
        f"report_txt={report_txt}",
        f"report_csv={report_csv}",
    ]

    report_txt.write_text("\n".join(lines), encoding="utf-8")

    with report_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "status",
            "source",
            "destination",
            "trainee_name",
            "program",
            "specialty_or_reason",
        ])
        writer.writerows(csv_rows)

    print("\n".join(lines))
    return 0 if errors == 0 else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--move", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    guessed_root = script_path.parent

    if (guessed_root / "manage.py").exists():
        project_root = guessed_root
    elif (guessed_root.parent / "manage.py").exists():
        project_root = guessed_root.parent
    else:
        project_root = Path(args.project_root or os.getcwd()).resolve()

    mode = "dry-run" if args.dry_run else ("move" if args.move else "copy")
    raise SystemExit(reorganize(project_root, mode=mode))


if __name__ == "__main__":
    main()