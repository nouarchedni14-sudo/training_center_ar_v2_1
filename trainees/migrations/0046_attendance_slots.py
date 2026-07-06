# Generated manually for attendance slots feature
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("trainees", "0045_sanctionrecord"),
    ]

    operations = [
        migrations.CreateModel(
            name="AttendanceSlotSheet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("البرنامج", models.CharField(choices=[("initial", "الحضوري الأولي"), ("apprentice", "التمهين"), ("evening", "المسائي/المعابر")], max_length=20, verbose_name="النمط")),
                ("التخصص", models.CharField(blank=True, default="", max_length=200, verbose_name="التخصص")),
                ("الشهر", models.PositiveSmallIntegerField(verbose_name="الشهر")),
                ("السنة", models.PositiveIntegerField(verbose_name="السنة")),
                ("يوم_الدراسة_1", models.PositiveSmallIntegerField(blank=True, choices=[(6, "الأحد"), (0, "الإثنين"), (1, "الثلاثاء"), (2, "الأربعاء"), (3, "الخميس"), (4, "الجمعة"), (5, "السبت")], null=True, verbose_name="يوم الدراسة 1")),
                ("يوم_الدراسة_2", models.PositiveSmallIntegerField(blank=True, choices=[(6, "الأحد"), (0, "الإثنين"), (1, "الثلاثاء"), (2, "الأربعاء"), (3, "الخميس"), (4, "الجمعة"), (5, "السبت")], null=True, verbose_name="يوم الدراسة 2")),
                ("يوم_الدراسة_3", models.PositiveSmallIntegerField(blank=True, choices=[(6, "الأحد"), (0, "الإثنين"), (1, "الثلاثاء"), (2, "الأربعاء"), (3, "الخميس"), (4, "الجمعة"), (5, "السبت")], null=True, verbose_name="يوم الدراسة 3")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_slot_sheets_created", to=settings.AUTH_USER_MODEL, verbose_name="أنشئ بواسطة")),
                ("الدفعة", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_slot_sheets", to="trainees.دفعة", verbose_name="الدفعة")),
            ],
            options={
                "verbose_name": "جدول غياب بالحصة",
                "verbose_name_plural": "جداول الغياب بالحصة",
                "ordering": ["-السنة", "-الشهر", "البرنامج", "التخصص"],
            },
        ),
        migrations.CreateModel(
            name="AttendanceSlotCell",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trainee_id", models.PositiveIntegerField(verbose_name="معرّف المتكوّن")),
                ("التاريخ", models.DateField(verbose_name="التاريخ")),
                ("رقم_الحصة", models.PositiveSmallIntegerField(verbose_name="رقم الحصة")),
                ("الحالة", models.CharField(choices=[("present", "حاضر"), ("absent", "غائب")], default="present", max_length=20, verbose_name="الحالة")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("الكشف", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="trainees.attendanceslotsheet", verbose_name="جدول الحصص")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendance_slot_cells_recorded", to=settings.AUTH_USER_MODEL, verbose_name="سجل بواسطة")),
            ],
            options={
                "verbose_name": "خلية غياب بالحصة",
                "verbose_name_plural": "خلايا الغياب بالحصة",
                "ordering": ["التاريخ", "trainee_id", "رقم_الحصة"],
            },
        ),
        migrations.AddIndex(
            model_name="attendanceslotsheet",
            index=models.Index(fields=["البرنامج", "السنة", "الشهر"], name="trainees_sl_program_72cf55_idx"),
        ),
        migrations.AddIndex(
            model_name="attendanceslotsheet",
            index=models.Index(fields=["البرنامج", "الدفعة", "التخصص", "السنة", "الشهر"], name="trainees_sl_program_3e8621_idx"),
        ),
        migrations.AddIndex(
            model_name="attendanceslotcell",
            index=models.Index(fields=["الكشف", "التاريخ", "رقم_الحصة"], name="trainees_sl_660889_idx"),
        ),
        migrations.AddIndex(
            model_name="attendanceslotcell",
            index=models.Index(fields=["الكشف", "trainee_id", "التاريخ", "رقم_الحصة"], name="trainees_sl_7e80cf_idx"),
        ),
        migrations.AddConstraint(
            model_name="attendanceslotcell",
            constraint=models.UniqueConstraint(fields=("الكشف", "trainee_id", "التاريخ", "رقم_الحصة"), name="trainees_unique_attendance_slot_cell"),
        ),
    ]
