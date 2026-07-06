from django.core.management.base import BaseCommand
from django.db.models import Count

from sync_core.models import SyncOutbox
from sync_core.services import tracked_model_labels


class Command(BaseCommand):
    help = "يعرض حالة صندوق الإرسال الخاص بالمزامنة المحلية."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("حالة SyncOutbox"))
        total = SyncOutbox.objects.count()
        self.stdout.write(f"إجمالي الأحداث: {total}")
        for row in SyncOutbox.objects.values("status").annotate(count=Count("id")).order_by("status"):
            self.stdout.write(f"- {row['status']}: {row['count']}")

        self.stdout.write("")
        self.stdout.write("النماذج المضبوطة للتتبع:")
        labels = tracked_model_labels()
        if labels:
            for label in labels:
                self.stdout.write(f"- {label}")
        else:
            self.stdout.write("- غير محددة. سيتم تتبع كل التطبيقات غير النظامية، وهذا غير منصوح به.")

        self.stdout.write("")
        self.stdout.write("آخر 10 أحداث:")
        qs = SyncOutbox.objects.order_by("-created_at")[:10]
        if not qs:
            self.stdout.write("لا توجد أحداث بعد.")
            return
        for event in qs:
            self.stdout.write(
                f"{event.created_at:%Y-%m-%d %H:%M:%S} | {event.status} | "
                f"{event.operation} | {event.app_label}.{event.model_name}:{event.object_pk}"
            )
