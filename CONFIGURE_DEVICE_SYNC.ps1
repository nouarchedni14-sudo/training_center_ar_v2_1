param(
    [string]$CentralUrl = "",
    [string]$AppDataDir = "C:\TrainingCenterData"
)

$ErrorActionPreference = "Stop"
$envPath = Join-Path $AppDataDir ".env"
if (-not (Test-Path $envPath)) {
    New-Item -ItemType Directory -Force -Path $AppDataDir | Out-Null
    New-Item -ItemType File -Force -Path $envPath | Out-Null
}

function Set-EnvValue([string]$Path, [string]$Key, [string]$Value) {
    $lines = @()
    if (Test-Path $Path) { $lines = Get-Content -Path $Path -Encoding UTF8 }
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") {
            $found = $true
            "$Key=$Value"
        } else {
            $line
        }
    }
    if (-not $found) { $out += "$Key=$Value" }
    Set-Content -Path $Path -Value $out -Encoding UTF8
}

if (-not $CentralUrl) { $CentralUrl = Read-Host "اكتب CENTRAL_URL الخاص بجهاز المطوّر/الخادم المركزي مثل http://192.168.1.10:9000" }

$deviceId = "device-{0}-{1}" -f ($env:COMPUTERNAME.ToLower() -replace '[^a-z0-9]+','-'), ([guid]::NewGuid().ToString('N').Substring(0,8))
$secret = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).TrimEnd('=').Replace('+','-').Replace('/','_')

Set-EnvValue $envPath "SYNC_MODE" "local_office"
Set-EnvValue $envPath "OFFICE_NAME" ""
Set-EnvValue $envPath "OFFICE_ID" ""
Set-EnvValue $envPath "SERVER_ID" $deviceId
Set-EnvValue $envPath "DEVICE_NODE_MODE" "1"
Set-EnvValue $envPath "DEVICE_NODE_INITIALIZED" "1"
Set-EnvValue $envPath "DEVICE_REQUEST_SECRET" $secret
Set-EnvValue $envPath "CENTRAL_URL" $CentralUrl
Set-EnvValue $envPath "CENTRAL_SYNC_ENABLED" "0"
Set-EnvValue $envPath "SYNC_WORKER_ENABLED" "0"
Set-EnvValue $envPath "IN_PROCESS_SYNC_WORKER_ENABLED" "1"
Set-EnvValue $envPath "SYNC_WORKER_INTERVAL_SECONDS" "120"
Set-EnvValue $envPath "ALLOW_REMOTE_UPDATES" "1"
Set-EnvValue $envPath "UPDATE_SERVER_URL" ""
Set-EnvValue $envPath "SYNC_TOKEN" ""
Set-EnvValue $envPath "SYNC_TRACKING_ENABLED" "1"
Set-EnvValue $envPath "SYNC_APPLY_INBOX_ENABLED" "1"
Set-EnvValue $envPath "SYNC_TRACKED_MODELS" "trainees.حضوري_أولي,trainees.تمهين,trainees.دفعة,trainees.مسائي_ومعابر"

Write-Host "تم ضبط الجهاز لطلب الربط من المطوّر."
Write-Host "ملف الإعداد: $envPath"
Write-Host "SERVER_ID: $deviceId"
Write-Host "الخطوة التالية: شغّل البرنامج، ثم اعتمد الجهاز من لوحة المطوّر > طلبات ربط الأجهزة."
