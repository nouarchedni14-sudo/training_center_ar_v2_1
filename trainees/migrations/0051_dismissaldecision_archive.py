# Generated for automatic dismissal-decision archiving
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0050_add_program_decision_number"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="dismissaldecision",
            name="trainees_unique_dismissal_decision_per_trainee",
        ),
        migrations.AddField(
            model_name="dismissaldecision",
            name="is_archived",
            field=models.BooleanField(default=False, verbose_name="مؤرشف"),
        ),
        migrations.AddField(
            model_name="dismissaldecision",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الأرشفة"),
        ),
        migrations.AddIndex(
            model_name="dismissaldecision",
            index=models.Index(fields=["program", "decision_scope", "is_archived"], name="trainees_di_program_41b6ac_idx"),
        ),
        migrations.AddIndex(
            model_name="dismissaldecision",
            index=models.Index(fields=["trainee_content_type", "trainee_object_id", "is_archived"], name="trainees_di_trainee_c872d5_idx"),
        ),
    ]
