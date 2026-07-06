Param(
    [string]$TaskName = "TrainingCenter-LAN-Server",
    [string]$AppDataDir = "C:\TrainingCenterData",
    [string]$ProjectRoot = "$PSScriptRoot",
    [string]$RunBatPath = "$PSScriptRoot\run_lan_server.bat"
)

$ErrorActionPreference = 'SilentlyContinue'
$statusFile = Join-Path $AppDataDir "runtime_state\lan_status.json"
$pidFile = Join-Path $AppDataDir "runtime_state\lan_server.pid"
$logFile = Join-Path $AppDataDir "logs\lan_watchdog.log"

function Write-WatchdogLog([string]$Message) {
    $dir = Split-Path $logFile -Parent
    if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Add-Content -Path $logFile -Value "[$((Get-Date).ToString('s'))] $Message"
}

$shouldRestart = $false

if (!(Test-Path $pidFile)) {
    $shouldRestart = $true
    Write-WatchdogLog "PID file غير موجود، ستتم محاولة إعادة التشغيل."
} else {
    $pid = Get-Content $pidFile | Select-Object -First 1
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        $shouldRestart = $true
        Write-WatchdogLog "العملية المسجلة في PID file متوقفة."
    }
}

if (Test-Path $statusFile) {
    try {
        $status = Get-Content $statusFile -Raw | ConvertFrom-Json
        if ($status.status -eq 'failed') {
            $shouldRestart = $true
            Write-WatchdogLog "السيرفر سجل حالة failed داخل lan_status.json"
        }
    } catch {
        Write-WatchdogLog "تعذر قراءة lan_status.json"
    }
}

if ($shouldRestart) {
    Write-WatchdogLog "إطلاق مهمة السيرفر: $TaskName"
    Start-ScheduledTask -TaskName $TaskName | Out-Null
}
