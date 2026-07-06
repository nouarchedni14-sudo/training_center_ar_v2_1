@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] لم يتم العثور على .venv\Scripts\python.exe
  pause
  exit /b 1
)

echo [1/4] تطبيق migrations الخاصة بجداول المزامنة...
".venv\Scripts\python.exe" manage.py migrate --settings=training_center.settings_lan
if errorlevel 1 goto :error

echo [2/4] ضبط هوية المكتب من ملف .env...
".venv\Scripts\python.exe" manage.py init_office_identity --settings=training_center.settings_lan
if errorlevel 1 goto :error

echo [3/4] إنشاء حدث  في صندوق الإرسال...
".venv\Scripts\python.exe" manage.py create_sync_test_event --settings=training_center.settings_lan
if errorlevel 1 goto :error

echo [4/4] عرض حالة المزامنة...
".venv\Scripts\python.exe" manage.py sync_design_status --settings=training_center.settings_lan
if errorlevel 1 goto :error

echo.
echo تم تجهيز المرحلة 2 بنجاح.
pause
exit /b 0

:error
echo.
echo حدث خطأ أثناء تجهيز المرحلة 2.
pause
exit /b 1
