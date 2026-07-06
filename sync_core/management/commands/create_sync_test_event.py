from django.core.management.base import BaseCommand

from sync_core.models import OfficeIdentity, SyncOutbox
from sync_core.services import create_outbox_event, ensure_office_identity_from_settings


class _FakeMeta:
    app_label = "sync_core"
    model_name = "manualtest"
    concrete_fields = []


class _FakeInstance:
    pk = "manual-test"
    _meta = _FakeMeta()


class Command(BaseCommand):
    help = "ينشئ حدث اختبار يدوي داخل SyncOutbox للتأكد من أن الجداول تعمل."

    def handle(self, *args, **options):
        ensure_office_identity_from_settings(create_missing_values=True)
        fake = _FakeInstance()
        event = create_outbox_event(
            fake,
            SyncOutbox.OP_SNAPSHOT,
            payload={"message": "اختبار يدوي لصندوق الإرسال", "source": "create_sync_test_event"},
        )
        if event:
            self.stdout.write(self.style.SUCCESS(f"تم إنشاء حدث اختبار: {event.event_id}"))
        else:
            identity = OfficeIdentity.objects.first()
            if identity:
                self.stdout.write(self.style.WARNING("لم يتم إنشاء الحدث. تأكد أن SYNC_TRACKING_ENABLED=1 في ملف .env."))
            else:
                self.stdout.write(self.style.ERROR("لم أتمكن من قراءة هوية المكتب."))
