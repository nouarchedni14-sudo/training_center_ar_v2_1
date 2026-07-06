@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe manage.py apply_sync_inbox --settings=training_center.settings_lan
pause
