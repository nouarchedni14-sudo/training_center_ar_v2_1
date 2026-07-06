@echo off
setlocal EnableExtensions
set "APPDIR=%~dp0.."
set "LOGDIR=%ProgramData%\TrainingCenterOfficeServer\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul
set "INSTALLER=%~1"

> "%LOGDIR%\postgres_install_cmd.log" echo Running PostgreSQL setup helper...
>> "%LOGDIR%\postgres_install_cmd.log" echo AppDir: %APPDIR%
>> "%LOGDIR%\postgres_install_cmd.log" echo Installer argument: %INSTALLER%

if not "%INSTALLER%"=="" (
  powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%APPDIR%\tools\install_postgresql_if_needed.ps1" -InstallerPath "%INSTALLER%" -SuperPassword "123456" -Port 5432 -FallbackPort 5433 >> "%LOGDIR%\postgres_install_cmd.log" 2>&1
) else (
  powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%APPDIR%\tools\install_postgresql_if_needed.ps1" -SuperPassword "123456" -Port 5432 -FallbackPort 5433 >> "%LOGDIR%\postgres_install_cmd.log" 2>&1
)
set "ERR=%ERRORLEVEL%"

if "%ERR%"=="0" exit /b 0

>> "%LOGDIR%\postgres_install_cmd.log" echo PostgreSQL helper failed with error %ERR%.
>> "%LOGDIR%\postgres_install_cmd.log" echo IMPORTANT: No direct fallback installer launch is used, to avoid PostgreSQL upgrade-mode when PostgreSQL already exists.

echo PostgreSQL setup/check failed. See logs:
echo %LOGDIR%\postgres_install_cmd.log
echo %LOGDIR%\postgres_install.log
exit /b %ERR%
