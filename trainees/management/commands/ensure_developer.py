import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from trainees.models import UserAccessProfile


FULL_PERMISSION_FIELDS = [
    "can_access_admin_panel",
    "can_manage_all_programs",
    "can_view_reports",
    "can_export_data",
    "initial_view",
    "initial_add",
    "initial_change",
    "initial_delete",
    "apprentice_view",
    "apprentice_add",
    "apprentice_change",
    "apprentice_delete",
    "evening_view",
    "evening_add",
    "evening_change",
    "evening_delete",
]


class Command(BaseCommand):
    help = "Ensure a fixed developer superuser exists with full application access"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Reset the developer password to the value from DEV_PASSWORD/.env even if the user already exists.",
        )

    def handle(self, *args, **options):
        username = os.getenv("DEV_USERNAME", "developer").strip() or "developer"
        password = os.getenv("DEV_PASSWORD", "developer123")
        email = os.getenv("DEV_EMAIL", "developer@local.test").strip()
        reset_password = options["reset_password"] or os.getenv("DEV_FORCE_PASSWORD_RESET", "0") in {
            "1", "true", "True", "yes", "YES"
        }

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        user_changed = False
        if email and user.email != email:
            user.email = email
            user_changed = True
        if not user.is_active:
            user.is_active = True
            user_changed = True
        if not user.is_staff:
            user.is_staff = True
            user_changed = True
        if not user.is_superuser:
            user.is_superuser = True
            user_changed = True

        if created or reset_password:
            user.set_password(password)
            user_changed = True

        if user_changed:
            user.save()

        profile, _ = UserAccessProfile.objects.get_or_create(user=user)
        profile_changed = False
        if not profile.access_enabled:
            profile.access_enabled = True
            profile_changed = True
        if profile.access_start_date is not None:
            profile.access_start_date = None
            profile_changed = True
        if profile.access_end_date is not None:
            profile.access_end_date = None
            profile_changed = True
        if profile.force_password_change:
            profile.force_password_change = False
            profile_changed = True

        for field_name in FULL_PERMISSION_FIELDS:
            if not getattr(profile, field_name):
                setattr(profile, field_name, True)
                profile_changed = True

        if profile_changed:
            profile.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"تم إنشاء حساب المطور الثابت: {username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"حساب المطور موجود وتم التأكد من صلاحيته: {username}"))

        if created or reset_password:
            self.stdout.write(self.style.WARNING("تم ضبط كلمة المرور من DEV_PASSWORD/.env أو من القيمة الافتراضية الحالية."))
        else:
            self.stdout.write("لم يتم تغيير كلمة المرور الحالية. استخدم --reset-password إذا أردت توحيدها من جديد.")

        self.stdout.write(f"اسم المستخدم: {username}")
        self.stdout.write(f"البريد: {email or '-'}")
        self.stdout.write(
            "التشغيل المقترح على أي جهاز جديد: python manage.py migrate && python manage.py ensure_developer"
        )
