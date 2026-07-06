from django.core.management.base import BaseCommand

from core.services.backup_service import create_database_backup


class Command(BaseCommand):
    help = "إنشاء نسخة احتياطية لقاعدة البيانات الحالية."

    def handle(self, *args, **options):
        backup_path = create_database_backup()
        self.stdout.write(self.style.SUCCESS(f"تم إنشاء النسخة الاحتياطية: {backup_path}"))
