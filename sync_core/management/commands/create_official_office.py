from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sync_core.models import CentralOffice, Commune, Wilaya
from sync_core.organization import (
    build_database_name,
    build_data_dir,
    build_office_alias,
    build_office_code,
    build_office_id,
    build_office_name,
    build_server_id,
    ensure_default_organization_units,
    normalize_establishment_number,
    normalize_establishment_type,
    normalize_commune_code,
    normalize_wilaya_code,
)
from sync_core.services import generate_sync_token, mask_token


class Command(BaseCommand):
    help = "إنشاء مؤسسة/مكتب رسمي مركزيًا اعتمادًا على كود الولاية والبلدية ونوع المؤسسة."

    def add_arguments(self, parser):
        parser.add_argument("--wilaya-code", required=True, help="مثال: 38")
        parser.add_argument("--commune-code", required=True, help="مثال: 03801")
        parser.add_argument("--type", required=True, dest="etype", help="INSFP / CFPA / ANNEXE / DIRECTION")
        parser.add_argument("--number", default="01", help="رقم المؤسسة داخل نفس البلدية، مثال 01 أو 02")
        parser.add_argument("--display-name", default="", help="الاسم الرسمي العربي الظاهر للمؤسسة")
        parser.add_argument("--office-api-url", default="")
        parser.add_argument("--max-users", type=int, default=5)
        parser.add_argument("--token", default="", help="رمز جاهز أو اتركه فارغًا للتوليد")
        parser.add_argument("--force", action="store_true", help="تحديث المكتب إذا كان موجودًا")

    def handle(self, *args, **options):
        wc = normalize_wilaya_code(options["wilaya_code"])
        cc = normalize_commune_code(options["commune_code"])
        et = normalize_establishment_type(options["etype"])
        num = normalize_establishment_number(options["number"])
        if not wc or not cc:
            raise CommandError("كود الولاية أو البلدية غير صحيح.")
        try:
            wilaya = Wilaya.objects.get(code=wc)
            commune = Commune.objects.select_related("wilaya").get(code=cc)
        except Wilaya.DoesNotExist as exc:
            raise CommandError("الولاية غير موجودة. شغّل import_algeria_cities أولًا.") from exc
        except Commune.DoesNotExist as exc:
            raise CommandError("البلدية غير موجودة. شغّل import_algeria_cities أولًا.") from exc
        if commune.wilaya_id != wilaya.id:
            raise CommandError("البلدية لا تنتمي إلى الولاية المختارة.")

        office_code = build_office_code(wc, cc, et, num)
        office_id = build_office_id(office_code)
        server_id = build_server_id(office_code)
        token = options["token"].strip() or generate_sync_token()
        defaults = {
            "office_code": office_code,
            "office_alias": build_office_alias(wc, commune.name_latin, et, num),
            "office_name": build_office_name(commune.name_latin, et, num),
            "office_display_name": options["display_name"].strip() or f"{et} {num} - {commune.name_ar}",
            "server_id": server_id,
            "wilaya": wilaya,
            "commune": commune,
            "establishment_type": et,
            "establishment_number": num,
            "office_api_url": options["office_api_url"].strip(),
            "sync_token": token,
            "is_active": True,
            "allow_push": True,
            "allow_pull": True,
            "pull_enabled": True,
            "max_users": int(options["max_users"]),
        }
        with transaction.atomic():
            if CentralOffice.objects.filter(office_id=office_id).exists() and not options["force"]:
                raise CommandError("المكتب موجود مسبقًا. استعمل --force للتحديث.")
            office, created = CentralOffice.objects.update_or_create(office_id=office_id, defaults=defaults)
            ensure_default_organization_units(office)

        env_text = f"""WILAYA_CODE={wc}
COMMUNE_CODE={cc}
OFFICE_CODE={office_code}
OFFICE_ALIAS={office.office_alias}
OFFICE_NAME={office.office_name}
OFFICE_DISPLAY_NAME={office.office_display_name}
OFFICE_ID={office.office_id}
SERVER_ID={office.server_id}
SYNC_TOKEN={token}
"""
        self.stdout.write(self.style.SUCCESS("تم إنشاء/تحديث المؤسسة الرسمية."))
        self.stdout.write(f"الحالة: {'إنشاء جديد' if created else 'تحديث'}")
        self.stdout.write(env_text)
        self.stdout.write(f"TOKEN_MASKED={mask_token(token)}")
        self.stdout.write(f"DATA_DIR={build_data_dir(office_code)}")
        self.stdout.write(f"DATABASE={build_database_name(office_code)}")
