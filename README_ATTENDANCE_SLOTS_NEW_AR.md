# نظام الغيابات الجديد بالحصة

تمت إضافة نظام جديد مستقل عن الجداول القديمة.

## الصفحات القديمة تبقى كما هي

- attendance/initial/
- attendance/apprentice/
- attendance/evening/

## الصفحات الجديدة

- attendance/initial-slots/
- attendance/apprentice-slots/
- attendance/evening-slots/

وتوجد كذلك روابط مختصرة:

- attendance-slots/initial/
- attendance-slots/apprentice/
- attendance-slots/evening/

## القاعدة الرسمية الجديدة

عدد الحصص البيداغوجية لكل المتكونين = عدد المتكونين غير المشطوبين × عدد الأيام الظاهرة × 4.

نسبة الغياب = مجموع الغيابات بالحصة ÷ عدد الحصص البيداغوجية لكل المتكونين × 100.

## الملفات الجديدة الأساسية

- trainees/attendance_slots_models.py
- trainees/attendance_slots_common.py
- trainees/attendance_initial_slots.py
- trainees/attendance_apprentice_slots.py
- trainees/attendance_evening_slots.py
- trainees/templates/trainees/attendance_slots_grid.html
- trainees/templates/trainees/attendance_slots_stats.html
- trainees/migrations/0046_attendance_slots.py

## ملاحظات مهمة

- النظام الجديد لا يستعمل جدول الغيابات القديم.
- كل يوم في الجدول الجديد مقسم إلى أربع حصص: ح1، ح2، ح3، ح4.
- الحالات المتاحة في النظام الجديد: حاضر / غائب فقط.
- المتكونون المشطوبون والمفصولون والمنقطعون لا يظهرون في الجداول الجديدة.
- يجب تشغيل migrate بعد وضع الملفات.

أمر الترحيل المقترح على جهاز المكتب:

```bat
cd /d D:\training_center_ar_v2_1
set APP_DATA_DIR=C:\TrainingCenterData_Tissemsilt
.venv\Scripts\python.exe manage.py migrate --settings=training_center.settings_lan
```
