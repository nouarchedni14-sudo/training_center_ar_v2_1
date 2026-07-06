from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0040_merge_0039_account_audit_and_roles"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="attendanceactiondeletionlog",
            name="trainees_unique_attendance_action_delete_log_per_scope",
        ),
        migrations.RemoveIndex(
            model_name="attendanceactiondeletionlog",
            name="trainees_at_program_f44550_idx",
        ),
        migrations.DeleteModel(
            name="AttendanceActionDeletionLog",
        ),
        migrations.RemoveField(
            model_name="useraccessprofile",
            name="activated_by",
        ),
        migrations.RemoveField(
            model_name="useraccessprofile",
            name="deactivated_by",
        ),
        migrations.RemoveField(
            model_name="useraccessprofile",
            name="suspended_at",
        ),
        migrations.AlterModelOptions(
            name="accessauditlog",
            options={"ordering": ["-created_at", "-id"], "verbose_name": "سجل تدقيق الصلاحيات", "verbose_name_plural": "سجل تدقيق الصلاحيات"},
        ),
        migrations.AlterField(
            model_name="accessauditlog",
            name="actor",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="performed_access_audit_logs", to="auth.user", verbose_name="تم بواسطة"),
        ),
        migrations.AlterField(
            model_name="useraccessprofile",
            name="allowed_weekdays",
            field=models.CharField(blank=True, default="", max_length=50, verbose_name="أيام الأسبوع المسموحة"),
        ),
        migrations.AlterField(
            model_name="useraccessprofile",
            name="grace_period_days",
            field=models.PositiveIntegerField(default=0, verbose_name="فترة السماح بالأيام"),
        ),
        migrations.AlterField(
            model_name="useraccessprofile",
            name="suspended_reason",
            field=models.TextField(blank=True, default="", verbose_name="سبب التعليق المؤقت"),
        ),
        migrations.AlterField(
            model_name="useraccessprofile",
            name="access_start_time",
            field=models.TimeField(blank=True, null=True, verbose_name="وقت بداية السماح اليومي"),
        ),
        migrations.AlterField(
            model_name="useraccessprofile",
            name="access_end_time",
            field=models.TimeField(blank=True, null=True, verbose_name="وقت نهاية السماح اليومي"),
        ),
        migrations.AlterField(
            model_name="useraccessprofile",
            name="access_type",
            field=models.CharField(choices=[("permanent", "دائم"), ("temporary", "مؤقت"), ("trainee", "متربص"), ("shift", "مناوب"), ("visitor", "زائر")], default="permanent", max_length=20, verbose_name="نوع الصلاحية"),
        ),
    ]
