from django.core.management.base import BaseCommand
from django.db.models import Count

from sync_core.models import CentralOffice, CentralSyncEvent


class Command(BaseCommand):
    help = "عرض ملخص التحكم المركزي: المكاتب، التراخيص، وأحداث المزامنة."

    def handle(self, *args, **options):
        self.stdout.write("=== Central Control Status ===")
        self.stdout.write(f"Offices: {CentralOffice.objects.count()}")
        self.stdout.write(f"Active offices: {CentralOffice.objects.filter(is_active=True).count()}")
        self.stdout.write(f"Disabled offices: {CentralOffice.objects.filter(is_active=False).count()}")
        self.stdout.write(f"Sync events: {CentralSyncEvent.objects.count()}")
        self.stdout.write("")
        for office in CentralOffice.objects.order_by("office_id"):
            count = CentralSyncEvent.objects.filter(source_office_id=office.office_id).count()
            self.stdout.write(
                f"- {office.office_id} | active={office.is_active} | license={office.effective_license_status} | "
                f"expires={office.license_expires_at} | max_users={office.max_users} | events={count} | last_seen={office.last_seen_at}"
            )
