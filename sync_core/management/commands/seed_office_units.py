from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sync_core.models import CentralOffice
from sync_core.organization import ensure_default_organization_units


class Command(BaseCommand):
    help = "إنشاء الهيكل الإداري الداخلي الافتراضي للمؤسسات حسب نوعها."

    def add_arguments(self, parser):
        parser.add_argument("--office-id", default="", help="مكتب واحد فقط. اتركه فارغًا مع --all لكل المكاتب.")
        parser.add_argument("--all", action="store_true", help="تطبيق على كل المكاتب.")
        parser.add_argument("--force", action="store_true", help="حذف الوحدات الحالية وإعادة إنشائها.")
        parser.add_argument("--quiet", action="store_true")

    def handle(self, *args, **options):
        if options["office_id"]:
            qs = CentralOffice.objects.filter(office_id=options["office_id"])
            if not qs.exists():
                raise CommandError("المكتب غير موجود.")
        elif options["all"]:
            qs = CentralOffice.objects.all()
        else:
            raise CommandError("استعمل --office-id أو --all")

        total = 0
        with transaction.atomic():
            for office in qs:
                total += ensure_default_organization_units(office, force=options["force"])
        if not options["quiet"]:
            self.stdout.write(self.style.SUCCESS(f"تم تجهيز/تحديث الوحدات الإدارية. عدد الوحدات الجديدة: {total}"))
