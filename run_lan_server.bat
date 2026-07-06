@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo ========================================
echo TrainingCenter LAN Server
echo Working dir: %cd%
echo Python: %PYTHON_EXE%
echo ========================================
echo.

"%PYTHON_EXE%" launcher\lan_server.py

echo.
echo Exit code: %ERRORLEVEL%
pause