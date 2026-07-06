from pathlib import Path
import hashlib
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from sync_core.models import CentralUpdateRelease


class Command(BaseCommand):
    help = "نشر أو تحديث إصدار مركزي جديد للمكاتب، برابط خارجي أو بملف محلي يرفعه الخادم المركزي."

    def add_arguments(self, parser):
        parser.add_argument("--version", required=True)
        parser.add_argument("--title", default="")
        parser.add_argument("--type", choices=["installer", "patch"], default="patch")
        parser.add_argument("--channel", choices=["stable", "test"], default="stable")
        parser.add_argument("--url", default="", help="رابط تحميل Installer أو Patch خارجي")
        parser.add_argument("--file", default="", help="مسار ملف ZIP/EXE/MSI لحفظه داخل الخادم المركزي")
        parser.add_argument("--sha256", default="")
        parser.add_argument("--notes", default="")
        parser.add_argument("--required", action="store_true")
        parser.add_argument("--inactive", action="store_true", help="حفظه بدون نشر")
        parser.add_argument("--office", action="append", default=[], help="Office ID مسموح. يمكن تكرارها")
        parser.add_argument("--block-office", action="append", default=[], help="Office ID مستثنى. يمكن تكرارها")

    def _save_local_file(self, obj: CentralUpdateRelease, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            raise CommandError(f"ملف التحديث غير موجود: {file_path}")
        if file_path.suffix.lower() not in {".zip", ".exe", ".msi"}:
            raise CommandError("ملف التحديث يجب أن يكون ZIP أو EXE أو MSI")
        root = Path(getattr(settings, "APP_DATA_DIR", settings.BASE_DIR)) / "central_updates" / "packages" / str(obj.pk)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        safe_version = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in obj.version)[:80] or "update"
        target = root / f"update_{safe_version}{file_path.suffix.lower()}"
        digest = hashlib.sha256()
        with file_path.open("rb") as src, target.open("wb") as dst:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                digest.update(chunk)
                dst.write(chunk)
        obj.local_package_name = f"{obj.pk}/{target.name}"
        obj.checksum_sha256 = digest.hexdigest()
        obj.file_size_bytes = target.stat().st_size
        obj.update_type = CentralUpdateRelease.TYPE_INSTALLER if target.suffix.lower() in {".exe", ".msi"} else CentralUpdateRelease.TYPE_PATCH
        obj.save(update_fields=["local_package_name", "checksum_sha256", "file_size_bytes", "update_type", "updated_at"])

    def handle(self, *args, **options):
        version = options["version"].strip()
        if not version:
            raise CommandError("--version مطلوب")
        if not options.get("url") and not options.get("file"):
            raise CommandError("يجب تمرير --url أو --file")
        allowed = [x.strip() for x in options["office"] if x.strip()]
        blocked = [x.strip() for x in options["block_office"] if x.strip()]
        rollout_all = not bool(allowed)
        obj, created = CentralUpdateRelease.objects.update_or_create(
            version=version,
            defaults={
                "title": options["title"],
                "update_type": options["type"],
                "channel": options["channel"],
                "download_url": options["url"],
                "checksum_sha256": options["sha256"],
                "release_notes": options["notes"],
                "is_required": bool(options["required"]),
                "is_active": not bool(options["inactive"]),
                "rollout_all_offices": rollout_all,
                "allowed_office_ids": allowed,
                "blocked_office_ids": blocked,
            },
        )
        if options.get("file"):
            self._save_local_file(obj, Path(options["file"]).expanduser())
        self.stdout.write(self.style.SUCCESS(("Created" if created else "Updated") + f" update {obj.version}"))
        self.stdout.write(f"Active: {obj.is_active} | Type: {obj.update_type} | Channel: {obj.channel}")
        self.stdout.write(f"Target: {'ALL' if obj.rollout_all_offices else ', '.join(obj.allowed_office_ids)}")
        if obj.local_package_name:
            self.stdout.write(f"Local package: {obj.local_package_name}")
