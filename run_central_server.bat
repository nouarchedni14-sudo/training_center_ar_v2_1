@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "DJANGO_SETTINGS_MODULE=training_center.settings_central"
set "DJANGO_ENV=central"
set "APP_DATA_DIR=C:\TrainingCenterCentralData"
set "ENV_FILE_PATH=C:\TrainingCenterCentralData\.env"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] لم يتم العثور على .venv\Scripts\python.exe
  pause
  exit /b 1
)
if exist "%~dp0AUTO_MAINTENANCE_CENTRAL.bat" (
  echo [INFO] تطبيق الترحيلات والفحص تلقائيا على الخادم المركزي...
  call "%~dp0AUTO_MAINTENANCE_CENTRAL.bat" /quiet
  if errorlevel 1 (
    echo [ERROR] فشلت الصيانة التلقائية للخادم المركزي.
    pause
    exit /b 1
  )
)
echo [INFO] تشغيل برنامج المطور المركزي على http://127.0.0.1:9000/central/
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:9000 --settings=training_center.settings_central
pause
