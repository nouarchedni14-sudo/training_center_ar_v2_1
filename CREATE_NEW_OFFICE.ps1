param(
    [Parameter(Mandatory=$true)][string]$OfficeName,
    [Parameter(Mandatory=$true)][string]$OfficeId,
    [Parameter(Mandatory=$false)][string]$ServerId = "",
    [string]$OfficeCode = "",
    [string]$OfficeAlias = "",
    [string]$OfficeDisplayName = "",
    [string]$WilayaCode = "",
    [string]$CommuneCode = "",
    [string]$EstablishmentType = "",
    [string]$EstablishmentNumber = "",
    [Parameter(Mandatory=$true)][int]$Port,
    [Parameter(Mandatory=$true)][string]$Database,
    [Parameter(Mandatory=$true)][string]$DataDir,
    [string]$SyncToken = "",
    [string]$CentralUrl = "",
    [string]$PostgresUser = "postgres",
    [string]$PostgresPassword = "",
    [string]$PsqlPath = "C:\Program Files\PostgreSQL\16\bin\psql.exe",
    [switch]$SkipCentralRegister
)

if (-not $CentralUrl) { $CentralUrl = "http://${env:COMPUTERNAME}:9000" }
if (-not $OfficeDisplayName) { $OfficeDisplayName = $OfficeName }

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

function Write-Step([string]$Text) { Write-Host "`n[INFO] $Text" -ForegroundColor Cyan }
function Get-ProjectRoot { Split-Path -Parent $MyInvocation.ScriptName }
function Get-PrimaryIPv4 {
    try {
        $ip = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
            Sort-Object InterfaceMetric |
            Select-Object -First 1 -ExpandProperty IPAddress
        if ($ip) { return $ip }
    } catch {}
    return "127.0.0.1"
}
function Get-ChromeExePath {
    $candidates = New-Object System.Collections.Generic.List[string]
    function Add-Candidate([string]$PathValue) {
        if (-not [string]::IsNullOrWhiteSpace($PathValue)) {
            $clean = $PathValue.Trim().Trim('"')
            if ($clean -and -not $candidates.Contains($clean)) { [void]$candidates.Add($clean) }
        }
    }

    # Registry: أدق مكان لمعرفة مسار Chrome إذا كان مثبتًا ولا يظهر في PATH.
    foreach ($regPath in @(
        'Registry::HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',
        'Registry::HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',
        'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe'
    )) {
        try {
            $item = Get-ItemProperty -Path $regPath -ErrorAction Stop
            Add-Candidate $item.'(default)'
            Add-Candidate $item.'PSChildName'
        } catch {}
    }

    if (${env:ProgramFiles}) { Add-Candidate (Join-Path ${env:ProgramFiles} 'Google\Chrome\Application\chrome.exe') }
    if (${env:ProgramFiles(x86)}) { Add-Candidate (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe') }
    if (${env:LOCALAPPDATA}) { Add-Candidate (Join-Path ${env:LOCALAPPDATA} 'Google\Chrome\Application\chrome.exe') }
    Add-Candidate 'C:\Program Files\Google\Chrome\Application\chrome.exe'
    Add-Candidate 'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'

    try {
        $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
        if ($cmd) { Add-Candidate $cmd.Source }
    } catch {}

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate -PathType Leaf)) { return $candidate }
    }
    return ""
}
function Get-EnvValue([string]$Path,[string]$Key,[string]$Default="") {
    if (!(Test-Path $Path)) { return $Default }
    $line = Get-Content $Path -Encoding UTF8 | Where-Object { $_ -match "^$([regex]::Escape($Key))=" } | Select-Object -Last 1
    if (!$line) { return $Default }
    return ($line -replace "^$([regex]::Escape($Key))=", "").Trim()
}
function Invoke-Checked([string]$FilePath, [string[]]$Arguments, [hashtable]$ExtraEnv) {
    $old = @{}
    foreach ($k in $ExtraEnv.Keys) {
        $old[$k] = [Environment]::GetEnvironmentVariable($k, "Process")
        [Environment]::SetEnvironmentVariable($k, [string]$ExtraEnv[$k], "Process")
    }
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) { throw ("Command failed: " + $FilePath + " " + ($Arguments -join " ")) }
    } finally {
        foreach ($k in $ExtraEnv.Keys) { [Environment]::SetEnvironmentVariable($k, $old[$k], "Process") }
    }
}
function Invoke-Psql([string]$Sql) {
    & $PsqlPath -U $PostgresUser -d postgres -c $Sql | Out-Host
    return $LASTEXITCODE
}
function New-SafeName([string]$Value) {
    $raw = ($Value -replace '^office-', '')
    $raw = ($raw -replace '[^A-Za-z0-9_-]', '_')
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = 'office' }
    return $raw
}
function New-SafeDatabaseName([string]$Value) {
    $raw = ($Value -replace '[^A-Za-z0-9_]', '_').ToLowerInvariant()
    while ($raw.Contains('__')) { $raw = $raw.Replace('__','_') }
    $raw = $raw.Trim('_')
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = 'training_center_office' }
    if ($raw[0] -match '[0-9]') { $raw = 'db_' + $raw }
    if ($raw.Length -gt 60) { $raw = $raw.Substring(0,60).Trim('_') }
    return $raw
}

