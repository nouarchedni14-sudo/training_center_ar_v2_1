@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] لم يتم العثور على .venv\Scripts\python.exe
    echo تأكد من تشغيل الملف من جذر المشروع الصحيح.
    pause
    exit /b 1
)

echo ==============================================
echo  Training Center - Phase 1 Sync Identity
echo ==============================================
echo.

echo [1/3] تطبيق migrations الخاصة بمرحلة المزامنة الأولى...
".venv\Scripts\python.exe" manage.py migrate --settings=training_center.settings_lan
if errorlevel 1 goto fail

echo.
echo [2/3] إنشاء/تحديث هوية المكتب من ملف .env...
".venv\Scripts\python.exe" manage.py init_office_identity --settings=training_center.settings_lan
if errorlevel 1 goto fail

echo.
echo [3/3] عرض الحالة النهائية...
".venv\Scripts\python.exe" manage.py sync_design_status --settings=training_center.settings_lan
if errorlevel 1 goto fail

echo.
echo تمت المرحلة الأولى بنجاح.
pause
exit /b 0

:fail
echo.
echo [ERROR] حدث خطأ أثناء تنفيذ المرحلة الأولى.
pause
exit /b 1
