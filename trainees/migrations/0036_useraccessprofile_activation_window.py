from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trainees", "0035_attendance_action_deletion"),
        ("trainees", "0035_attendance_action_deletion_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccessprofile",
            name="access_enabled",
            field=models.BooleanField(default=True, verbose_name="الصلاحيات مفعلة"),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="access_end_date",
            field=models.DateField(blank=True, null=True, verbose_name="تاريخ نهاية الصلاحية"),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="access_start_date",
            field=models.DateField(blank=True, null=True, verbose_name="تاريخ بداية الصلاحية"),
        ),
    ]
