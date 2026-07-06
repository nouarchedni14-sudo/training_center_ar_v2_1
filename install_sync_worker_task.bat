@echo off
setlocal
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0tools\install_sync_worker_task.ps1" -ProjectRoot "%CD%" -IntervalMinutes 5
pause
endlocal
