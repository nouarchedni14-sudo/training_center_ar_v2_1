# Generated manually to support optional third study day in daily attendance sheets.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0053_evening_crossing_split"),
    ]

    operations = [
        migrations.AddField(
            model_name="كشفغياب",
            name="يوم_الدراسة_3",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[
                    (6, "الأحد"),
                    (0, "الإثنين"),
                    (1, "الثلاثاء"),
                    (2, "الأربعاء"),
                    (3, "الخميس"),
                    (4, "الجمعة"),
                    (5, "السبت"),
                ],
                null=True,
                verbose_name="يوم الدراسة 3",
            ),
        ),
    ]
