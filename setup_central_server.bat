@echo off
chcp 65001 >nul
setlocal EnableExtensions

cd /d "%~dp0"
set "TC_PROJECT_DIR=%~dp0"
set "TC_DATA_DIR=C:\TrainingCenterCentralData"
set "ENV_FILE=%TC_DATA_DIR%\.env"
set "SETUP_LOG=%TC_DATA_DIR%\central_setup_log.txt"

rem Developer account data requested by the user
set "DEV_USERNAME_VALUE=adem"
set "DEV_PASSWORD_VALUE=2022"
set "DEV_EMAIL_VALUE=nouarchedni14@gmail.com"

title Training Center Central Setup

echo ============================================================
echo SETUP CENTRAL SERVER
echo Project: %TC_PROJECT_DIR%
echo Data:    %TC_DATA_DIR%
echo Env:     %ENV_FILE%
echo ============================================================
echo.

if not exist "%TC_DATA_DIR%" (
    echo [INFO] Creating folder: %TC_DATA_DIR%
    mkdir "%TC_DATA_DIR%" 2>nul
)

if not exist "%TC_DATA_DIR%" (
    echo [ERROR] Cannot create folder: %TC_DATA_DIR%
    echo Run as Administrator, then try again.
    if /I not "%~1"=="/from-start" pause
    exit /b 1
)

echo ============================================================ > "%SETUP_LOG%"
echo SETUP CENTRAL SERVER >> "%SETUP_LOG%"
echo Date: %DATE% %TIME% >> "%SETUP_LOG%"
echo Project: %TC_PROJECT_DIR% >> "%SETUP_LOG%"
echo Data: %TC_DATA_DIR% >> "%SETUP_LOG%"
echo ============================================================ >> "%SETUP_LOG%"

set "OLD_POSTGRES_HOST=127.0.0.1"
set "OLD_POSTGRES_PORT=5432"
set "OLD_POSTGRES_DB=training_center_central"
set "OLD_POSTGRES_USER=postgres"
set "OLD_POSTGRES_PASSWORD=123456"
set "OLD_SECRET="
set "OLD_CHROME_EXE_PATH="

if exist "%ENV_FILE%" (
    echo [INFO] Existing .env found. A backup will be created.
    echo [INFO] Existing .env found. A backup will be created. >> "%SETUP_LOG%"
    copy /Y "%ENV_FILE%" "%TC_DATA_DIR%\.env.backup" >nul 2>nul
    for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_HOST=" "%ENV_FILE%" 2^>nul') do set "OLD_POSTGRES_HOST=%%B"
    for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_PORT=" "%ENV_FILE%" 2^>nul') do set "OLD_POSTGRES_PORT=%%B"
    for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_DB=" "%ENV_FILE%" 2^>nul') do set "OLD_POSTGRES_DB=%%B"
    for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_USER=" "%ENV_FILE%" 2^>nul') do set "OLD_POSTGRES_USER=%%B"
    for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_PASSWORD=" "%ENV_FILE%" 2^>nul') do set "OLD_POSTGRES_PASSWORD=%%B"
    for /f "tokens=1,* delims==" %%A in ('findstr /B /I "DJANGO_SECRET_KEY=" "%ENV_FILE%" 2^>nul') do set "OLD_SECRET=%%B"
    for /f "tokens=1,* delims==" %%A in ('findstr /B /I "CHROME_EXE_PATH=" "%ENV_FILE%" 2^>nul') do set "OLD_CHROME_EXE_PATH=%%B"
)

if "%OLD_SECRET%"=="" (
    for /f "delims=" %%S in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')" 2^>nul') do set "OLD_SECRET=%%S"
)
if "%OLD_SECRET%"=="" set "OLD_SECRET=replace-with-a-long-random-secret-central"

if "%OLD_CHROME_EXE_PATH%"=="" call :DETECT_CHROME_EXE

call :WRITE_ENV
if errorlevel 1 goto FAIL

