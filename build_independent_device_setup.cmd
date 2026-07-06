@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo ============================================================
echo Building Training Center Independent Device Setup
echo Python: %PYTHON_EXE%
echo ============================================================
echo.

"%PYTHON_EXE%" "%~dp0tools\build_office_server_setup.py"
if errorlevel 1 (
  echo.
  echo Build failed. Check the messages above.
  pause
  exit /b 1
)

echo.
echo Build finished.
echo Expected installer:
echo dist_office_server\installer\TrainingCenter_Office_Server_Setup.exe
echo.
pause
