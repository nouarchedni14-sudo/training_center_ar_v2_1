from django.db import migrations, models


def mark_existing_slot_actions(apps, schema_editor):
    AttendanceAction = apps.get_model("trainees", "AttendanceAction")
    AttendanceAction.objects.filter(notes__icontains="جدول الغياب بالحصة").update(source="slots")
    AttendanceAction.objects.filter(threshold_value__gte=12).update(source="slots")


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0047_summonsrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendanceaction",
            name="source",
            field=models.CharField(choices=[("daily", "غيابات بالأيام"), ("slots", "غيابات بالحصة")], default="daily", max_length=20, verbose_name="مصدر الإجراء"),
        ),
        migrations.AddField(
            model_name="attendanceactiondeletion",
            name="source",
            field=models.CharField(choices=[("daily", "غيابات بالأيام"), ("slots", "غيابات بالحصة")], default="daily", max_length=20, verbose_name="مصدر الإجراء"),
        ),
        migrations.RunPython(mark_existing_slot_actions, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="attendanceaction",
            name="trainees_unique_attendance_action_per_scope",
        ),
        migrations.RemoveConstraint(
            model_name="attendanceactiondeletion",
            name="trainees_unique_attendance_action_deletion_per_scope",
        ),
        migrations.AddConstraint(
            model_name="attendanceaction",
            constraint=models.UniqueConstraint(fields=("source", "program", "year", "month", "batch", "specialty", "trainee_content_type", "trainee_object_id", "action_type"), name="trainees_unique_attendance_action_per_scope"),
        ),
        migrations.AddConstraint(
            model_name="attendanceactiondeletion",
            constraint=models.UniqueConstraint(fields=("source", "program", "year", "month", "batch", "specialty", "trainee_content_type", "trainee_object_id", "action_type"), name="trainees_unique_attendance_action_deletion_per_scope"),
        ),
        migrations.AddIndex(
            model_name="attendanceaction",
            index=models.Index(fields=["source", "program", "year", "month", "action_type"], name="trainees_at_src_ymt_idx"),
        ),
        migrations.AddIndex(
            model_name="attendanceactiondeletion",
            index=models.Index(fields=["source", "program", "year", "month"], name="trainees_del_src_ym_idx"),
        ),
    ]
