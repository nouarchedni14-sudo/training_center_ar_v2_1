@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe manage.py central_update_status --settings=training_center.settings_central
pause
