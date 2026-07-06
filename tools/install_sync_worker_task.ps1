param(
    [string]$ProjectRoot = "",
    [int]$IntervalMinutes = 5,
    [string]$TaskName = "TrainingCenter Sync Worker"
)

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ManagePy = Join-Path $ProjectRoot "manage.py"

if (!(Test-Path $PythonExe)) {
    Write-Error "Python virtualenv not found: $PythonExe"
    exit 1
}
if (!(Test-Path $ManagePy)) {
    Write-Error "manage.py not found: $ManagePy"
    exit 1
}

$Arguments = "manage.py sync_worker --once --settings=training_center.settings_lan"
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Arguments -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "TrainingCenter local office sync worker" | Out-Null
    Write-Host "Task created: $TaskName"
    Write-Host "ProjectRoot: $ProjectRoot"
    Write-Host "Interval: every $IntervalMinutes minutes"
    Write-Host "You can test it from Task Scheduler by choosing Run."
} catch {
    Write-Error $_
    exit 1
}
