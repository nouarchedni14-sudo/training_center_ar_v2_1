from django.core.management.base import BaseCommand

from sync_core.models import OfficeIdentity
from sync_core.services import mask_token, read_sync_design_settings


class Command(BaseCommand):
    help = "عرض إعدادات المرحلة الأولى: office_id و server_id و sync_token و central_url."

    def handle(self, *args, **options):
        cfg = read_sync_design_settings()
        self.stdout.write(self.style.MIGRATE_HEADING("إعدادات .env الحالية"))
        self.stdout.write(f"SYNC_MODE: {cfg.mode}")
        self.stdout.write(f"OFFICE_NAME: {cfg.office_name or 'غير محدد'}")
        self.stdout.write(f"OFFICE_ID: {cfg.office_id or 'غير محدد'}")
        self.stdout.write(f"SERVER_ID: {cfg.server_id or 'غير محدد'}")
        self.stdout.write(f"CENTRAL_URL: {cfg.central_url or 'غير محدد'}")
        self.stdout.write(f"CENTRAL_SYNC_ENABLED: {cfg.sync_enabled}")
        self.stdout.write(f"SYNC_TOKEN: {mask_token(cfg.sync_token)}")

        identity = OfficeIdentity.objects.first()
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("القيمة المحفوظة في قاعدة البيانات"))
        if not identity:
            self.stdout.write(self.style.WARNING("لم يتم إنشاء OfficeIdentity بعد. شغّل: python manage.py init_office_identity"))
            return
        self.stdout.write(f"mode: {identity.mode}")
        self.stdout.write(f"office_name: {identity.office_name or 'غير محدد'}")
        self.stdout.write(f"office_id: {identity.office_id}")
        self.stdout.write(f"server_id: {identity.server_id}")
        self.stdout.write(f"central_url: {identity.central_url or 'غير محدد'}")
        self.stdout.write(f"sync_enabled: {identity.sync_enabled}")
        self.stdout.write(f"sync_token: {mask_token(identity.sync_token)}")
