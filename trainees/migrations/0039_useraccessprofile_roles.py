
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0038_fix_accessauditlog_schema"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccessprofile",
            name="role_code",
            field=models.CharField(
                choices=[
                    ("general_manager", "مدير عام"),
                    ("branch_manager", "مدير فرع"),
                    ("registration_officer", "موظف تسجيل"),
                    ("accountant", "محاسب"),
                    ("trainer", "مكون / مدرب"),
                    ("read_only", "مراقب"),
                ],
                default="read_only",
                max_length=40,
                verbose_name="الدور الجاهز",
            ),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="is_customized",
            field=models.BooleanField(default=False, verbose_name="تم تخصيص الصلاحيات يدويًا"),
        ),
    ]
