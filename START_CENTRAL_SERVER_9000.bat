@echo off
chcp 65001 >nul
setlocal EnableExtensions

cd /d "%~dp0"
set "TC_PROJECT_DIR=%~dp0"
set "TC_DATA_DIR=C:\TrainingCenterCentralData"
set "ENV_FILE_PATH=%TC_DATA_DIR%\.env"
set "DJANGO_SETTINGS_MODULE=training_center.settings_central"
set "DJANGO_ENV=central"
set "CENTRAL_HOSTNAME=%COMPUTERNAME%"
set "CENTRAL_PUBLIC_URL=http://%COMPUTERNAME%:9000"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
set "SETUP_BAT=%~dp0setup_central_server.bat"

title Training Center Central Server 9000

echo ============================================================
echo START CENTRAL SERVER 9000
echo Project: %TC_PROJECT_DIR%
echo Local URL:   http://127.0.0.1:9000/
echo Network URL: http://%COMPUTERNAME%:9000/
echo ============================================================
echo.

if not exist "%TC_DATA_DIR%" (
    echo [INFO] Creating data folder: %TC_DATA_DIR%
    mkdir "%TC_DATA_DIR%" 2>nul
)

if not exist "%TC_DATA_DIR%" (
    echo [ERROR] Cannot create folder: %TC_DATA_DIR%
    echo Run this file as Administrator, then try again.
    echo.
    pause
    exit /b 1
)

set "START_LOG=%TC_DATA_DIR%\central_start_log.txt"
echo ============================================================ > "%START_LOG%"
echo START CENTRAL SERVER 9000 >> "%START_LOG%"
echo Date: %DATE% %TIME% >> "%START_LOG%"
echo Project: %TC_PROJECT_DIR% >> "%START_LOG%"
echo Computer: %COMPUTERNAME% >> "%START_LOG%"
echo ============================================================ >> "%START_LOG%"

if not exist "%SETUP_BAT%" (
    echo [ERROR] setup_central_server.bat not found in this project folder.
    echo Put START_CENTRAL_SERVER_9000.bat and setup_central_server.bat inside the main project folder beside manage.py.
    echo Log: %START_LOG%
    echo.
    pause
    exit /b 1
)

echo [INFO] Running setup_central_server.bat first...
echo [INFO] Running setup_central_server.bat first... >> "%START_LOG%"

rem Run setup in a child CMD so this window does NOT disappear even if setup has an error.
cmd /d /c call "%SETUP_BAT%" /from-start
set "SETUP_EXIT=%ERRORLEVEL%"

if not "%SETUP_EXIT%"=="0" (
    echo.
    echo [ERROR] setup_central_server.bat failed with code %SETUP_EXIT%.
    echo See log: %TC_DATA_DIR%\central_setup_log.txt
    echo This window will stay open so you can read the error.
    echo.
    pause
    exit /b %SETUP_EXIT%
)

if not exist "%PYTHON_EXE%" (
    echo.
    echo [ERROR] Python virtual environment not found:
    echo %PYTHON_EXE%
    echo.
    echo You must run this file from the real project folder, not from inside the ZIP.
    echo.
    pause
    exit /b 1
)

echo.
echo [INFO] Setup completed.
echo [INFO] Running Django migrations from START_CENTRAL_SERVER_9000...
echo [INFO] Running Django migrations from START_CENTRAL_SERVER_9000... >> "%START_LOG%"
"%PYTHON_EXE%" "%~dp0manage.py" migrate --noinput --settings=training_center.settings_central
set "MIGRATE_EXIT=%ERRORLEVEL%"
if not "%MIGRATE_EXIT%"=="0" (
    echo.
    echo [ERROR] migrate failed with code %MIGRATE_EXIT%.
    echo [ERROR] migrate failed with code %MIGRATE_EXIT%. >> "%START_LOG%"
    echo This window will stay open so you can read the error.
    echo.
    pause
    exit /b %MIGRATE_EXIT%
)
echo [OK] Migrations completed from START_CENTRAL_SERVER_9000.
echo [OK] Migrations completed from START_CENTRAL_SERVER_9000. >> "%START_LOG%"

echo [INFO] Importing Algeria Cities and preparing default organization units...
echo [INFO] Importing Algeria Cities and preparing default organization units... >> "%START_LOG%"
"%PYTHON_EXE%" "%~dp0manage.py" import_algeria_cities --quiet --settings=training_center.settings_central
set "CITIES_EXIT=%ERRORLEVEL%"
if not "%CITIES_EXIT%"=="0" (
    echo [ERROR] import_algeria_cities failed with code %CITIES_EXIT%.
    echo [ERROR] import_algeria_cities failed with code %CITIES_EXIT%. >> "%START_LOG%"
    pause
    exit /b %CITIES_EXIT%
)
"%PYTHON_EXE%" "%~dp0manage.py" seed_office_units --all --quiet --settings=training_center.settings_central

if exist "%~dp0AUTO_MAINTENANCE_OFFICES.bat" (
    echo.
    echo [INFO] Applying automatic maintenance to all detected offices...
    echo [INFO] Applying automatic maintenance to all detected offices... >> "%START_LOG%"
    call "%~dp0AUTO_MAINTENANCE_OFFICES.bat" /quiet /soft
    echo [INFO] Automatic offices maintenance finished. See logs folder for details.
    echo [INFO] Automatic offices maintenance finished. >> "%START_LOG%"
)

echo.
echo [INFO] Opening browser automatically...
echo [INFO] Starting central server now...
echo.
echo Open on this computer:
echo http://127.0.0.1:9000/
echo.
echo Other devices use:
echo http://%COMPUTERNAME%:9000/
echo.
echo Do not close this window while using the program.
echo.

rem Open the browser after a few seconds, while Django server is starting.
rem Prefer Google Chrome and open a NEW TAB in the existing Chrome window if Chrome is already open.
rem If Chrome is not running, Chrome will open normally. If Chrome is not found, fall back to the Windows default browser.
set "CENTRAL_BROWSER_URL=http://127.0.0.1:9000/"
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$u='%CENTRAL_BROWSER_URL%'; Start-Sleep -Seconds 4; $paths=@($env:CHROME_EXE_PATH,'C:\Program Files\Google\Chrome\Application\chrome.exe','C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'); $chrome=$paths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1; if(-not $chrome){ $cmd=Get-Command chrome.exe -ErrorAction SilentlyContinue; if($cmd){$chrome=$cmd.Source} }; if($chrome){ Start-Process -FilePath $chrome -ArgumentList @('--new-tab',$u) } else { Start-Process $u }"

"%PYTHON_EXE%" "%~dp0manage.py" runserver 0.0.0.0:9000 --settings=training_center.settings_central
set "RUN_EXIT=%ERRORLEVEL%"

echo.
echo [INFO] Central server stopped. Code: %RUN_EXIT%
echo [INFO] Central server stopped. Code: %RUN_EXIT% >> "%START_LOG%"
echo This window will stay open.
echo.
pause
exit /b %RUN_EXIT%