function New-SafeFolderName([string]$Value, [string]$Fallback) {
    $raw = $Value
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = $Fallback }
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = 'office' }
    foreach ($ch in [System.IO.Path]::GetInvalidFileNameChars()) { $raw = $raw.Replace([string]$ch, '_') }
    $raw = ($raw -replace '\s+', ' ')
    $raw = $raw.Trim()
    $raw = $raw.Trim('.')
    $raw = $raw.Trim('_')
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = $Fallback }
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = 'office' }
    return $raw
}

$ProjectRoot = Get-ProjectRoot
Set-Location $ProjectRoot
$Database = New-SafeDatabaseName $Database
$GeneratedScriptsDir = Join-Path $ProjectRoot "generated_office_scripts"
New-Item -ItemType Directory -Force $GeneratedScriptsDir | Out-Null
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) { $Python = "python" }

if ([string]::IsNullOrWhiteSpace($ServerId)) {
    $ServerId = "server-" + (New-SafeName $OfficeId).ToLower() + "-01"
}

$CentralEnv = "C:\TrainingCenterCentralData\.env"
if ([string]::IsNullOrWhiteSpace($PostgresPassword)) {
    $PostgresPassword = Get-EnvValue $CentralEnv "POSTGRES_PASSWORD" "123456"
}
$DevUsername = Get-EnvValue $CentralEnv "DEV_USERNAME" ""
$DevPassword = Get-EnvValue $CentralEnv "DEV_PASSWORD" ""
$DevEmail = Get-EnvValue $CentralEnv "DEV_EMAIL" ""
$DevLoginEnabled = "0"
if (-not [string]::IsNullOrWhiteSpace($DevUsername) -and -not [string]::IsNullOrWhiteSpace($DevPassword)) {
    $DevLoginEnabled = "1"
}
if (!(Test-Path $PsqlPath)) { $PsqlPath = "psql" }

