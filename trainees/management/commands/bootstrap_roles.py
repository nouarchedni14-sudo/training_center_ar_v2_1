from django.core.management.base import BaseCommand  # استيراد عناصر محددة من مكتبة/وحدة
from django.contrib.auth.models import Group, Permission  # استيراد عناصر محددة من مكتبة/وحدة
from django.contrib.contenttypes.models import ContentType  # استيراد عناصر محددة من مكتبة/وحدة


ROLE_PERMS = {  # تعيين قيمة لمتغير/إعداد
    # Django superuser bypasses everything, but we still create groups for clarity.
    "Admin": {"add", "change", "delete", "view"},  # سطر كود لتنفيذ منطق/إعداد
    "Manager": {"add", "change", "view"},  # سطر كود لتنفيذ منطق/إعداد
    "Staff": {"add", "change", "view"},  # سطر كود لتنفيذ منطق/إعداد
    # Trainers: view trainees data, plus add/change/view attendance (will exist after migrations)
    "Trainer": {"view"},  # سطر كود لتنفيذ منطق/إعداد
}  # سطر كود لتنفيذ منطق/إعداد


class Command(BaseCommand):  # تعريف كلاس (Class)
    help = "Create default roles/groups and assign model permissions for trainees app"  # تعيين قيمة لمتغير/إعداد

    def handle(self, *args, **options):  # تعريف دالة (Function)
        trainees_cts = ContentType.objects.filter(app_label="trainees")  # تعيين قيمة لمتغير/إعداد
        all_perms = Permission.objects.filter(content_type__in=trainees_cts)  # تعيين قيمة لمتغير/إعداد

        # Try to detect attendance permissions
        attendance_perms = [  # تعيين قيمة لمتغير/إعداد
            p for p in all_perms if p.codename in {"add_attendance", "change_attendance", "view_attendance"}  # سطر كود لتنفيذ منطق/إعداد
        ]  # سطر كود لتنفيذ منطق/إعداد

        for role, actions in ROLE_PERMS.items():  # حلقة تكرار (For)
            group, _ = Group.objects.get_or_create(name=role)  # تعيين قيمة لمتغير/إعداد

            selected = []  # تعيين قيمة لمتغير/إعداد
            for p in all_perms:  # حلقة تكرار (For)
                # Always include attendance perms for Trainer
                if role == "Trainer" and p in attendance_perms:  # شرط (If)
                    selected.append(p)  # سطر كود لتنفيذ منطق/إعداد
                    continue  # سطر كود لتنفيذ منطق/إعداد

                # Regular model permissions by prefix
                if any(p.codename.startswith(f"{act}_") for act in actions):  # شرط (If)
                    selected.append(p)  # سطر كود لتنفيذ منطق/إعداد

            group.permissions.set(selected)  # سطر كود لتنفيذ منطق/إعداد
            group.save()  # سطر كود لتنفيذ منطق/إعداد
            self.stdout.write(self.style.SUCCESS(f"âœ… Group ready: {role} ({len(selected)} permissions)"))  # سطر كود لتنفيذ منطق/إعداد

        self.stdout.write(  # سطر كود لتنفيذ منطق/إعداد
            self.style.SUCCESS(  # سطر كود لتنفيذ منطق/إعداد
                "ðŸŽ‰ Done. Now assign users to groups in /admin/ (Users â†’ Groups) and test permissions."  # سطر كود لتنفيذ منطق/إعداد
            )  # سطر كود لتنفيذ منطق/إعداد
        )  # سطر كود لتنفيذ منطق/إعداد
