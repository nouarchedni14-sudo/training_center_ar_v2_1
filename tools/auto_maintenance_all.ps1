param(
    [string]$ProjectRoot = "",
    [switch]$CentralOnly,
    [switch]$OfficesOnly,
    [switch]$CheckOnly,
    [switch]$ContinueOnError,
    [switch]$NoPause
)

$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

function Write-Info([string]$Text) { Write-Host "[INFO] $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "[OK] $Text" -ForegroundColor Green }
function Write-Warn2([string]$Text) { Write-Host "[WARN] $Text" -ForegroundColor Yellow }
function Write-Err2([string]$Text) { Write-Host "[ERROR] $Text" -ForegroundColor Red }

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$ProjectRoot = ([string]$ProjectRoot).Trim().Trim('"').TrimEnd('\')
try {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
} catch {
    Write-Err2 ("ProjectRoot not found: {0}" -f $ProjectRoot)
    exit 2
}
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $Python -PathType Leaf)) { $Python = "python" }
$Manage = Join-Path $ProjectRoot "manage.py"
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "auto_maintenance_$Stamp.log"

function Add-Log([string]$Text) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Text
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Get-EnvValue([string]$Path, [string]$Key, [string]$Default="") {
    if (!(Test-Path $Path)) { return $Default }
    $line = Get-Content $Path -Encoding UTF8 -ErrorAction SilentlyContinue | Where-Object { $_ -match "^$([regex]::Escape($Key))=" } | Select-Object -Last 1
    if (!$line) { return $Default }
    return ($line -replace "^$([regex]::Escape($Key))=", "").Trim().Trim('"').Trim("'")
}

function Invoke-DjangoCommand([string]$Label, [string]$SettingsModule, [string]$DjangoEnv, [string]$AppDataDir, [string]$EnvFilePath, [string[]]$CommandArgs) {
    Write-Info ("{0} -> python manage.py {1}" -f $Label, ($CommandArgs -join " "))
    Add-Log ("START {0} :: manage.py {1}" -f $Label, ($CommandArgs -join " "))

    $old = @{}
    foreach ($pair in @{
        "DJANGO_SETTINGS_MODULE" = $SettingsModule
        "DJANGO_ENV" = $DjangoEnv
        "APP_DATA_DIR" = $AppDataDir
        "ENV_FILE_PATH" = $EnvFilePath
    }.GetEnumerator()) {
        $old[$pair.Key] = [Environment]::GetEnvironmentVariable($pair.Key, "Process")
        [Environment]::SetEnvironmentVariable($pair.Key, [string]$pair.Value, "Process")
    }

    try {
        & $Python $Manage @CommandArgs --settings=$SettingsModule 2>&1 | Tee-Object -FilePath $LogFile -Append
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            Write-Err2 ("{0} failed: manage.py {1} - code: {2}" -f $Label, ($CommandArgs -join " "), $code)
            Add-Log ("FAILED {0} code={1}" -f $Label, $code)
            return $false
        }
        Write-Ok ("{0} OK: {1}" -f $Label, ($CommandArgs -join " "))
        Add-Log ("OK {0}" -f $Label)
        return $true
    } finally {
        foreach ($k in $old.Keys) { [Environment]::SetEnvironmentVariable($k, $old[$k], "Process") }
    }
}

function Invoke-DjangoMaintenance([string]$Label, [string]$SettingsModule, [string]$DjangoEnv, [string]$AppDataDir, [string]$EnvFilePath) {
    $success = $true
    if (!(Test-Path $EnvFilePath -PathType Leaf)) {
        Write-Warn2 ("{0}: env file not found: {1}" -f $Label, $EnvFilePath)
        Add-Log ("SKIP {0} missing env {1}" -f $Label, $EnvFilePath)
        return $true
    }
    if (-not $CheckOnly) {
        $success = (Invoke-DjangoCommand $Label $SettingsModule $DjangoEnv $AppDataDir $EnvFilePath @("migrate","--noinput")) -and $success
        if ($SettingsModule -eq "training_center.settings_central") {
            $success = (Invoke-DjangoCommand $Label $SettingsModule $DjangoEnv $AppDataDir $EnvFilePath @("import_algeria_cities","--quiet")) -and $success
            $success = (Invoke-DjangoCommand $Label $SettingsModule $DjangoEnv $AppDataDir $EnvFilePath @("seed_office_units","--all","--quiet")) -and $success
        }
    }
    $success = (Invoke-DjangoCommand $Label $SettingsModule $DjangoEnv $AppDataDir $EnvFilePath @("check")) -and $success
    return $success
}

