param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$false)][string]$EnvFile = "",
    [Parameter(Mandatory=$false)][int]$DelaySeconds = 2
)

# يفتح الرابط في Google Chrome أولًا. إذا لم يجد Chrome يستعمل المتصفح الافتراضي.
# يستعمل CHROME_EXE_PATH من ملف .env إذا كان موجودًا، ثم يبحث في Registry والمسارات المعروفة.

try {
    if ($DelaySeconds -gt 0) { Start-Sleep -Seconds $DelaySeconds }
} catch {}

$candidates = New-Object 'System.Collections.Generic.List[string]'

function Add-Candidate([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    $Path = $Path.Trim()
    if ($Path.StartsWith('"') -and $Path.EndsWith('"') -and $Path.Length -gt 1) {
        $Path = $Path.Substring(1, $Path.Length - 2)
    }
    if (-not $candidates.Contains($Path)) { [void]$candidates.Add($Path) }
}

# 1) مسار يدوي من .env
try {
    if ($EnvFile -and (Test-Path -LiteralPath $EnvFile)) {
        foreach ($line in [System.IO.File]::ReadLines($EnvFile)) {
            if ($line -match '^\s*CHROME_EXE_PATH\s*=(.*)$') {
                Add-Candidate $Matches[1]
            }
        }
    }
} catch {}

# 2) Windows Registry
foreach ($key in @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe'
)) {
    try {
        $props = Get-ItemProperty -LiteralPath $key -ErrorAction Stop
        Add-Candidate $props.'(default)'
        Add-Candidate $props.Path
    } catch {}
}

# 3) المسارات المعروفة
$pf = [Environment]::GetEnvironmentVariable('ProgramFiles')
$pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
$local = [Environment]::GetEnvironmentVariable('LOCALAPPDATA')
if ($pf) { Add-Candidate (Join-Path $pf 'Google\Chrome\Application\chrome.exe') }
if ($pf86) { Add-Candidate (Join-Path $pf86 'Google\Chrome\Application\chrome.exe') }
if ($local) { Add-Candidate (Join-Path $local 'Google\Chrome\Application\chrome.exe') }
Add-Candidate 'C:\Program Files\Google\Chrome\Application\chrome.exe'
Add-Candidate 'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'

# 4) PATH إن كان chrome.exe مضافًا إليه
try {
    $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if ($cmd) { Add-Candidate $cmd.Source }
} catch {}

foreach ($chrome in $candidates) {
    try {
        if ($chrome -and (Test-Path -LiteralPath $chrome)) {
            Start-Process -FilePath $chrome -ArgumentList @('--new-window', $Url)
            exit 0
        }
    } catch {}
}

# fallback: المتصفح الافتراضي
Start-Process $Url
