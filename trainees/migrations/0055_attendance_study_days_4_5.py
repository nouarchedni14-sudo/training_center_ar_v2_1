# Generated manually to support up to five selected study days.

from django.db import migrations, models


WEEKDAY_CHOICES = [
    (6, "الأحد"),
    (0, "الإثنين"),
    (1, "الثلاثاء"),
    (2, "الأربعاء"),
    (3, "الخميس"),
    (4, "الجمعة"),
    (5, "السبت"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0054_daily_attendance_weekday3"),
    ]

    operations = [
        migrations.AddField(
            model_name="كشفغياب",
            name="يوم_الدراسة_4",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=WEEKDAY_CHOICES,
                null=True,
                verbose_name="يوم الدراسة 4",
            ),
        ),
        migrations.AddField(
            model_name="كشفغياب",
            name="يوم_الدراسة_5",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=WEEKDAY_CHOICES,
                null=True,
                verbose_name="يوم الدراسة 5",
            ),
        ),
        migrations.AddField(
            model_name="attendanceslotsheet",
            name="يوم_الدراسة_4",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=WEEKDAY_CHOICES,
                null=True,
                verbose_name="يوم الدراسة 4",
            ),
        ),
        migrations.AddField(
            model_name="attendanceslotsheet",
            name="يوم_الدراسة_5",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=WEEKDAY_CHOICES,
                null=True,
                verbose_name="يوم الدراسة 5",
            ),
        ),
    ]
