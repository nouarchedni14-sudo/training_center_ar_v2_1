param(
    [string]$InstallerPath = "",
    [string]$SuperPassword = "123456",
    [int]$Port = 5432,
    [int]$FallbackPort = 5433,
    [string]$AppDataDir = "C:\TrainingCenterData"
)

$ErrorActionPreference = "Stop"
$ProgramDataRoot = Join-Path $env:ProgramData "TrainingCenterOfficeServer"
$LogDir = Join-Path $ProgramDataRoot "logs"
$ReadyMarker = Join-Path $ProgramDataRoot "postgres_ready.ok"
$FailMarker = Join-Path $ProgramDataRoot "postgres_failed.txt"
$LogFile = Join-Path $LogDir "postgres_install.log"
$AppEnvPath = Join-Path $AppDataDir ".env"
$SupportedMajors = @(18,17,16,15)

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log([string]$message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $message
}

function Fail-Install([int]$errCode, [string]$message) {
    Write-Log ("ERROR {0}: {1}" -f $errCode, $message)
    Set-Content -Path $FailMarker -Value $message -Encoding UTF8
    if (Test-Path $ReadyMarker) { Remove-Item $ReadyMarker -Force -ErrorAction SilentlyContinue }
    exit $errCode
}

function Mark-Ready([string]$message) {
    Set-Content -Path $ReadyMarker -Value $message -Encoding UTF8
    if (Test-Path $FailMarker) { Remove-Item $FailMarker -Force -ErrorAction SilentlyContinue }
    Write-Log $message
}

function New-RandomPassword {
    $bytes = New-Object byte[] 18
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ([Convert]::ToBase64String($bytes) -replace '[^a-zA-Z0-9]', '').Substring(0, 20)
}

function Get-InstallerMajor([string]$path) {
    $name = [System.IO.Path]::GetFileName($path)
    if ($name -match 'postgresql-(\d+)([\.\-]|$)') { return [int]$Matches[1] }
    return 0
}

function Find-BundledInstaller {
    if ($InstallerPath -and (Test-Path $InstallerPath)) { return (Resolve-Path $InstallerPath).Path }
    $scriptRoot = Split-Path -Parent $PSCommandPath
    $appRoot = Split-Path -Parent $scriptRoot
    $pgDir = Join-Path $appRoot "third_party\postgresql"
    if (-not (Test-Path $pgDir)) { return "" }
    $items = Get-ChildItem -Path $pgDir -Filter "postgresql-*-windows-x64*.exe" -File -ErrorAction SilentlyContinue
    $valid = @()
    foreach ($item in $items) {
        $major = Get-InstallerMajor $item.FullName
        if ($SupportedMajors -contains $major) { $valid += $item }
    }
    if (-not $valid -or $valid.Count -eq 0) { return "" }
    return ($valid | Sort-Object @{Expression={Get-InstallerMajor $_.FullName};Descending=$true}, Name -Descending | Select-Object -First 1).FullName
}

function Get-PostgresServices {
    $items = @()
    foreach ($major in $SupportedMajors) {
        foreach ($name in @("postgresql-x64-$major-trainingcenter", "postgresql-x64-$major")) {
            $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
            if ($svc) { $items += $svc }
        }
    }
    $any = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
    foreach ($svc in $any) {
        if (-not ($items | Where-Object { $_.Name -eq $svc.Name })) { $items += $svc }
    }
    return $items | Sort-Object Name -Descending
}

