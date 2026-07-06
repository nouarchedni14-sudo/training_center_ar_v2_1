@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "NO_PAUSE=0"
set "SOFT=0"
for %%A in (%*) do (
    if /I "%%~A"=="/quiet" set "NO_PAUSE=1"
    if /I "%%~A"=="/soft" set "SOFT=1"
)
if "%SOFT%"=="1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\auto_maintenance_all.ps1" -ProjectRoot "%CD%" -CentralOnly -ContinueOnError
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\auto_maintenance_all.ps1" -ProjectRoot "%CD%" -CentralOnly
)
set "EXIT_CODE=%ERRORLEVEL%"
if not "%NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
