# -*- coding: utf-8 -*-
from django.db import migrations, models
import re

EVENING = "مسائي"
CROSSING = "معابر"


def _duration_months(start, end):
    if not start or not end:
        return None
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day >= start.day:
        months += 1
    return months


def _clean_specialty(value):
    text = str(value or "").replace("\u00A0", " ").strip()
    if not text:
        return ""
    text = re.sub(r"\s*(?:[-–—_/\\|،,؛;:]*\s*)?(?:معابر|معبر)\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—_/\\|،,؛;:")
    return text.strip()


def classify_existing_evening_rows(apps, schema_editor):
    """تصنيف السجلات القديمة.

    ملاحظة مهمة: لا نعتمد على القيمة الافتراضية "مسائي" الموجودة في العمود الجديد،
    لأن كل السجلات القديمة ستأخذها تلقائياً عند إنشاء العمود. لذلك نعتمد على
    كلمة معابر أو مدة التكوين فقط.
    """
    Trainee = apps.get_model("trainees", "مسائي_ومعابر")
    rows = []
    for obj in Trainee.objects.all().only(
        "id", "التخصص", "النظام", "رمز_التخصص",
        "تاريخ_بداية_التكوين", "تاريخ_نهاية_التكوين", "السداسي", "نوع_التكوين",
    ).iterator(chunk_size=1000):
        joined = f"{obj.التخصص or ''} {obj.النظام or ''} {getattr(obj, 'رمز_التخصص', '') or ''}"
        months = _duration_months(obj.تاريخ_بداية_التكوين, obj.تاريخ_نهاية_التكوين)
        training_type = CROSSING if ("معابر" in joined or "معبر" in joined or (months is not None and months <= 14)) else EVENING
        obj.نوع_التكوين = training_type
        obj.التخصص = _clean_specialty(obj.التخصص)
        if training_type == CROSSING and obj.السداسي not in ("", None, "الأول", "الثاني"):
            obj.السداسي = "الثاني"
        rows.append(obj)
        if len(rows) >= 1000:
            Trainee.objects.bulk_update(rows, ["نوع_التكوين", "التخصص", "السداسي"], batch_size=1000)
            rows = []
    if rows:
        Trainee.objects.bulk_update(rows, ["نوع_التكوين", "التخصص", "السداسي"], batch_size=1000)


PROGRAM_CHOICES = [
    ("initial", "حضوري أولي"),
    ("apprentice", "تمهين"),
    ("evening", "دروس مسائية"),
    ("crossing", "معابر"),
]

SLOT_PROGRAM_CHOICES = [
    ("initial", "الحضوري الأولي"),
    ("apprentice", "التمهين"),
    ("evening", "الدروس المسائية"),
    ("crossing", "المعابر"),
]

CUSTOM_FIELD_PROGRAM_CHOICES = [
    ("all", "كل الأنماط"),
    ("initial", "حضوري أولي"),
    ("apprentice", "تمهين"),
    ("evening", "دروس مسائية"),
    ("crossing", "معابر"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0052_backfill_dismissal_decisions"),
    ]

    operations = [
        # استعملنا SeparateDatabaseAndState حتى لا يفشل PostgreSQL إذا كان العمود أو الفهرس
        # موجودين جزئياً من محاولة سابقة. هذا يحل خطأ DuplicateTable الخاص بالفهرس.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "trainees_مسائي_ومعابر" ADD COLUMN IF NOT EXISTS "نوع_التكوين" varchar(20);',
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql='UPDATE "trainees_مسائي_ومعابر" SET "نوع_التكوين" = \'مسائي\' WHERE "نوع_التكوين" IS NULL OR "نوع_التكوين" = \'\';',
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE "trainees_مسائي_ومعابر" ALTER COLUMN "نوع_التكوين" SET DEFAULT \'مسائي\';',
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE "trainees_مسائي_ومعابر" ALTER COLUMN "نوع_التكوين" SET NOT NULL;',
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql='CREATE INDEX IF NOT EXISTS "trainees_مسائي_ومعابر_نوع_التكوين_fea0f3fd" ON "trainees_مسائي_ومعابر" ("نوع_التكوين");',
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="مسائي_ومعابر",
                    name="نوع_التكوين",
                    field=models.CharField(
                        choices=[("مسائي", "دروس مسائية"), ("معابر", "معابر")],
                        db_index=True,
                        default="مسائي",
                        max_length=20,
                        verbose_name="نوع التكوين",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="كشفغياب",
            name="البرنامج",
            field=models.CharField(choices=PROGRAM_CHOICES, max_length=20, verbose_name="النمط"),
        ),
        migrations.AlterField(
            model_name="attendanceaction",
            name="program",
            field=models.CharField(choices=PROGRAM_CHOICES, max_length=20, verbose_name="النمط"),
        ),
        migrations.AlterField(
            model_name="attendanceactiondeletion",
            name="program",
            field=models.CharField(choices=PROGRAM_CHOICES, max_length=20, verbose_name="النمط"),
        ),
        migrations.AlterField(
            model_name="attendancestatsnapshot",
            name="program",
            field=models.CharField(choices=PROGRAM_CHOICES, max_length=20, verbose_name="النمط"),
        ),
        migrations.AlterField(
            model_name="customfield",
            name="program",
            field=models.CharField(choices=CUSTOM_FIELD_PROGRAM_CHOICES, default="all", max_length=20, verbose_name="النمط"),
        ),
        migrations.AlterField(
            model_name="dismissaldecision",
            name="program",
            field=models.CharField(choices=PROGRAM_CHOICES, max_length=20, verbose_name="النمط"),
        ),
        migrations.AlterField(
            model_name="sanctionrecord",
            name="program",
            field=models.CharField(choices=PROGRAM_CHOICES, max_length=20, verbose_name="النمط"),
        ),
        migrations.AlterField(
            model_name="summonsrecord",
            name="program",
            field=models.CharField(choices=PROGRAM_CHOICES, max_length=20, verbose_name="النمط"),
        ),
        migrations.AlterField(
            model_name="attendanceslotsheet",
            name="البرنامج",
            field=models.CharField(choices=SLOT_PROGRAM_CHOICES, max_length=20, verbose_name="النمط"),
        ),
        migrations.RunPython(classify_existing_evening_rows, migrations.RunPython.noop),
    ]
