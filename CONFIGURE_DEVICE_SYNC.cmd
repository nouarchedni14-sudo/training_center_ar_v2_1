@echo off
chcp 65001 >nul
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0CONFIGURE_DEVICE_SYNC.ps1"
pause
