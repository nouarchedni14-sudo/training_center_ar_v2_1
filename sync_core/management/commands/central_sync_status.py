from django.core.management.base import BaseCommand
from django.db.models import Count

from sync_core.models import CentralOffice, CentralSyncEvent


class Command(BaseCommand):
    help = "يعرض حالة الخادم المركزي وأعداد المكاتب والأحداث."

    def handle(self, *args, **options):
        self.stdout.write("=== Central Sync Status ===")
        self.stdout.write(f"Offices: {CentralOffice.objects.count()}")
        self.stdout.write(f"Events:  {CentralSyncEvent.objects.count()}")
        self.stdout.write("")
        for office in CentralOffice.objects.order_by("office_id"):
            count = CentralSyncEvent.objects.filter(source_office_id=office.office_id).count()
            status = "active" if office.is_active else "disabled"
            self.stdout.write(f"- {office.office_id} | {office.office_name} | {status} | events={count} | last_seen={office.last_seen_at}")
