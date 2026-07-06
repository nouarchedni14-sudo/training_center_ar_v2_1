Param(
    [string]$TaskName = "TrainingCenter-LAN-Server",
    [string]$WatchdogTaskName = "TrainingCenter-LAN-Watchdog",
    [string]$AppDataDir = "C:\TrainingCenterData",
    [string]$ProjectRoot = "$PSScriptRoot",
    [string]$PythonExe = "python",
    [string]$RunBatPath = "$PSScriptRoot\run_lan_server.bat",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

if (!(Test-Path $RunBatPath)) {
    throw "لم يتم العثور على ملف التشغيل: $RunBatPath"
}

if (!(Test-Path $AppDataDir)) {
    New-Item -ItemType Directory -Path $AppDataDir -Force | Out-Null
}

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"set APP_DATA_DIR=$AppDataDir && set DJANGO_ENV=lan && call `""$RunBatPath`"`"`"" -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -AtStartup

if ($Force) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $WatchdogTaskName -Confirm:$false -ErrorAction SilentlyContinue
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "تشغيل TrainingCenter كسيرفر LAN عند إقلاع ويندوز" | Out-Null

$watchdogScript = Join-Path $PSScriptRoot "lan_watchdog.ps1"
if (!(Test-Path $watchdogScript)) {
    throw "ملف المراقبة غير موجود: $watchdogScript"
}

$watchdogAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$watchdogScript`" -TaskName `"$TaskName`" -AppDataDir `"$AppDataDir`" -ProjectRoot `"$ProjectRoot`" -RunBatPath `"$RunBatPath`""
$watchdogTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$watchdogTrigger.Repetition = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650) | Select-Object -ExpandProperty Repetition

Register-ScheduledTask -TaskName $WatchdogTaskName -Action $watchdogAction -Trigger $watchdogTrigger -Principal $principal -Settings $settings -Description "مراقبة TrainingCenter-LAN وإعادة تشغيله إذا توقف" | Out-Null

Write-Host "تم تسجيل مهمة تشغيل السيرفر: $TaskName" -ForegroundColor Green
Write-Host "تم تسجيل مهمة المراقبة: $WatchdogTaskName" -ForegroundColor Green
Write-Host "بعدها شغّل المهمة يدويًا أول مرة أو أعد تشغيل الجهاز." -ForegroundColor Yellow