echo [OK] .env is ready: %ENV_FILE%
echo [OK] .env is ready: %ENV_FILE% >> "%SETUP_LOG%"
echo.
echo Developer username: %DEV_USERNAME_VALUE%
echo Developer password: %DEV_PASSWORD_VALUE%
echo Developer email:    %DEV_EMAIL_VALUE%
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found: %~dp0.venv\Scripts\python.exe
    echo [ERROR] Python virtual environment not found: %~dp0.venv\Scripts\python.exe >> "%SETUP_LOG%"
    goto FAIL
)

call :LOAD_ENV

set "CREATE_DB_PY=%TEMP%\tc_create_central_db_%RANDOM%%RANDOM%.py"
call :WRITE_CREATE_DB_PY
if errorlevel 1 goto FAIL

echo [INFO] Checking/creating PostgreSQL database...
echo [INFO] Checking/creating PostgreSQL database... >> "%SETUP_LOG%"
"%~dp0.venv\Scripts\python.exe" "%CREATE_DB_PY%"
if errorlevel 1 (
    del "%CREATE_DB_PY%" >nul 2>nul
    goto FAIL
)
del "%CREATE_DB_PY%" >nul 2>nul

echo [INFO] Checking Django...
echo [INFO] Checking Django... >> "%SETUP_LOG%"
"%~dp0.venv\Scripts\python.exe" "%~dp0manage.py" check --settings=training_center.settings_central
if errorlevel 1 goto FAIL

echo [INFO] Applying migrations...
echo [INFO] Applying migrations... >> "%SETUP_LOG%"
"%~dp0.venv\Scripts\python.exe" "%~dp0manage.py" migrate --settings=training_center.settings_central
if errorlevel 1 goto FAIL

echo [INFO] Creating/updating developer account...
echo [INFO] Creating/updating developer account... >> "%SETUP_LOG%"
"%~dp0.venv\Scripts\python.exe" "%~dp0manage.py" ensure_developer --reset-password --settings=training_center.settings_central
if errorlevel 1 (
    echo [WARN] ensure_developer --reset-password failed. Trying without --reset-password...
    echo [WARN] ensure_developer --reset-password failed. Trying without --reset-password... >> "%SETUP_LOG%"
    "%~dp0.venv\Scripts\python.exe" "%~dp0manage.py" ensure_developer --settings=training_center.settings_central
    if errorlevel 1 goto FAIL
)

echo.
echo [OK] Central setup completed successfully.
echo [OK] Central setup completed successfully. >> "%SETUP_LOG%"
if /I not "%~1"=="/from-start" pause
exit /b 0

:FAIL
echo.
echo [ERROR] Central setup failed.
echo [ERROR] Central setup failed. >> "%SETUP_LOG%"
echo See log: %SETUP_LOG%
echo.
if /I not "%~1"=="/from-start" pause
exit /b 1

:LOAD_ENV
set "ENV_FILE_PATH=%ENV_FILE%"
set "DJANGO_SETTINGS_MODULE=training_center.settings_central"
set "DJANGO_ENV=central"
for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_HOST=" "%ENV_FILE%" 2^>nul') do set "POSTGRES_HOST=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_PORT=" "%ENV_FILE%" 2^>nul') do set "POSTGRES_PORT=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_DB=" "%ENV_FILE%" 2^>nul') do set "POSTGRES_DB=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_USER=" "%ENV_FILE%" 2^>nul') do set "POSTGRES_USER=%%B"
for /f "tokens=1,* delims==" %%A in ('findstr /B /I "POSTGRES_PASSWORD=" "%ENV_FILE%" 2^>nul') do set "POSTGRES_PASSWORD=%%B"
set "DEV_LOGIN_ENABLED=1"
set "DEV_USERNAME=%DEV_USERNAME_VALUE%"
set "DEV_PASSWORD=%DEV_PASSWORD_VALUE%"
set "DEV_EMAIL=%DEV_EMAIL_VALUE%"
set "DEV_FORCE_PASSWORD_RESET=1"
exit /b 0