function Start-PostgresServiceIfNeeded($svc) {
    if ($svc -and $svc.Status -ne "Running") {
        Write-Log ("Starting PostgreSQL service: {0}" -f $svc.Name)
        try { Start-Service -Name $svc.Name -ErrorAction Stop } catch { Write-Log ("Could not start service directly: {0}" -f $_) }
    }
    if ($svc) {
        for ($i = 0; $i -lt 30; $i++) {
            $s = Get-Service -Name $svc.Name -ErrorAction SilentlyContinue
            if ($s -and $s.Status -eq "Running") { return $true }
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

function Find-PsqlExe {
    $cmd = Get-Command "psql.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        "C:\Program Files\PostgreSQL\18\bin\psql.exe",
        "C:\Program Files\PostgreSQL\17\bin\psql.exe",
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files\TrainingCenterPostgreSQL\18\bin\psql.exe",
        "C:\Program Files\TrainingCenterPostgreSQL\17\bin\psql.exe",
        "C:\Program Files\TrainingCenterPostgreSQL\16\bin\psql.exe",
        "C:\Program Files\TrainingCenterPostgreSQL\15\bin\psql.exe"
    )
    foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($root in $roots) {
        if (Test-Path $root) {
            $found = Get-ChildItem -Path $root -Recurse -Filter "psql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
            if ($found) { return $found.FullName }
        }
    }
    return ""
}

function Test-TcpPort([int]$TestPort) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect("127.0.0.1", $TestPort, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(1200, $false)
        if ($ok) { $client.EndConnect($iar) }
        $client.Close()
        return $ok
    } catch { return $false }
}

function Test-PostgresLogin([int]$TestPort, [string]$Password) {
    $psql = Find-PsqlExe
    if (-not $psql -or -not (Test-Path $psql)) {
        Write-Log "psql.exe was not found."
        return $false
    }
    if (-not (Test-TcpPort $TestPort)) {
        Write-Log ("TCP port {0} is not open." -f $TestPort)
        return $false
    }

    $out = Join-Path $env:TEMP ("tc_pg_ok_{0}.txt" -f $TestPort)
    $err = Join-Path $env:TEMP ("tc_pg_err_{0}.txt" -f $TestPort)
    Remove-Item $out,$err -Force -ErrorAction SilentlyContinue
    $env:PGPASSWORD = $Password
    try {
        $args = @("-h", "127.0.0.1", "-p", "$TestPort", "-U", "postgres", "-d", "postgres", "-w", "-t", "-A", "-c", "SELECT 1;")
        $p = Start-Process -FilePath $psql -ArgumentList $args -PassThru -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
        $finished = $p.WaitForExit(15000)
        if (-not $finished) {
            try { $p.Kill() } catch {}
            Write-Log ("psql test timed out on port {0}." -f $TestPort)
            return $false
        }
        $stdout = if (Test-Path $out) { (Get-Content $out -Raw -ErrorAction SilentlyContinue).Trim() } else { "" }
        $stderr = if (Test-Path $err) { (Get-Content $err -Raw -ErrorAction SilentlyContinue).Trim() } else { "" }
        if ($p.ExitCode -eq 0 -and $stdout -match "1") {
            Write-Log ("PostgreSQL login OK on port {0}." -f $TestPort)
            return $true
        }
        if ($stderr) { Write-Log ("psql error on port {0}: {1}" -f $TestPort, $stderr) }
        return $false
    } catch {
        Write-Log ("psql test exception on port {0}: {1}" -f $TestPort, $_)
        return $false
    } finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        Remove-Item $out,$err -Force -ErrorAction SilentlyContinue
    }
}

function Set-EnvValue([string]$Key, [string]$Value) {
    New-Item -ItemType Directory -Force -Path $AppDataDir | Out-Null
    $lines = @()
    if (Test-Path $AppEnvPath) { $lines = Get-Content $AppEnvPath -Encoding UTF8 }
    $found = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") { $found = $true; "$Key=$Value" } else { $line }
    }
    if (-not $found) { $newLines += "$Key=$Value" }
    Set-Content -Path $AppEnvPath -Value $newLines -Encoding UTF8
}

function Get-EmbeddedCentralUrl {
    try {
        $scriptRoot = Split-Path -Parent $PSCommandPath
        $appRoot = Split-Path -Parent $scriptRoot
        $candidates = @(
            (Join-Path $appRoot "CENTRAL_URL_FOR_INSTALLER.txt"),
            (Join-Path $appRoot "central_url_for_installer.txt"),
            (Join-Path $appRoot ".central_url")
        )
        foreach ($candidate in $candidates) {
            if (Test-Path $candidate) {
                $value = (Get-Content -Path $candidate -Raw -Encoding UTF8).Trim()
                if ($value -and $value -match '^https?://') { return $value.TrimEnd('/') }
            }
        }
    } catch {}
    return ""
}

