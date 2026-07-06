from django.core.management.base import BaseCommand

from sync_core.applier import conflict_summary
from sync_core.models import SyncConflict


class Command(BaseCommand):
    help = "عرض ملخص تعارضات المزامنة المحفوظة في SyncConflict."

    def add_arguments(self, parser):
        parser.add_argument("--show", type=int, default=10, help="عدد آخر التعارضات المعروضة.")

    def handle(self, *args, **options):
        summary = conflict_summary()
        self.stdout.write("ملخص التعارضات:")
        for key, value in summary.items():
            self.stdout.write(f"  {key}: {value}")

        limit = max(0, int(options.get("show") or 0))
        if limit:
            self.stdout.write("\nآخر التعارضات:")
            for conflict in SyncConflict.objects.order_by("-created_at")[:limit]:
                self.stdout.write(
                    f"- {conflict.created_at} | {conflict.status} | "
                    f"{conflict.app_label}.{conflict.model_name}:{conflict.object_pk} | {conflict.reason}"
                )
