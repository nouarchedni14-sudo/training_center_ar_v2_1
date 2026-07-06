import json
import uuid
import urllib.error
import urllib.request
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from sync_core.models import CentralOffice, CentralSyncEvent
from sync_core.services import normalize_url


class Command(BaseCommand):
    help = "يسحب سجل العمليات من خوادم المكاتب عند تشغيل جهاز المطور، حتى لو لم تدفع المكاتب السجلات تلقائيًا."

    def add_arguments(self, parser):
        parser.add_argument("--office-id", default="", help="اسحب من مكتب واحد فقط")
        parser.add_argument("--all", action="store_true", help="اسحب من كل المكاتب التي لها office_api_url")
        parser.add_argument("--limit", type=int, default=500, help="عدد السجلات في كل طلب")
        parser.add_argument("--reset-cursor", action="store_true", help="ابدأ من الصفر بدل آخر مؤشر محفوظ")
        parser.add_argument("--url", default="", help="رابط خادم مكتب يدوي مثل http://192.168.1.20:8000")
        parser.add_argument("--token", default="", help="رمز السحب اليدوي. إذا تركته فارغًا يستعمل sync_token للمكتب")
        parser.add_argument("--timeout", type=int, default=20)

    def handle(self, *args, **options):
        office_id = (options.get("office_id") or "").strip()
        if office_id:
            offices = list(CentralOffice.objects.filter(office_id=office_id))
            if not offices:
                raise CommandError(f"لم أجد المكتب: {office_id}")
        elif options.get("all"):
            offices = list(CentralOffice.objects.filter(is_active=True, pull_enabled=True).exclude(office_api_url="").order_by("office_id"))
        else:
            raise CommandError("استعمل --office-id office-oran أو --all")

        total_received = 0
        total_duplicates = 0
        total_errors = 0
        for office in offices:
            url = normalize_url(options.get("url") or office.office_api_url)
            if not url:
                self.stdout.write(self.style.WARNING(f"{office.office_id}: لا يوجد office_api_url للسحب"))
                continue
            result = self._pull_one(office, url, options)
            total_received += result["received"]
            total_duplicates += result["duplicates"]
            total_errors += 0 if result["ok"] else 1
            label = self.style.SUCCESS if result["ok"] else self.style.ERROR
            self.stdout.write(label(f"{office.office_id}: received={result['received']} duplicates={result['duplicates']} next_cursor={result.get('next_cursor')} message={result.get('message','')}"))

        self.stdout.write(self.style.SUCCESS(f"DONE received={total_received} duplicates={total_duplicates} errors={total_errors}"))

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {raw[:1000]}") from exc

    def _event_uuid(self, office: CentralOffice, item: dict[str, Any]) -> uuid.UUID:
        raw = str(item.get("event_id") or item.get("source_event_id") or f"audit-{office.office_id}-{item.get('object_pk')}")
        return uuid.uuid5(uuid.NAMESPACE_URL, raw)

    def _pull_one(self, office: CentralOffice, base_url: str, options: dict[str, Any]) -> dict[str, Any]:
        endpoint = normalize_url(base_url) + "/api/audit/export/"
        cursor = "0" if options.get("reset_cursor") else (office.last_pull_cursor or "0")
        token = (options.get("token") or office.sync_token or "").strip()
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "X-Sync-Office": office.office_id,
            "X-Sync-Server": office.server_id or "central-pull",
            "X-Sync-Token": token,
        }
        payload = {"last_cursor": cursor, "limit": int(options.get("limit") or 500)}
        try:
            data = self._post_json(endpoint, payload, headers, int(options.get("timeout") or 20))
            if not data.get("ok"):
                raise RuntimeError(str(data))
            received = 0
            duplicates = 0
            next_cursor = str(data.get("next_cursor") or cursor)
            for item in data.get("events") or []:
                event_uuid = self._event_uuid(office, item)
                obj, created = CentralSyncEvent.objects.get_or_create(
                    source_event_id=event_uuid,
                    defaults={
                        "source_office_id": str(item.get("source_office_id") or office.office_id),
                        "source_server_id": str(item.get("source_server_id") or office.server_id or ""),
                        "app_label": str(item.get("app_label") or "trainees"),
                        "model_name": str(item.get("model_name") or "ComprehensiveAuditLog"),
                        "object_pk": str(item.get("object_pk") or ""),
                        "operation": str(item.get("operation") or "snapshot"),
                        "payload": item.get("payload") or {},
                        "changed_fields": item.get("changed_fields") or [],
                        "payload_hash": str(item.get("payload_hash") or ""),
                        "source_created_at": item.get("created_at") or None,
                        "extra": {"pulled_by_central": True, "office_api_url": base_url},
                    },
                )
                if created:
                    received += 1
                else:
                    duplicates += 1
            office.mark_pulled(cursor=next_cursor, error="")
            return {"ok": True, "received": received, "duplicates": duplicates, "next_cursor": next_cursor, "message": "ok"}
        except Exception as exc:
            office.mark_pulled(cursor=cursor, error=str(exc))
            return {"ok": False, "received": 0, "duplicates": 0, "next_cursor": cursor, "message": str(exc)}