Write-Host "============================================================" -ForegroundColor White
Write-Host "AUTO MAINTENANCE - Training Center" -ForegroundColor White
Write-Host "Project: $ProjectRoot" -ForegroundColor White
Write-Host "Log:     $LogFile" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor White
Add-Log "AUTO MAINTENANCE START Project=$ProjectRoot"

$failures = New-Object System.Collections.Generic.List[string]

if (-not $OfficesOnly) {
    $centralDir = "C:\TrainingCenterCentralData"
    $centralEnv = Join-Path $centralDir ".env"
    if (Test-Path $centralEnv -PathType Leaf) {
        $ok = Invoke-DjangoMaintenance "Central server" "training_center.settings_central" "central" $centralDir $centralEnv
        if (-not $ok) { [void]$failures.Add("Central server") }
    } else {
        Write-Warn2 ("Central env file not found: {0}" -f $centralEnv)
        Add-Log "SKIP central missing env"
    }
}

if (-not $CentralOnly) {
    $officeDirs = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in @("C:\TrainingCenterData")) {
        if ((Test-Path (Join-Path $candidate ".env") -PathType Leaf) -and $candidate -ne "C:\TrainingCenterCentralData") {
            [void]$officeDirs.Add($candidate)
        }
    }
    Get-ChildItem -Path "C:\" -Directory -Filter "TrainingCenterData_*" -ErrorAction SilentlyContinue | ForEach-Object {
        $envPath = Join-Path $_.FullName ".env"
        if (Test-Path $envPath -PathType Leaf) { [void]$officeDirs.Add($_.FullName) }
    }

    $officeDirs = $officeDirs | Sort-Object -Unique
    if (-not $officeDirs -or $officeDirs.Count -eq 0) {
        Write-Warn2 "No local offices found under C:\TrainingCenterData_* with .env"
        Add-Log "NO OFFICES FOUND"
    } else {
        foreach ($dir in $officeDirs) {
            $envPath = Join-Path $dir ".env"
            $dbEngine = Get-EnvValue $envPath "DB_ENGINE" ""
            if ($dbEngine -and $dbEngine.ToLowerInvariant() -notin @("postgres","postgresql")) {
                Write-Warn2 ("Skipping {0} because DB_ENGINE={1}" -f $dir, $dbEngine)
                Add-Log ("SKIP {0} DB_ENGINE={1}" -f $dir, $dbEngine)
                continue
            }
            $officeName = Get-EnvValue $envPath "OFFICE_NAME" ""
            if ([string]::IsNullOrWhiteSpace($officeName)) { $officeName = Split-Path $dir -Leaf }
            $label = "Office: {0} ({1})" -f $officeName, $dir
            $ok = Invoke-DjangoMaintenance $label "training_center.settings_lan" "lan" $dir $envPath
            if (-not $ok) { [void]$failures.Add($label) }
        }
    }
}

Write-Host "============================================================" -ForegroundColor White
if ($failures.Count -gt 0) {
    Write-Err2 ("Maintenance finished with errors in: {0}" -f ($failures -join ', '))
    Add-Log ("AUTO MAINTENANCE FAILED {0}" -f ($failures -join ', '))
    Write-Host ("Log: {0}" -f $LogFile) -ForegroundColor Yellow
    if ($ContinueOnError) { exit 0 } else { exit 1 }
} else {
    Write-Ok "Maintenance finished successfully for all available environments."
    Add-Log "AUTO MAINTENANCE OK"
    Write-Host ("Log: {0}" -f $LogFile) -ForegroundColor Gray
    exit 0
}