:DETECT_CHROME_EXE
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set "OLD_CHROME_EXE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
    exit /b 0
)
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set "OLD_CHROME_EXE_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    exit /b 0
)
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set "OLD_CHROME_EXE_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    exit /b 0
)
for /f "delims=" %%C in ('where chrome 2^>nul') do (
    set "OLD_CHROME_EXE_PATH=%%C"
    goto :DETECT_CHROME_EXE_DONE
)
:DETECT_CHROME_EXE_DONE
exit /b 0

:WRITE_ENV
> "%ENV_FILE%" echo # ============================================================
>> "%ENV_FILE%" echo # Training Center - Central Server Environment
>> "%ENV_FILE%" echo # Auto-created by setup_central_server.bat
>> "%ENV_FILE%" echo # Path: C:\TrainingCenterCentralData\.env
>> "%ENV_FILE%" echo # ============================================================
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo DJANGO_ENV=central
>> "%ENV_FILE%" echo DJANGO_DEBUG=1
>> "%ENV_FILE%" echo DJANGO_SECRET_KEY=%OLD_SECRET%
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,%COMPUTERNAME%,*
>> "%ENV_FILE%" echo DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:9000,http://localhost:9000,http://%COMPUTERNAME%:9000
>> "%ENV_FILE%" echo CENTRAL_ALLOW_ALL_HOSTS=1
>> "%ENV_FILE%" echo CENTRAL_PUBLIC_URL=
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo APP_DATA_DIR=C:/TrainingCenterCentralData
>> "%ENV_FILE%" echo DB_ENGINE=postgres
>> "%ENV_FILE%" echo POSTGRES_HOST=%OLD_POSTGRES_HOST%
>> "%ENV_FILE%" echo POSTGRES_PORT=%OLD_POSTGRES_PORT%
>> "%ENV_FILE%" echo POSTGRES_DB=%OLD_POSTGRES_DB%
>> "%ENV_FILE%" echo POSTGRES_USER=%OLD_POSTGRES_USER%
>> "%ENV_FILE%" echo POSTGRES_PASSWORD=%OLD_POSTGRES_PASSWORD%
>> "%ENV_FILE%" echo POSTGRES_CONN_MAX_AGE=120
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo SYNC_MODE=central_server
>> "%ENV_FILE%" echo CENTRAL_SYNC_API_ENABLED=1
>> "%ENV_FILE%" echo CENTRAL_AUTO_REGISTER_OFFICES=0
>> "%ENV_FILE%" echo SYNC_PULL_LIMIT=100
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo # Main developer account
>> "%ENV_FILE%" echo DEV_LOGIN_ENABLED=1
>> "%ENV_FILE%" echo DEV_USERNAME=%DEV_USERNAME_VALUE%
>> "%ENV_FILE%" echo DEV_PASSWORD=%DEV_PASSWORD_VALUE%
>> "%ENV_FILE%" echo DEV_EMAIL=%DEV_EMAIL_VALUE%
>> "%ENV_FILE%" echo DEV_FORCE_PASSWORD_RESET=1
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo CENTRAL_TRAINEE_MANAGER_URL=http://127.0.0.1:8000/developer/login/
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo # Auto-open central dashboard in Google Chrome when available
>> "%ENV_FILE%" echo AUTO_OPEN_BROWSER=1
>> "%ENV_FILE%" echo PREFER_CHROME_BROWSER=1
>> "%ENV_FILE%" echo AUTO_OPEN_BROWSER_URL=http://127.0.0.1:9000/
if not "%OLD_CHROME_EXE_PATH%"=="" >> "%ENV_FILE%" echo CHROME_EXE_PATH=%OLD_CHROME_EXE_PATH:\=/%
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo CENTRAL_CONTROL_ENABLED=1
>> "%ENV_FILE%" echo CENTRAL_DEFAULT_LICENSE_PLAN=standard
>> "%ENV_FILE%" echo CENTRAL_DEFAULT_MAX_USERS=5
>> "%ENV_FILE%" echo CENTRAL_DEFAULT_FEATURE_FLAGS={"trainees_add":true,"trainees_edit":true,"trainees_delete":false,"reports_export":true,"attendance":true,"media_upload":true,"admin_panel":false}
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo APP_VERSION=1.0.0
>> "%ENV_FILE%" echo CENTRAL_DEFAULT_UPDATE_CHANNEL=stable
>> "%ENV_FILE%" echo CENTRAL_LATEST_VERSION=1.0.0
>> "%ENV_FILE%" echo CENTRAL_UPDATE_DOWNLOAD_URL=
>> "%ENV_FILE%" echo CENTRAL_UPDATE_NOTES=
>> "%ENV_FILE%" echo.
>> "%ENV_FILE%" echo SESSION_COOKIE_SECURE=0
>> "%ENV_FILE%" echo CSRF_COOKIE_SECURE=0
>> "%ENV_FILE%" echo BEHIND_REVERSE_PROXY=0
>> "%ENV_FILE%" echo DJANGO_LOG_LEVEL=INFO
if errorlevel 1 exit /b 1
exit /b 0

