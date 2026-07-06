from django.core.management.base import BaseCommand, CommandError

from sync_core.applier import apply_received_events


class Command(BaseCommand):
    help = "تطبيق أحداث SyncInbox المستقبلة على قاعدة بيانات المكتب المحلي حسب سياسة التعارضات."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="أقصى عدد أحداث يتم تطبيقها في هذه الدورة.")

    def handle(self, *args, **options):
        try:
            result = apply_received_events(limit=options.get("limit"))
            self.stdout.write(self.style.SUCCESS("تم تطبيق أحداث SyncInbox."))
            self.stdout.write(str(result))
        except Exception as exc:
            raise CommandError(str(exc)) from exc
