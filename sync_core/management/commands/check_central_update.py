import json
import urllib.request
import urllib.error

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import SystemConfiguration
from core.services.local_update_service import download_remote_update_and_prepare
from core.services.update_service import central_update_download_headers, check_for_updates, discover_runtime_version
from sync_core.services import ensure_office_identity_from_settings


class Command(BaseCommand):
    help = "فحص وجود تحديث من الخادم المركزي، ويمكن اختياريًا تنزيله وتجهيزه."

    def add_arguments(self, parser):
        parser.add_argument("--version", default="", help="اتركه فارغًا ليستعمل الإصدار الفعلي الحالي")
        parser.add_argument("--channel", default=getattr(settings, "CENTRAL_DEFAULT_UPDATE_CHANNEL", "stable"))
        parser.add_argument("--timeout", type=int, default=int(getattr(settings, "SYNC_WORKER_HTTP_TIMEOUT", 20)))
        parser.add_argument("--prepare", action="store_true", help="تنزيل التحديث وتجهيزه للتطبيق إذا كان متاحًا")

    def handle(self, *args, **options):
        if options.get("prepare"):
            config = SystemConfiguration.get_solo()
            result = check_for_updates(force=True)
            self.stdout.write(json.dumps({k: v for k, v in result.items() if k not in {"config"}}, ensure_ascii=False, indent=2, default=str))
            if not result.get("ok"):
                raise CommandError(result.get("message") or "فشل فحص التحديث المركزي")
            payload = result.get("payload") or {}
            if not payload.get("update_available"):
                self.stdout.write(self.style.SUCCESS("لا يوجد تحديث جديد لهذا المكتب."))
                return
            download_url = str(payload.get("download_url") or config.update_download_url or "").strip()
            if not download_url:
                raise CommandError("يوجد تحديث لكن رابط التنزيل غير متوفر.")
            pending = download_remote_update_and_prepare(
                download_url=download_url,
                current_version=config.current_version or discover_runtime_version(),
                expected_version=str(payload.get("latest_version") or payload.get("version") or config.latest_version or ""),
                expected_sha256=str(payload.get("sha256") or payload.get("checksum") or ""),
                package_name=str(payload.get("package_name") or ""),
                notes=str(payload.get("release_notes") or payload.get("message") or ""),
                request_headers=central_update_download_headers() if payload.get("download_requires_sync_auth") else None,
            )
            self.stdout.write(self.style.SUCCESS(f"تم تنزيل وتجهيز التحديث: {pending.get('version')}"))
            self.stdout.write(f"Script: {pending.get('script_path')}")
            return

        identity, _ = ensure_office_identity_from_settings(create_missing_values=True)
        central_url = (identity.central_url or getattr(settings, "CENTRAL_URL", "")).rstrip("/")
        if not central_url:
            raise CommandError("CENTRAL_URL غير مضبوط في .env")
        if not identity.office_id or not identity.sync_token:
            raise CommandError("OFFICE_ID أو SYNC_TOKEN غير مضبوط")

        url = central_url + "/api/updates/check/"
        payload = {
            "office_id": identity.office_id,
            "server_id": identity.server_id,
            "current_version": options["version"] or discover_runtime_version(),
            "channel": options["channel"],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Sync-Office": identity.office_id,
                "X-Sync-Server": identity.server_id,
                "X-Sync-Token": identity.sync_token,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=options["timeout"]) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise CommandError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc
        except Exception as exc:
            raise CommandError(f"فشل الاتصال بالخادم المركزي: {exc}") from exc

        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("has_update"):
            update = result.get("update") or {}
            self.stdout.write(self.style.WARNING("يوجد تحديث جديد:"))
            self.stdout.write(f"Version: {update.get('version')}")
            self.stdout.write(f"Type: {update.get('update_type')}")
            self.stdout.write(f"URL: {update.get('download_url')}")
            self.stdout.write("للتنزيل والتجهيز: أعد الأمر مع --prepare")
        else:
            self.stdout.write(self.style.SUCCESS("لا يوجد تحديث جديد لهذا المكتب."))
