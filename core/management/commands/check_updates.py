from django.core.management.base import BaseCommand

from core.services.update_service import check_for_updates


class Command(BaseCommand):
    help = "يفحص وجود تحديثات جديدة من خادم التحديث إذا كان مفعّلًا"

    def handle(self, *args, **options):
        result = check_for_updates(force=True)
        message = result.get("message") or "تم تنفيذ الفحص."
        if result.get("ok"):
            self.stdout.write(self.style.SUCCESS(message))
        else:
            self.stdout.write(self.style.WARNING(message))
