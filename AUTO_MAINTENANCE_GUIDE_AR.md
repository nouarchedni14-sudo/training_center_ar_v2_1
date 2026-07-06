# الصيانة التلقائية للتحديثات والترحيلات

بعد هذا التعديل لا تحتاج إلى كتابة أوامر `set APP_DATA_DIR` و `migrate` و `check` يدويًا في كل مرة.

## ما الذي يحدث تلقائيًا؟

- عند تشغيل الخادم المركزي من `START_CENTRAL_SERVER_9000.bat` يتم تطبيق الترحيلات وفحص الخادم المركزي، ثم يتم فحص كل المكاتب الموجودة تلقائيًا.
- عند تشغيل أي مكتب من ملفات التشغيل التي ينشئها النظام، يقوم المكتب تلقائيًا بتنفيذ:
  - `migrate --noinput`
  - `check`
- عند إنشاء مكتب جديد مستقبلًا داخل `C:\TrainingCenterData_<OfficeName>`، سيكتشفه ملف الصيانة العام تلقائيًا لأنه يبحث عن كل مجلدات:
  - `C:\TrainingCenterData_*`

## الملفات المهمة

- `AUTO_MAINTENANCE_ALL.bat`  
  يطبق migrate/check على الخادم المركزي وكل المكاتب المكتشفة.

- `AUTO_MAINTENANCE_CENTRAL.bat`  
  يطبق migrate/check على الخادم المركزي فقط.

- `AUTO_MAINTENANCE_OFFICES.bat`  
  يطبق migrate/check على كل المكاتب فقط.

- `CHECK_CENTRAL.bat`  
  اسم مختصر لفحص الخادم المركزي.

- `CHECK_ALL_OFFICES.bat`  
  اسم مختصر لفحص كل المكاتب.

- `CHECK_ALL_ENVIRONMENTS.bat`  
  اسم مختصر لفحص الخادم المركزي وكل المكاتب.

## تشغيل بدون توقف النافذة

للاستعمال داخل ملفات التشغيل:

```bat
AUTO_MAINTENANCE_ALL.bat /quiet /soft
```

- `/quiet`: لا ينتظر الضغط على زر في النهاية.
- `/soft`: إذا فشل مكتب واحد لا يوقف تشغيل الخادم المركزي، لكن يسجل الخطأ في ملف السجل.

## أين توجد السجلات؟

كل عملية تكتب سجلًا داخل:

```text
D:\training_center_ar_v2_1\logs\auto_maintenance_YYYYMMDD_HHMMSS.log
```

## ملاحظة

هذه الصيانة تطبق تحديثات قاعدة البيانات والفحص بعد نسخ ملفات تحديث جديدة. أما تحميل التحديث نفسه فيتم عبر نظام التحديث المركزي أو رفع ZIP يدويًا.

## إضافة رسمية جديدة: Algeria Cities والهيكل الإداري

بعد التحديث الجديد، الصيانة التلقائية للخادم المركزي لا تكتفي بـ `migrate` و `check` فقط، بل تنفذ أيضًا:

```bat
manage.py import_algeria_cities --quiet
manage.py seed_office_units --all --quiet
```

هذا يعني أن قائمة الولايات والبلديات من الملف:

```text
sync_core/data/algeria_cities.csv
sync_core/data/algeria_cities.xlsx
```

تُستورد تلقائيًا إلى الخادم المركزي، وأي مؤسسة موجودة يتم تجهيز هيكلها الإداري الافتراضي إذا كان ناقصًا.
