from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from sync_core.models import CentralOffice


class Command(BaseCommand):
    help = "تعديل ترخيص وصلاحيات مكتب من سطر الأوامر على الخادم المركزي."

    def add_arguments(self, parser):
        parser.add_argument("--office-id", required=True)
        parser.add_argument("--enable", action="store_true")
        parser.add_argument("--disable", action="store_true")
        parser.add_argument("--allow-push", choices=["0", "1"])
        parser.add_argument("--allow-pull", choices=["0", "1"])
        parser.add_argument("--expires")
        parser.add_argument("--status", choices=["active", "trial", "expired", "suspended"])
        parser.add_argument("--plan", default=None)
        parser.add_argument("--max-users", type=int)
        parser.add_argument("--reason", default="")
        parser.add_argument("--feature", action="append", default=[], help="صيغة key=value مثل trainees_delete=false")

    def handle(self, *args, **options):
        office = CentralOffice.objects.filter(office_id=options["office_id"]).first()
        if not office:
            raise CommandError("المكتب غير موجود في الخادم المركزي.")

        if options["enable"]:
            office.is_active = True
            office.disabled_reason = ""
        if options["disable"]:
            office.is_active = False
            office.disabled_reason = options["reason"] or "تم التعطيل من طرف المطور"

        if options["allow_push"] is not None:
            office.allow_push = options["allow_push"] == "1"
        if options["allow_pull"] is not None:
            office.allow_pull = options["allow_pull"] == "1"
        if options["status"]:
            office.license_status = options["status"]
        if options["plan"] is not None:
            office.license_plan = options["plan"]
        if options["max_users"] is not None:
            office.max_users = max(0, options["max_users"])
        if options["expires"]:
            try:
                office.license_expires_at = datetime.strptime(options["expires"], "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("صيغة تاريخ الانتهاء يجب أن تكون YYYY-MM-DD") from exc

        flags = dict(office.feature_flags or {})
        for item in options["feature"]:
            if "=" not in item:
                raise CommandError("--feature يجب أن تكون key=value")
            key, value = item.split("=", 1)
            value = value.strip().lower()
            if value in {"1", "true", "yes", "on"}:
                flags[key.strip()] = True
            elif value in {"0", "false", "no", "off"}:
                flags[key.strip()] = False
            else:
                flags[key.strip()] = value
        office.feature_flags = flags

        office.save()
        self.stdout.write(self.style.SUCCESS("تم تحديث المكتب بنجاح."))
        self.stdout.write(f"office_id={office.office_id}")
        self.stdout.write(f"is_active={office.is_active}")
        self.stdout.write(f"license_status={office.effective_license_status}")
        self.stdout.write(f"expires={office.license_expires_at}")
        self.stdout.write(f"max_users={office.max_users}")
        self.stdout.write(f"features={office.feature_flags}")