$DetectedIP = Get-PrimaryIPv4
$DeviceName = $env:COMPUTERNAME
$ChromeExePath = Get-ChromeExePath
if (-not [System.IO.Path]::IsPathRooted($DataDir)) {
    $DataDir = Join-Path "C:\" $DataDir
}
$DataDir = $DataDir.TrimEnd([char]'\', [char]'/')
$EnvPath = Join-Path $DataDir ".env"
$StartName = (New-SafeName $OfficeId).ToUpper()
$StartOfficeBat = Join-Path $GeneratedScriptsDir ("START_OFFICE_{0}_{1}.bat" -f $StartName, $Port)
$StartSyncBat = Join-Path $GeneratedScriptsDir ("START_SYNC_{0}_ONCE.bat" -f $StartName)
# تنظيف ملفات قديمة في جذر المشروع لنفس المكتب حتى لا يحدث خلط لاحقًا.
Get-ChildItem -Path $ProjectRoot -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -like ("START_OFFICE_{0}_*.bat" -f $StartName) -or $_.Name -like ("START_SYNC_{0}_*.bat" -f $StartName) -or $_.Name -like ("START_SYNC_{0}_ONCE.bat" -f $StartName)
} | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Step ("Preparing database: " + $Database)
$env:PGPASSWORD = $PostgresPassword
try {
    Invoke-Psql ("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='" + $Database + "' AND pid != pg_backend_pid();") | Out-Null
    $existsSql = "SELECT 1 FROM pg_database WHERE datname='" + $Database + "';"
    $exists = & $PsqlPath -U $PostgresUser -d postgres -tAc $existsSql
    if (($exists | Out-String).Trim() -ne "1") {
        $code = Invoke-Psql ("CREATE DATABASE " + $Database + " WITH ENCODING 'UTF8';")
        if ($code -ne 0) { throw "Could not create database $Database" }
    } else {
        Write-Host "Database already exists; continuing." -ForegroundColor Yellow
    }
} finally {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Step ("Preparing data folder: " + $DataDir)
New-Item -ItemType Directory -Force $DataDir | Out-Null

if ([string]::IsNullOrWhiteSpace($SyncToken) -and -not $SkipCentralRegister) {
    Write-Step "Registering office in central server"
    $registerArgs = @(
        "manage.py", "register_central_office",
        "--office-id", $OfficeId,
        "--office-name", $OfficeName,
        "--server-id", $ServerId,
        "--office-code", $OfficeCode,
        "--office-alias", $OfficeAlias,
        "--office-display-name", $OfficeDisplayName,
        "--wilaya-code", $WilayaCode,
        "--commune-code", $CommuneCode,
        "--establishment-type", $EstablishmentType,
        "--establishment-number", $EstablishmentNumber,
        "--settings=training_center.settings_central"
    )
    $registerOutput = & $Python @registerArgs 2>&1
    $registerOutput | Out-Host
    $tokenLine = $registerOutput | Where-Object { $_ -match '^SYNC_TOKEN=' } | Select-Object -Last 1
    if ($tokenLine) { $SyncToken = ($tokenLine -replace '^SYNC_TOKEN=', '').Trim() }
}
if ([string]::IsNullOrWhiteSpace($SyncToken)) {
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $SyncToken = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','A').Replace('/','B')
}

Write-Step "Writing .env file"
$dataDirEnv = $DataDir -replace '\\','/'
$trackedModels = "trainees.حضوري_أولي,trainees.تمهين,trainees.دفعة,trainees.مسائي_ومعابر"
$envLines = @(
"DJANGO_ENV=lan",
"DJANGO_DEBUG=1",
"DJANGO_SECRET_KEY=replace-with-a-long-random-secret-$OfficeId",
"DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,$DetectedIP,$DeviceName",
"DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:$Port,http://localhost:$Port,http://${DetectedIP}:$Port,http://${DeviceName}:$Port",
"APP_DATA_DIR=$dataDirEnv",
"DB_ENGINE=postgres",
"POSTGRES_HOST=127.0.0.1",
"POSTGRES_PORT=5432",
"POSTGRES_DB=$Database",
"POSTGRES_USER=$PostgresUser",
"POSTGRES_PASSWORD=$PostgresPassword",
"POSTGRES_CONN_MAX_AGE=120",
"LAN_SERVER_HOST=0.0.0.0",
"LAN_SERVER_PORT=$Port",
"LAN_SERVER_PUBLIC_BASE_URL=http://${DetectedIP}:$Port",
"LAN_HEALTH_TOKEN=",
"SESSION_COOKIE_SECURE=0",
"CSRF_COOKIE_SECURE=0",
"BEHIND_REVERSE_PROXY=0",
"WAITRESS_THREADS=8",
"WAITRESS_CONNECTION_LIMIT=100",
"WAITRESS_CHANNEL_TIMEOUT=120",
"DJANGO_LOG_LEVEL=INFO",
"DEV_LOGIN_ENABLED=$DevLoginEnabled",
"DEV_USERNAME=$DevUsername",
"DEV_PASSWORD=$DevPassword",
"DEV_EMAIL=$DevEmail",
"SYNC_MODE=local_office",
"WILAYA_CODE=$WilayaCode",
"COMMUNE_CODE=$CommuneCode",
"OFFICE_CODE=$OfficeCode",
"OFFICE_ALIAS=$OfficeAlias",
"OFFICE_NAME=$OfficeName",
"OFFICE_DISPLAY_NAME=$OfficeDisplayName",
"INSTITUTION_TYPE=$EstablishmentType",
"INSTITUTION_SERIAL=$EstablishmentNumber",
"OFFICE_ID=$OfficeId",
"SERVER_ID=$ServerId",
"CENTRAL_URL=$CentralUrl",
"CENTRAL_SYNC_ENABLED=1",
"SYNC_WORKER_ENABLED=1",
"ALLOW_REMOTE_UPDATES=1",
"UPDATE_SERVER_URL=",
"SYNC_TOKEN=$SyncToken",
"SYNC_TRACKING_ENABLED=1",
"SYNC_TRACKED_MODELS=$trackedModels",
"SYNC_BATCH_SIZE=100",
"SYNC_PULL_LIMIT=100",
"SYNC_CONFLICT_POLICY=last_write_wins",
"SYNC_APPLY_INBOX_ENABLED=1",
"SYNC_APPLY_LIMIT=100",
"AUTO_OPEN_BROWSER=1",
"PREFER_CHROME_BROWSER=1",
"AUTO_OPEN_BROWSER_URL=http://127.0.0.1:$Port",
"AUTO_OPEN_BROWSER_DELAY_SECONDS=2",
"AUTO_OPEN_BROWSER_TIMEOUT_SECONDS=45",
"APP_VERSION=1.0.0",
"CENTRAL_TRAINEE_MANAGER_URL=http://127.0.0.1:$Port/developer/login/",
"CENTRAL_DASHBOARD_URL=http://127.0.0.1:9000/central/"
)
if (-not [string]::IsNullOrWhiteSpace($ChromeExePath)) {
    $envLines += "CHROME_EXE_PATH=$($ChromeExePath.Replace('\','/'))"
}
Set-Content -Path $EnvPath -Value $envLines -Encoding UTF8

Write-Step "Writing start/sync BAT files"
$officeBatLines = @(
"@echo off",
"chcp 65001 >nul",
"cd /d ""$ProjectRoot""",
"set ""ENV_FILE_PATH=$EnvPath""",
"set ""APP_DATA_DIR=$DataDir""",
"set ""AUTO_OPEN_BROWSER=1""",
"set ""AUTO_OPEN_BROWSER_URL=http://127.0.0.1:$Port/""",
"set ""PREFER_CHROME_BROWSER=1""",
"set ""RUN_STARTUP_TASKS=1""",
"echo ==========================================",
"echo Starting $OfficeName on port $Port",
"echo ENV_FILE_PATH=%ENV_FILE_PATH%",
"echo APP_DATA_DIR=%APP_DATA_DIR%",
"echo Auto maintenance: migrate + check on startup",
"echo ==========================================",
""".venv\Scripts\python.exe"" launcher\lan_server.py",
"pause"
)
Set-Content -Path $StartOfficeBat -Value $officeBatLines -Encoding UTF8

$syncBatLines = @(
"@echo off",
"chcp 65001 >nul",
"cd /d ""$ProjectRoot""",
"set ""ENV_FILE_PATH=$EnvPath""",
"set ""APP_DATA_DIR=$DataDir""",
"echo ==========================================",
"echo Sync $OfficeName once",
"echo ENV_FILE_PATH=%ENV_FILE_PATH%",
"echo APP_DATA_DIR=%APP_DATA_DIR%",
"echo Auto maintenance: migrate + check on startup",
"echo ==========================================",
""".venv\Scripts\python.exe"" manage.py sync_worker --once --settings=training_center.settings_lan",
"pause"
)
Set-Content -Path $StartSyncBat -Value $syncBatLines -Encoding UTF8

Write-Step "Writing office shortcuts folder inside project"
$OfficeShortcutsRoot = Join-Path $ProjectRoot "مكاتب_التشغيل"
$OfficeFolderName = New-SafeFolderName $OfficeName $StartName
$OfficeShortcutDir = Join-Path $OfficeShortcutsRoot $OfficeFolderName
New-Item -ItemType Directory -Force $OfficeShortcutDir | Out-Null

$OfficeLocalUrl = "http://127.0.0.1:$Port/"
$OfficeDeveloperUrl = "http://127.0.0.1:$Port/developer/login/"
$OfficeShortcutBat = Join-Path $OfficeShortcutDir "تشغيل_المكتب.bat"
$OfficeShortcutSyncBat = Join-Path $OfficeShortcutDir "مزامنة_المكتب_مرة_واحدة.bat"
$OfficeShortcutUrl = Join-Path $OfficeShortcutDir "رابط_المكتب.url"
$OfficeShortcutTxt = Join-Path $OfficeShortcutDir "رابط_المكتب.txt"

$officeShortcutBatLines = @(
"@echo off",
"chcp 65001 >nul",
"cd /d ""$ProjectRoot""",
"set ""ENV_FILE_PATH=$EnvPath""",
"set ""APP_DATA_DIR=$DataDir""",
"set ""AUTO_OPEN_BROWSER=1""",
"set ""AUTO_OPEN_BROWSER_URL=$OfficeLocalUrl""",
"set ""PREFER_CHROME_BROWSER=1""",
"set ""RUN_STARTUP_TASKS=1""",
"echo ==========================================",
"echo Starting $OfficeName on port $Port",
"echo URL: $OfficeLocalUrl",
"echo ENV_FILE_PATH=%ENV_FILE_PATH%",
"echo APP_DATA_DIR=%APP_DATA_DIR%",
"echo Auto maintenance: migrate + check on startup",
"echo ==========================================",
""".venv\Scripts\python.exe"" launcher\lan_server.py",
"pause"
)
$officeShortcutSyncLines = @(
"@echo off",
"chcp 65001 >nul",
"cd /d ""$ProjectRoot""",
"set ""ENV_FILE_PATH=$EnvPath""",
"set ""APP_DATA_DIR=$DataDir""",
"echo ==========================================",
"echo Sync $OfficeName once",
"echo ENV_FILE_PATH=%ENV_FILE_PATH%",
"echo APP_DATA_DIR=%APP_DATA_DIR%",
"echo Auto maintenance: migrate + check on startup",
"echo ==========================================",
""".venv\Scripts\python.exe"" manage.py sync_worker --once --settings=training_center.settings_lan",
"pause"
)
Set-Content -Path $OfficeShortcutBat -Value $officeShortcutBatLines -Encoding UTF8
Set-Content -Path $OfficeShortcutSyncBat -Value $officeShortcutSyncLines -Encoding UTF8
Set-Content -Path $OfficeShortcutUrl -Value @("[InternetShortcut]", "URL=$OfficeLocalUrl") -Encoding ASCII
Set-Content -Path $OfficeShortcutTxt -Value @(
"رابط دخول المكتب:",
$OfficeLocalUrl,
"",
"رابط دخول المطور إلى المكتب:",
$OfficeDeveloperUrl,
"",
"ملف الإعدادات:",
$EnvPath
) -Encoding UTF8

Write-Step "Running migrations and init_office_identity"
$extra = @{ "ENV_FILE_PATH" = $EnvPath; "APP_DATA_DIR" = $DataDir }
Invoke-Checked $Python @("manage.py","migrate","--settings=training_center.settings_lan") $extra
Invoke-Checked $Python @("manage.py","init_office_identity","--settings=training_center.settings_lan") $extra

Write-Step "Opening firewall port if possible"
try {
    New-NetFirewallRule -DisplayName "TrainingCenter $OfficeId $Port" -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -ErrorAction SilentlyContinue | Out-Null
} catch {}

Write-Host "`nOffice prepared successfully." -ForegroundColor Green
Write-Host "ENV_FILE_PATH=$EnvPath"
Write-Host "OFFICE_CODE=$OfficeCode"
Write-Host "OFFICE_ALIAS=$OfficeAlias"
Write-Host "OFFICE_DISPLAY_NAME=$OfficeDisplayName"
Write-Host "START_OFFICE=$StartOfficeBat"
Write-Host "START_SYNC=$StartSyncBat"
Write-Host "OFFICE_FOLDER=$OfficeShortcutDir"
Write-Host "URL=http://${DetectedIP}:$Port"
