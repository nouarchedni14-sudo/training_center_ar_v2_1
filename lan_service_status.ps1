Param(
    [string]$AppDataDir = "C:\TrainingCenterData",
    [string]$TaskName = "TrainingCenter-LAN-Server",
    [string]$WatchdogTaskName = "TrainingCenter-LAN-Watchdog"
)

$statusFile = Join-Path $AppDataDir "runtime_state\lan_status.json"
$pidFile = Join-Path $AppDataDir "runtime_state\lan_server.pid"

Write-Host "==== TrainingCenter LAN Status ====" -ForegroundColor Cyan
Write-Host "APP_DATA_DIR: $AppDataDir"

Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Format-Table TaskName, State
Get-ScheduledTask -TaskName $WatchdogTaskName -ErrorAction SilentlyContinue | Format-Table TaskName, State

if (Test-Path $pidFile) {
    $pid = Get-Content $pidFile | Select-Object -First 1
    Write-Host "PID: $pid"
    Get-Process -Id $pid -ErrorAction SilentlyContinue | Format-Table Id, ProcessName, StartTime
} else {
    Write-Host "PID file غير موجود" -ForegroundColor Yellow
}

if (Test-Path $statusFile) {
    Write-Host "--- lan_status.json ---" -ForegroundColor Green
    Get-Content $statusFile -Raw
} else {
    Write-Host "lan_status.json غير موجود" -ForegroundColor Yellow
}
