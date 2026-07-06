from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("trainees", "0034_attendance_action_archiving"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AttendanceActionDeletionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("program", models.CharField(choices=[("initial", "حضوري أولي"), ("apprentice", "تمهين"), ("evening", "مسائي ومعابر")], max_length=20, verbose_name="النمط")),
                ("month", models.PositiveSmallIntegerField(verbose_name="الشهر")),
                ("year", models.PositiveIntegerField(verbose_name="السنة")),
                ("specialty", models.CharField(blank=True, default="", max_length=200, verbose_name="التخصص وقت الحذف")),
                ("trainee_object_id", models.PositiveIntegerField(verbose_name="معرّف المتكوّن")),
                ("action_type", models.CharField(choices=[("excuse_1", "الإعذار الأول"), ("excuse_2", "الإعذار الثاني"), ("excuse_3", "الإعذار الثالث"), ("summon", "الاستدعاء")], max_length=20, verbose_name="نوع الإجراء")),
                ("deleted_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الحذف")),
                ("batch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_action_deletion_logs", to="trainees.دفعة", verbose_name="الدفعة")),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deleted_attendance_action_logs", to=settings.AUTH_USER_MODEL, verbose_name="حُذف بواسطة")),
                ("trainee_content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype", verbose_name="نوع المتكوّن")),
            ],
            options={
                "verbose_name": "سجل حذف إجراء غياب",
                "verbose_name_plural": "سجلات حذف إجراءات الغياب",
            },
        ),
        migrations.AddConstraint(
            model_name="attendanceactiondeletionlog",
            constraint=models.UniqueConstraint(fields=("program", "year", "month", "batch", "specialty", "trainee_content_type", "trainee_object_id", "action_type"), name="trainees_unique_attendance_action_delete_log_per_scope"),
        ),
        migrations.AddIndex(
            model_name="attendanceactiondeletionlog",
            index=models.Index(fields=["program", "year", "month"], name="trainees_at_program_f44550_idx"),
        ),
    ]
