# -*- coding: utf-8 -*-
"""
تشغيل هذا الملف بعد عمل --fake للترحيل 0053.
الهدف:
1) التأكد من وجود عمود نوع_التكوين في جدول الدروس المسائية/المعابر.
2) ضبط القيمة الافتراضية وعدم ترك NULL.
3) تصنيف السجلات القديمة إلى مسائي/معابر حسب الكلمة أو مدة التكوين.
4) تنظيف كلمة معابر من اسم التخصص، وتحديد سداسيات المعابر في الأول/الثاني فقط.

طريقة التشغيل من داخل مجلد المشروع:
.venv\Scripts\python manage.py shell --settings=training_center.settings_lan < fix_evening_crossing_after_fake.py
"""
from django.db import connection
from django.db.models import Count

from trainees.models import مسائي_ومعابر
from trainees.evening_training_type import (
    detect_evening_training_type,
    clean_crossing_specialty_label,
    clamp_semester_for_evening_type,
    EVENING_TRAINING_TYPE_CROSSING,
    EVENING_TRAINING_TYPE_EVENING,
)

TABLE_NAME = "trainees_مسائي_ومعابر"
COLUMN_NAME = "نوع_التكوين"
INDEX_NAME = "trainees_مسائي_ومعابر_نوع_التكوين_fea0f3fd"


def qn(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


print("[1/4] التأكد من العمود والفهرس...")
with connection.cursor() as cur:
    cur.execute("SELECT to_regclass(%s)", [TABLE_NAME])
    table_exists = cur.fetchone()[0]
    if not table_exists:
        raise RuntimeError(f"الجدول غير موجود: {TABLE_NAME}")

    cur.execute(
        f"ALTER TABLE {qn(TABLE_NAME)} "
        f"ADD COLUMN IF NOT EXISTS {qn(COLUMN_NAME)} varchar(20)"
    )
    cur.execute(
        f"UPDATE {qn(TABLE_NAME)} "
        f"SET {qn(COLUMN_NAME)} = %s "
        f"WHERE {qn(COLUMN_NAME)} IS NULL OR {qn(COLUMN_NAME)} = %s",
        [EVENING_TRAINING_TYPE_EVENING, ""],
    )
    cur.execute(
        f"ALTER TABLE {qn(TABLE_NAME)} "
        f"ALTER COLUMN {qn(COLUMN_NAME)} SET DEFAULT %s",
        [EVENING_TRAINING_TYPE_EVENING],
    )
    cur.execute(
        f"ALTER TABLE {qn(TABLE_NAME)} "
        f"ALTER COLUMN {qn(COLUMN_NAME)} SET NOT NULL"
    )
    try:
        cur.execute(
            f"CREATE INDEX IF NOT EXISTS {qn(INDEX_NAME)} "
            f"ON {qn(TABLE_NAME)} ({qn(COLUMN_NAME)})"
        )
    except Exception as exc:
        # الفهرس ليس ضروريًا لتشغيل البرنامج. إذا كان الاسم محجوزًا بعلاقة أخرى، نتجاوز فقط.
        print(f"[تنبيه] لم يتم إنشاء الفهرس، ويمكن تجاهل ذلك مؤقتًا: {exc}")

print("[2/4] تصنيف سجلات الدروس المسائية والمعابر...")
model_field_names = {f.name for f in مسائي_ومعابر._meta.fields}
only_fields = [
    name for name in [
        "id",
        "التخصص",
        "النظام",
        "رمز_التخصص",
        "تاريخ_بداية_التكوين",
        "تاريخ_نهاية_التكوين",
        "السداسي",
        "نوع_التكوين",
    ] if name in model_field_names
]

updates = []
update_fields = [name for name in ["نوع_التكوين", "التخصص", "السداسي"] if name in model_field_names]
total = 0
changed = 0
crossing = 0
evening = 0

qs = مسائي_ومعابر.objects.all().only(*only_fields).iterator(chunk_size=1000)
for obj in qs:
    total += 1
    old_type = getattr(obj, "نوع_التكوين", None)
    old_specialty = getattr(obj, "التخصص", None)
    old_semester = getattr(obj, "السداسي", None)

    detected_type = detect_evening_training_type(obj)
    if detected_type == EVENING_TRAINING_TYPE_CROSSING:
        crossing += 1
        new_specialty = clean_crossing_specialty_label(old_specialty)
    else:
        evening += 1
        new_specialty = str(old_specialty or "").strip()

    new_semester = clamp_semester_for_evening_type(old_semester, detected_type)

    if "نوع_التكوين" in model_field_names:
        setattr(obj, "نوع_التكوين", detected_type)
    if "التخصص" in model_field_names:
        setattr(obj, "التخصص", new_specialty)
    if "السداسي" in model_field_names:
        setattr(obj, "السداسي", new_semester)

    if old_type != detected_type or old_specialty != new_specialty or old_semester != new_semester:
        updates.append(obj)
        changed += 1

    if len(updates) >= 1000:
        مسائي_ومعابر.objects.bulk_update(updates, update_fields, batch_size=1000)
        updates = []

if updates:
    مسائي_ومعابر.objects.bulk_update(updates, update_fields, batch_size=1000)

print("[3/4] النتيجة:")
print(f"إجمالي السجلات المفحوصة: {total}")
print(f"دروس مسائية: {evening}")
print(f"معابر: {crossing}")
print(f"سجلات تم تحديثها: {changed}")

print("[4/4] العدّ النهائي من قاعدة البيانات:")
for row in مسائي_ومعابر.objects.values("نوع_التكوين").annotate(n=Count("id")).order_by("نوع_التكوين"):
    print(f"{row['نوع_التكوين']}: {row['n']}")

print("تم الإصلاح بنجاح.")
