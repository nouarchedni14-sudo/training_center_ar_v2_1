from django.core.management.base import BaseCommand

from sync_core.services import ensure_office_identity_from_settings, mask_token


class Command(BaseCommand):
    help = "إنشاء/تحديث هوية خادم المكتب المحلي من إعدادات .env للمرحلة الأولى من المزامنة."

    def handle(self, *args, **options):
        identity, created = ensure_office_identity_from_settings(create_missing_values=True)
        self.stdout.write(self.style.SUCCESS("تم تجهيز هوية المزامنة."))
        self.stdout.write(f"الحالة: {'إنشاء جديد' if created else 'تحديث/قراءة الموجود'}")
        self.stdout.write(f"نمط التشغيل: {identity.mode}")
        self.stdout.write(f"اسم المكتب: {identity.office_name or 'غير محدد'}")
        self.stdout.write(f"office_id: {identity.office_id}")
        self.stdout.write(f"server_id: {identity.server_id}")
        self.stdout.write(f"central_url: {identity.central_url or 'غير محدد'}")
        self.stdout.write(f"sync_enabled: {identity.sync_enabled}")
        self.stdout.write(f"sync_token: {mask_token(identity.sync_token)}")
