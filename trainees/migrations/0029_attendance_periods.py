from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0028_كشفغياب_خليةغياب_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="خليةغياب",
            name="الفترة",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="الفترة"),
        ),
        migrations.RemoveConstraint(
            model_name="خليةغياب",
            name="trainees_unique_attendance_cell",
        ),
        migrations.AddConstraint(
            model_name="خليةغياب",
            constraint=models.UniqueConstraint(fields=("الكشف", "trainee_id", "التاريخ", "الفترة"), name="trainees_unique_attendance_cell_period"),
        ),
        migrations.AddIndex(
            model_name="خليةغياب",
            index=models.Index(fields=["الكشف", "التاريخ", "الفترة"], name="trainees_att_cell_period_idx"),
        ),
    ]
