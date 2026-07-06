from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0033_attendance_actions"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendanceaction",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة"),
        ),
        migrations.AddField(
            model_name="attendanceaction",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="مؤرشف"),
        ),
        migrations.AddIndex(
            model_name="attendanceaction",
            index=models.Index(fields=["program", "is_archived"], name="trainees_at_program_4e3284_idx"),
        ),
    ]
