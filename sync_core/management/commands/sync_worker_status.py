from django.core.management.base import BaseCommand
from django.db.models import Count

from sync_core.models import SyncInbox, SyncOutbox, SyncState
from sync_core.services import ensure_office_identity_from_settings, mask_token


class Command(BaseCommand):
    help = "يعرض حالة عامل المزامنة المحلي وصناديق الإرسال والاستقبال."

    def handle(self, *args, **options):
        identity, _ = ensure_office_identity_from_settings(create_missing_values=True)
        self.stdout.write("=== Office Sync Identity ===")
        self.stdout.write(f"office_id      : {identity.office_id}")
        self.stdout.write(f"office_name    : {identity.office_name}")
        self.stdout.write(f"server_id      : {identity.server_id}")
        self.stdout.write(f"central_url    : {identity.central_url}")
        self.stdout.write(f"sync_enabled   : {identity.sync_enabled}")
        self.stdout.write(f"sync_token     : {mask_token(identity.sync_token)}")

        self.stdout.write("\n=== Outbox ===")
        for row in SyncOutbox.objects.values("status").annotate(total=Count("id")).order_by("status"):
            self.stdout.write(f"{row['status']}: {row['total']}")

        self.stdout.write("\n=== Inbox ===")
        for row in SyncInbox.objects.values("status").annotate(total=Count("id")).order_by("status"):
            self.stdout.write(f"{row['status']}: {row['total']}")

        self.stdout.write("\n=== Sync State ===")
        for state in SyncState.objects.order_by("direction", "scope"):
            self.stdout.write(
                f"{state.direction}/{state.scope}: cursor={state.last_cursor or '-'} "
                f"success={state.last_success_at or '-'} error={state.last_error or '-'}"
            )
