@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe manage.py sync_conflicts_status --settings=training_center.settings_lan
pause