function Ensure-StandardSyncEnv {
    $central = Get-EmbeddedCentralUrl
    if ($central) { Set-EnvValue "CENTRAL_URL" $central }
    Set-EnvValue "DEVICE_NODE_MODE" "1"
    if (-not ((Test-Path $AppEnvPath) -and ((Get-Content $AppEnvPath -Raw) -match '(?m)^DEVICE_NODE_INITIALIZED='))) { Set-EnvValue "DEVICE_NODE_INITIALIZED" "0" }
    if (-not ((Test-Path $AppEnvPath) -and ((Get-Content $AppEnvPath -Raw) -match '(?m)^SERVER_ID='))) { Set-EnvValue "SERVER_ID" "auto" }
    Set-EnvValue "IN_PROCESS_SYNC_WORKER_ENABLED" "1"
    if (-not ((Test-Path $AppEnvPath) -and ((Get-Content $AppEnvPath -Raw) -match '(?m)^SYNC_WORKER_INTERVAL_SECONDS='))) { Set-EnvValue "SYNC_WORKER_INTERVAL_SECONDS" "120" }
    Set-EnvValue "SYNC_TRACKING_ENABLED" "1"
    Set-EnvValue "SYNC_APPLY_INBOX_ENABLED" "1"
    Set-EnvValue "SYNC_TRACKED_MODELS" "trainees.حضوري_أولي,trainees.تمهين,trainees.دفعة,trainees.مسائي_ومعابر"
}

function Ensure-BaseEnv([int]$DbPort, [string]$Password) {
    New-Item -ItemType Directory -Force -Path $AppDataDir | Out-Null
    if (-not (Test-Path $AppEnvPath)) {
        $secret = New-RandomPassword
        $content = @(
            "DJANGO_ENV=lan",
            "DJANGO_DEBUG=0",
            "DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost",
            "DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000",
            "DJANGO_SECRET_KEY=$secret",
            "DB_ENGINE=postgres",
            "POSTGRES_HOST=127.0.0.1",
            "POSTGRES_PORT=$DbPort",
            "POSTGRES_DB=training_center",
            "POSTGRES_USER=postgres",
            "POSTGRES_PASSWORD=$Password",
            "POSTGRES_CONN_MAX_AGE=120",
            "APP_DATA_DIR=$($AppDataDir.Replace('\\','/'))",
            "LAN_SERVER_HOST=0.0.0.0",
            "LAN_SERVER_PORT=8000",
            "RUN_STARTUP_TASKS=1",
            "DEV_LOGIN_ENABLED=0",
            "DEVICE_NODE_MODE=1",
            "DEVICE_NODE_INITIALIZED=0",
            "SERVER_ID=auto",
            "OFFICE_ID=",
            "OFFICE_NAME=",
            "CENTRAL_URL=$(Get-EmbeddedCentralUrl)",
            "CENTRAL_SYNC_ENABLED=0",
            "SYNC_WORKER_ENABLED=0",
            "IN_PROCESS_SYNC_WORKER_ENABLED=1",
            "SYNC_WORKER_INTERVAL_SECONDS=120",
            "SYNC_TRACKING_ENABLED=1",
            "SYNC_APPLY_INBOX_ENABLED=1",
            "SYNC_TRACKED_MODELS=trainees.حضوري_أولي,trainees.تمهين,trainees.دفعة,trainees.مسائي_ومعابر",
            "SYNC_TOKEN=",
            "DEVICE_TOKEN=",
            "DEVICE_REQUEST_SECRET=",
            "AUTO_OPEN_BROWSER=1",
            "PREFER_CHROME_BROWSER=1",
            "AUTO_OPEN_BROWSER_DELAY_SECONDS=2",
            "AUTO_OPEN_BROWSER_TIMEOUT_SECONDS=60"
        )
        Set-Content -Path $AppEnvPath -Value $content -Encoding UTF8
    } else {
        Set-EnvValue "POSTGRES_HOST" "127.0.0.1"
        Set-EnvValue "POSTGRES_PORT" "$DbPort"
        Set-EnvValue "POSTGRES_DB" "training_center"
        Set-EnvValue "POSTGRES_USER" "postgres"
        Set-EnvValue "POSTGRES_PASSWORD" "$Password"
        Set-EnvValue "DB_ENGINE" "postgres"
        Set-EnvValue "APP_DATA_DIR" $($AppDataDir.Replace('\\','/'))
        Set-EnvValue "DEV_LOGIN_ENABLED" "0"
        if (-not ((Get-Content $AppEnvPath -Raw) -match "(?m)^AUTO_OPEN_BROWSER=")) { Set-EnvValue "AUTO_OPEN_BROWSER" "1" }
        if (-not ((Get-Content $AppEnvPath -Raw) -match "(?m)^PREFER_CHROME_BROWSER=")) { Set-EnvValue "PREFER_CHROME_BROWSER" "1" }
    }
    Ensure-StandardSyncEnv
}