:WRITE_CREATE_DB_PY
> "%CREATE_DB_PY%" echo import os, sys
>> "%CREATE_DB_PY%" echo try:
>> "%CREATE_DB_PY%" echo     import psycopg2
>> "%CREATE_DB_PY%" echo     from psycopg2 import sql
>> "%CREATE_DB_PY%" echo except Exception as exc:
>> "%CREATE_DB_PY%" echo     print("[WARN] psycopg2 not available; database auto-create skipped:", exc)
>> "%CREATE_DB_PY%" echo     sys.exit(0)
>> "%CREATE_DB_PY%" echo host=os.getenv("POSTGRES_HOST","127.0.0.1")
>> "%CREATE_DB_PY%" echo port=os.getenv("POSTGRES_PORT","5432")
>> "%CREATE_DB_PY%" echo user=os.getenv("POSTGRES_USER","postgres")
>> "%CREATE_DB_PY%" echo password=os.getenv("POSTGRES_PASSWORD","")
>> "%CREATE_DB_PY%" echo dbname=os.getenv("POSTGRES_DB","training_center_central")
>> "%CREATE_DB_PY%" echo maintenance=os.getenv("POSTGRES_MAINTENANCE_DB","postgres")
>> "%CREATE_DB_PY%" echo try:
>> "%CREATE_DB_PY%" echo     conn=psycopg2.connect(host=host,port=port,user=user,password=password,dbname=maintenance,connect_timeout=10)
>> "%CREATE_DB_PY%" echo     conn.autocommit=True
>> "%CREATE_DB_PY%" echo     cur=conn.cursor()
>> "%CREATE_DB_PY%" echo     cur.execute("SELECT 1 FROM pg_database WHERE datname=%%s", (dbname,))
>> "%CREATE_DB_PY%" echo     exists=cur.fetchone() is not None
>> "%CREATE_DB_PY%" echo     if exists:
>> "%CREATE_DB_PY%" echo         print(f"[OK] Database already exists: {dbname}")
>> "%CREATE_DB_PY%" echo     else:
>> "%CREATE_DB_PY%" echo         cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
>> "%CREATE_DB_PY%" echo         print(f"[OK] Database created: {dbname}")
>> "%CREATE_DB_PY%" echo     cur.close()
>> "%CREATE_DB_PY%" echo     conn.close()
>> "%CREATE_DB_PY%" echo except Exception as exc:
>> "%CREATE_DB_PY%" echo     print("[ERROR] Could not verify/create PostgreSQL database.")
>> "%CREATE_DB_PY%" echo     print("Check PostgreSQL service and POSTGRES_PASSWORD in C:\\TrainingCenterCentralData\\.env")
>> "%CREATE_DB_PY%" echo     print("Details:", exc)
>> "%CREATE_DB_PY%" echo     sys.exit(1)
if errorlevel 1 exit /b 1
exit /b 0
