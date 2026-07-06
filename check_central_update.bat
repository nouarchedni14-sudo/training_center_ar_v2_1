@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe manage.py check_central_update --settings=training_center.settings_lan
pause
