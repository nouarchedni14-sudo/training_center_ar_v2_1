# دليل الهيكل الرسمي للمكاتب والمؤسسات

هذا التعديل يعتمد تسمية رسمية قابلة للتوسع لكل الولايات والبلديات والمؤسسات داخل نفس البلدية.

## القاعدة النهائية

```env
OFFICE_CODE = الدولة + كود الولاية + كود البلدية + نوع المؤسسة + رقم المؤسسة
```

أمثلة:

```env
DZ38-03801-INSFP01
DZ38-03801-INSFP02
DZ38-03802-CFPA01
DZ38-03811-CFPA02
DZ38-03811-ANNEXE01
```

## مثال: بلدية تيسمسيلت

المعهد الأول:

```env
WILAYA_CODE=38
COMMUNE_CODE=03801
OFFICE_CODE=DZ38-03801-INSFP01
OFFICE_ALIAS=DZ38-TIS-INSFP01
OFFICE_NAME=Tissemsilt_INSFP01
OFFICE_DISPLAY_NAME=المعهد الوطني المتخصص في التكوين المهني الشهيد تاج الدين حامد عبد الوهاب - تيسمسيلت
OFFICE_ID=office_dz38_03801_insfp01
SERVER_ID=server_dz38_03801_insfp01_main
```

المعهد الثاني داخل نفس البلدية:

```env
WILAYA_CODE=38
COMMUNE_CODE=03801
OFFICE_CODE=DZ38-03801-INSFP02
OFFICE_ALIAS=DZ38-TIS-INSFP02
OFFICE_NAME=Tissemsilt_INSFP02
OFFICE_DISPLAY_NAME=المعهد الوطني المتخصص في التكوين المهني تيسمسيلت 02
OFFICE_ID=office_dz38_03801_insfp02
SERVER_ID=server_dz38_03801_insfp02_main
```

## الإدارات والمصالح

لا تدخل المديريات والمصالح في `OFFICE_CODE`.

`OFFICE_CODE` يمثل المؤسسة كاملة، أما الهيكل الداخلي فيحفظ في جدول:

```text
OrganizationUnit
```

داخل كل مؤسسة INSFP ينشئ النظام تلقائيًا:

- إدارة المدير العام
- مدير المؤسسة
- المديرية الفرعية للإعلام والتوجيه والرقمنة والإدماج المهني
- مدير المديرية الفرعية
- مصلحة التوجيه
- مصلحة المراقبة العامة
- المديرية الفرعية للدراسات والتربصات
- مدير المديرية الفرعية
- مصلحة التنظيم ومتابعة التكوين الحضوري والتربصات في الوسط المهني
- مصلحة السكرتارية
- مصلحة الشهادات
- المديرية الفرعية للتمهين والتكوين المهني المتواصل
- مدير المديرية الفرعية
- مصلحة التمهين
- مصلحة السكرتارية
- مصلحة التكوين المهني المتواصل والشراكة

## ملف Algeria Cities

تم وضع الملف داخل المشروع في:

```text
sync_core/data/algeria_cities.xlsx
sync_core/data/algeria_cities.csv
```

ويتم استيراده إلى قاعدة الخادم المركزي بهذا الأمر:

```bat
.venv\Scripts\python manage.py import_algeria_cities --settings=training_center.settings_central
```

الصيانة التلقائية والخادم المركزي يشغلان هذا الأمر تلقائيًا بعد `migrate`.

## إنشاء مؤسسة رسمية من سطر الأوامر

```bat
.venv\Scripts\python manage.py create_official_office ^
  --wilaya-code 38 ^
  --commune-code 03801 ^
  --type INSFP ^
  --number 01 ^
  --display-name "المعهد الوطني المتخصص في التكوين المهني الشهيد تاج الدين حامد عبد الوهاب - تيسمسيلت" ^
  --settings=training_center.settings_central
```

بعد الإنشاء سيطبع النظام:

```text
OFFICE_CODE
OFFICE_ALIAS
OFFICE_NAME
OFFICE_DISPLAY_NAME
OFFICE_ID
SERVER_ID
SYNC_TOKEN
DATA_DIR
DATABASE
```

## بعد التحديث

شغّل على الخادم المركزي:

```bat
cd /d D:\training_center_ar_v2_1
set DJANGO_SETTINGS_MODULE=training_center.settings_central
set DJANGO_ENV=central
set APP_DATA_DIR=C:\TrainingCenterCentralData
set ENV_FILE_PATH=C:\TrainingCenterCentralData\.env

.venv\Scripts\python manage.py migrate --settings=training_center.settings_central
.venv\Scripts\python manage.py import_algeria_cities --settings=training_center.settings_central
.venv\Scripts\python manage.py seed_office_units --all --settings=training_center.settings_central
.venv\Scripts\python manage.py check --settings=training_center.settings_central
```

أو فقط شغل:

```bat
START_CENTRAL_SERVER_9000.bat
```

لأنه أصبح يستورد البلديات ويجهز الوحدات الإدارية تلقائيًا بعد الترحيلات.