function Get-AvailablePort {
    if (-not (Test-TcpPort $Port)) { return $Port }
    if (-not (Test-TcpPort $FallbackPort)) { return $FallbackPort }
    return $Port
}

function Run-VisiblePostgresInstaller([string]$Installer, [int]$DbPort) {
    $sizeMb = [math]::Round((Get-Item $Installer).Length / 1MB, 1)
    if ($sizeMb -lt 100) { Fail-Install 23 ("PostgreSQL installer is too small ({0} MB). It is probably incomplete." -f $sizeMb) }
    Write-Log ("Opening PostgreSQL installer only because no usable PostgreSQL service/port was detected. Installer: {0}" -f $Installer)
    $p = Start-Process -FilePath $Installer -Wait -PassThru
    Write-Log ("Visible PostgreSQL installer exit code: {0}" -f $p.ExitCode)
}

try {
    Remove-Item $ReadyMarker,$FailMarker -Force -ErrorAction SilentlyContinue
    Write-Log "Starting PostgreSQL check/install for Training Center."

    $services = @(Get-PostgresServices)
    foreach ($svc in $services) {
        Write-Log ("Detected PostgreSQL service: {0} / {1}" -f $svc.Name, $svc.Status)
        Start-PostgresServiceIfNeeded $svc | Out-Null
    }

    # IMPORTANT: Always test the real connection first. If it works, never open the PostgreSQL installer.
    foreach ($tryPort in @($Port, $FallbackPort)) {
        if (Test-PostgresLogin $tryPort $SuperPassword) {
            Ensure-BaseEnv $tryPort $SuperPassword
            Mark-Ready ("Existing PostgreSQL verified on port {0} with password 123456. No reinstall needed." -f $tryPort)
            exit 0
        }
    }

    if ($services.Count -gt 0 -or (Test-TcpPort $Port) -or (Test-TcpPort $FallbackPort)) {
        Fail-Install 31 "PostgreSQL exists, but the installer could not connect with password 123456 on ports 5432/5433. It will NOT reinstall to avoid upgrade-mode problems. Fix the postgres password or remove the old PostgreSQL completely, then run setup again."
    }

    $installer = Find-BundledInstaller
    if (-not $installer -or -not (Test-Path $installer)) { Fail-Install 20 "Bundled PostgreSQL installer was not found." }

    $dbPort = Get-AvailablePort
    Run-VisiblePostgresInstaller $installer $dbPort

    Start-Sleep -Seconds 5
    $services = @(Get-PostgresServices)
    foreach ($svc in $services) { Start-PostgresServiceIfNeeded $svc | Out-Null }

    foreach ($tryPort in @($dbPort, $Port, $FallbackPort)) {
        if (Test-PostgresLogin $tryPort $SuperPassword) {
            Ensure-BaseEnv $tryPort $SuperPassword
            Mark-Ready ("PostgreSQL ready on port {0}." -f $tryPort)
            exit 0
        }
    }

    Fail-Install 25 ("PostgreSQL was installed or detected, but connection with password 123456 failed. Log: $LogFile")
} catch {
    Fail-Install 99 ("Exception during PostgreSQL setup: {0}" -f $_)
}
