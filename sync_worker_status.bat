@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe manage.py sync_worker_status --settings=training_center.settings_lan
pause
endlocal
