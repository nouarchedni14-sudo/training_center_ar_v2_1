from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "يعرض أسماء النماذج التي يمكن وضعها في SYNC_TRACKED_MODELS."

    def add_arguments(self, parser):
        parser.add_argument("--app", default="", help="تصفية حسب اسم التطبيق، مثل trainees")

    def handle(self, *args, **options):
        app_filter = (options.get("app") or "").strip().lower()
        self.stdout.write(self.style.MIGRATE_HEADING("النماذج المتاحة للتتبع"))
        found = False
        for model in sorted(apps.get_models(), key=lambda m: m._meta.label_lower):
            if app_filter and model._meta.app_label.lower() != app_filter:
                continue
            self.stdout.write(f"{model._meta.app_label}.{model.__name__}")
            found = True
        if not found:
            self.stdout.write("لم أجد نماذج مطابقة.")
