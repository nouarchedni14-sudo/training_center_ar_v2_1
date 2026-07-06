from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from sync_core.models import CentralOffice, Commune, Wilaya
from sync_core.organization import ensure_default_organization_units, normalize_commune_code, normalize_wilaya_code
from sync_core.services import generate_sync_token, mask_token


class Command(BaseCommand):
    help = "يسجل مكتبًا في الخادم المركزي ويطبع رمز المزامنة الخاص به."

    def add_arguments(self, parser):
        parser.add_argument("--office-id", required=True, help="مثال: office-oran")
        parser.add_argument("--office-name", default="", help="مثال: مكتب وهران")
        parser.add_argument("--server-id", default="", help="مثال: server-oran-01")
        parser.add_argument("--token", default="", help="رمز جاهز، أو اتركه فارغًا لإنشاء رمز جديد")
        parser.add_argument("--inactive", action="store_true", help="إنشاء المكتب معطلًا")
        parser.add_argument("--expires", default="", help="تاريخ انتهاء الترخيص YYYY-MM-DD")
        parser.add_argument("--max-users", type=int, default=5)
        parser.add_argument("--plan", default="standard")
        parser.add_argument("--office-code", default="", help="مثال: DZ38-03801-INSFP01")
        parser.add_argument("--office-alias", default="", help="مثال: DZ38-TIS-INSFP01")
        parser.add_argument("--office-display-name", default="", help="الاسم الرسمي الظاهر في الوثائق")
        parser.add_argument("--wilaya-code", default="", help="مثال: 38")
        parser.add_argument("--commune-code", default="", help="مثال: 03801")
        parser.add_argument("--establishment-type", default="", help="INSFP / CFPA / ANNEXE / DIRECTION")
        parser.add_argument("--establishment-number", default="", help="مثال: 01")

    def handle(self, *args, **options):
        office_id = options["office_id"].strip()
        if not office_id:
            raise CommandError("office-id فارغ")

        expires = None
        if options["expires"]:
            try:
                expires = datetime.strptime(options["expires"], "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("صيغة --expires يجب أن تكون YYYY-MM-DD") from exc

        token = options["token"].strip() or generate_sync_token()
        wilaya = None
        commune = None
        wc = normalize_wilaya_code(options.get("wilaya_code"))
        cc = normalize_commune_code(options.get("commune_code"))
        if wc:
            wilaya = Wilaya.objects.filter(code=wc).first()
        if cc:
            commune = Commune.objects.filter(code=cc).select_related("wilaya").first()
            if commune and not wilaya:
                wilaya = commune.wilaya

        office, created = CentralOffice.objects.update_or_create(
            office_id=office_id,
            defaults={
                "office_code": options["office_code"].strip() or None,
                "office_alias": options["office_alias"].strip(),
                "office_name": options["office_name"].strip(),
                "office_display_name": options["office_display_name"].strip(),
                "wilaya": wilaya,
                "commune": commune,
                "establishment_type": options["establishment_type"].strip().upper(),
                "establishment_number": options["establishment_number"].strip() or "01",
                "server_id": options["server_id"].strip(),
                "sync_token": token,
                "is_active": not options["inactive"],
                "allow_push": True,
                "allow_pull": True,
                "license_status": CentralOffice.LICENSE_ACTIVE,
                "license_expires_at": expires,
                "license_plan": options["plan"].strip() or "standard",
                "max_users": max(0, options["max_users"]),
            },
        )
        ensure_default_organization_units(office)

        self.stdout.write(self.style.SUCCESS("تم إنشاء المكتب." if created else "تم تحديث المكتب."))
        self.stdout.write(f"OFFICE_CODE={office.office_code or ''}")
        self.stdout.write(f"OFFICE_ALIAS={office.office_alias or ''}")
        self.stdout.write(f"OFFICE_ID={office.office_id}")
        self.stdout.write(f"OFFICE_NAME={office.office_name}")
        self.stdout.write(f"OFFICE_DISPLAY_NAME={office.office_display_name or ''}")
        self.stdout.write(f"SERVER_ID={office.server_id}")
        self.stdout.write(f"SYNC_TOKEN={token}")
        self.stdout.write(f"TOKEN_MASKED={mask_token(token)}")
        self.stdout.write(f"LICENSE_EXPIRES_AT={office.license_expires_at}")
        self.stdout.write(f"MAX_USERS={office.max_users}")
