@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

echo ============================================================
echo Building TrainingCenter light client and Setup
echo Python: %PYTHON_EXE%
echo ============================================================
echo.

"%PYTHON_EXE%" tools\build_client_setup_auto.py

echo.
echo Final expected outputs:
echo - dist_client_setup\TrainingCenterClient.exe
echo - dist_client_setup\server_url.txt
echo - dist_client_setup\TrainingCenter_Client_Setup.exe
echo.
pause
