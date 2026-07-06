Param(
    [string]$AppDataDir = "C:\TrainingCenterData",
    [string]$ProjectRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

$folders = @(
    $AppDataDir,
    (Join-Path $AppDataDir "media"),
    (Join-Path $AppDataDir "logs"),
    (Join-Path $AppDataDir "staticfiles"),
    (Join-Path $AppDataDir "backups"),
    (Join-Path $AppDataDir "tmp_imports"),
    (Join-Path $AppDataDir "local_updates"),
    (Join-Path $AppDataDir "runtime_state")
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
    }
}

$envTarget = Join-Path $AppDataDir ".env"
if (-not (Test-Path $envTarget)) {
    $example1 = Join-Path $ProjectRoot ".env.lan.example"
    $example2 = Join-Path $ProjectRoot ".env.example"

    if (Test-Path $example1) {
        Copy-Item $example1 $envTarget -Force
    } elseif (Test-Path $example2) {
        Copy-Item $example2 $envTarget -Force
    } else {
        @"
DJANGO_ENV=lan
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=change-me-for-lan-server
DB_ENGINE=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=training_center
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
APP_DATA_DIR=C:/TrainingCenterData
LAN_SERVER_HOST=0.0.0.0
LAN_SERVER_PORT=8000
LAN_SERVER_PUBLIC_BASE_URL=http://127.0.0.1:8000
DEV_LOGIN_ENABLED=0
"@ | Set-Content -Encoding UTF8 $envTarget
    }
}

Write-Host "LAN data folders prepared automatically:" -ForegroundColor Green
foreach ($folder in $folders) {
    Write-Host " - $folder"
}
Write-Host " - $envTarget"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1) Edit PostgreSQL settings inside $envTarget"
Write-Host "2) Copy your current media folder into $AppDataDir\media"
Write-Host "3) Run: python manage.py migrate --settings=training_center.settings_lan"
Write-Host "4) Run: python manage.py collectstatic --noinput --settings=training_center.settings_lan"
Write-Host "5) Run: python launcher/lan_server.py"
