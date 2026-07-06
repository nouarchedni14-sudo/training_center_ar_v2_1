@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] لم أجد Python داخل البيئة الافتراضية: .venv\Scripts\python.exe
    echo شغل الأمر من جذر المشروع أو تأكد من وجود .venv
    pause
    exit /b 1
)

echo ============================================================
echo   TrainingCenter - إعداد المرحلة 3 لتسجيل التغييرات المحلية
echo ============================================================
echo.

echo [1/4] تنفيذ migrations لإنشاء جداول المزامنة...
".venv\Scripts\python.exe" manage.py migrate --settings=training_center.settings_lan
if errorlevel 1 goto :fail

echo.
echo [2/4] تثبيت/تحديث هوية المكتب من ملف .env...
".venv\Scripts\python.exe" manage.py init_office_identity --settings=training_center.settings_lan
if errorlevel 1 goto :fail

echo.
echo [3/4] عرض النماذج المتاحة للتتبع داخل تطبيق trainees...
".venv\Scripts\python.exe" manage.py list_sync_candidate_models --app trainees --settings=training_center.settings_lan

echo.
echo [4/4] عرض حالة صندوق الإرسال...
".venv\Scripts\python.exe" manage.py sync_outbox_status --settings=training_center.settings_lan

echo.
echo تم تجهيز المرحلة 3.
echo مهم: تأكد أن C:\TrainingCenterData\.env يحتوي على:
echo SYNC_TRACKING_ENABLED=1
echo SYNC_TRACKED_MODELS=trainees.Specialty,trainees.Trainee
echo ثم أعد تشغيل الخادم من Task Scheduler أو يدويًا.
pause
exit /b 0

:fail
echo.
echo [ERROR] حدث خطأ أثناء الإعداد.
pause
exit /b 1
