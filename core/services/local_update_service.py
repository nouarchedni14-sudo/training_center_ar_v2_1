from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings

from core.services.advanced_update_service import calculate_sha256, verify_manifest_signature

try:
    from launcher.runtime_state import app_data_dir, read_runtime_state
except Exception:  # noqa: BLE001
    def app_data_dir() -> Path:
        base = Path(getattr(settings, "BASE_DIR", ".")).resolve()
        path = base / ".desktop_runtime"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def read_runtime_state() -> dict:
        return {}


MANIFEST_NAME = "manifest.json"
STATE_FILE_NAME = "pending_update_state.json"
ALLOWED_REMOTE_SUFFIXES = {".zip", ".exe", ".msi"}


def get_runtime_root() -> Path:
    state = read_runtime_state()
    runtime_root = state.get("runtime_root")
    if runtime_root:
        return Path(runtime_root).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(settings.BASE_DIR).resolve()


def get_updates_root() -> Path:
    root = app_data_dir() / "local_updates"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_packages_root() -> Path:
    path = get_updates_root() / "packages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_extracted_root() -> Path:
    path = get_updates_root() / "extracted"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_scripts_root() -> Path:
    path = get_updates_root() / "scripts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_root() -> Path:
    path = get_updates_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_state_path() -> Path:
    return get_updates_root() / STATE_FILE_NAME


def parse_version(value: str) -> tuple[int, ...]:
    cleaned = (value or "").strip().replace("v", "")
    parts: list[int] = []
    for token in cleaned.split('.'):
        token = ''.join(ch for ch in token if ch.isdigit())
        parts.append(int(token) if token else 0)
    return tuple(parts or [0])


def cleanup_old_pending() -> None:
    for path in (get_packages_root(), get_extracted_root()):
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)


def _safe_extract(zip_path: Path, extract_to: Path) -> None:
    extract_to.mkdir(parents=True, exist_ok=True)
    base_dir = extract_to.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = extract_to / member.filename
            resolved = member_path.resolve()
            try:
                resolved.relative_to(base_dir)
            except ValueError as exc:
                raise ValueError("ملف التحديث يحتوي على مسارات غير آمنة.") from exc
        zf.extractall(extract_to)


def find_manifest(extracted_dir: Path) -> Path | None:
    direct = extracted_dir / MANIFEST_NAME
    if direct.exists():
        return direct
    for path in extracted_dir.rglob(MANIFEST_NAME):
        return path
    return None


def load_manifest(extracted_dir: Path) -> dict[str, Any]:
    manifest_path = find_manifest(extracted_dir)
    if not manifest_path:
        raise ValueError("ملف التحديث لا يحتوي على manifest.json.")
    data = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError("ملف manifest.json غير صالح.")
    if not data.get("version"):
        raise ValueError("ملف manifest.json يجب أن يحتوي على version.")
    ok, message = verify_manifest_signature(data)
    if not ok:
        raise ValueError(message)
    return data


def find_payload_dir(extracted_dir: Path) -> Path:
    direct = extracted_dir / 'app'
    if direct.exists() and direct.is_dir():
        return direct
    for path in extracted_dir.rglob('app'):
        if path.is_dir():
            return path
    raise ValueError("ملف التحديث لا يحتوي على مجلد app للملفات الجديدة.")




def _filename_from_url(download_url: str, fallback: str = "remote_update") -> str:
    parsed = urlparse(download_url or "")
    name = Path(parsed.path).name or fallback
    return name


def save_uploaded_zip(uploaded_file) -> Path:
    cleanup_old_pending()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = get_packages_root() / f"update_{timestamp}.zip"
    with target.open('wb') as fh:
        for chunk in uploaded_file.chunks():
            fh.write(chunk)
    return target


def _download_remote_package(download_url: str, package_name: str = "", request_headers: dict[str, str] | None = None) -> Path:
    if not download_url:
        raise ValueError("رابط تنزيل التحديث غير متوفر.")
    cleanup_old_pending()
    name = package_name.strip() or _filename_from_url(download_url)
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_REMOTE_SUFFIXES:
        raise ValueError("نوع ملف التحديث البعيد غير مدعوم. يجب أن يكون ZIP أو EXE أو MSI.")
    target = get_packages_root() / name
    headers = {str(k): str(v) for k, v in (request_headers or {}).items() if str(k).strip() and str(v).strip()}
    request = Request(download_url, headers=headers)
    with urlopen(request, timeout=60) as response, target.open('wb') as fh:
        while True:
            chunk = response.read(1024 * 512)
            if not chunk:
                break
            fh.write(chunk)
    return target



def _ps_quote(value: Path | str) -> str:
    return str(value).replace("'", "''")


def _relaunch_details() -> tuple[str, list[str], str]:
    state = read_runtime_state() or {}

    executable = str(state.get("relaunch_executable") or "").strip()
    args_value = state.get("relaunch_args")
    if isinstance(args_value, list):
        args = [str(item).strip() for item in args_value if str(item).strip()]
    else:
        args = []

    working_dir = str(
        state.get("relaunch_working_dir") or state.get("runtime_root") or ""
    ).strip()

    def _is_valid_executable(path_str: str) -> bool:
        if not path_str:
            return False
        try:
            p = Path(path_str).expanduser()
            return p.exists() and p.is_file()
        except Exception:
            return False

    def _is_valid_dir(path_str: str) -> bool:
        if not path_str:
            return False
        try:
            p = Path(path_str).expanduser()
            return p.exists() and p.is_dir()
        except Exception:
            return False

    # 1) إذا كانت القيم القادمة من runtime_state صالحة نستخدمها
    if _is_valid_executable(executable):
        if not _is_valid_dir(working_dir):
            working_dir = str(Path(executable).resolve().parent)
        return executable, args, working_dir

    # 2) fallback: إذا التطبيق يعمل كـ exe مجمّع
    if getattr(sys, "frozen", False):
        exe_path = str(Path(sys.executable).resolve())
        exe_dir = str(Path(sys.executable).resolve().parent)
        return exe_path, [], exe_dir

    # 3) fallback للتشغيل من السورس أثناء التطوير فقط
    root = Path(settings.BASE_DIR).resolve()
    desktop_app = (root / "launcher" / "desktop_app.py").resolve()
    python_exe = str(Path(sys.executable).resolve())

    if desktop_app.exists():
        return python_exe, [str(desktop_app)], str(root)

    # 4) fallback أخير آمن
    return python_exe, [], str(Path(python_exe).resolve().parent)


def _ps_array(items: list[str]) -> str:
    if not items:
        return '@()'
    joined = ', '.join(f"'{_ps_quote(item)}'" for item in items)
    return f'@({joined})'


def _stop_runtime_commands_ps() -> str:
    state = read_runtime_state()
    lines: list[str] = []
    launcher_pid = state.get("launcher_pid")
    server_pid = state.get("server_pid")
    if launcher_pid:
        lines.append(f"Stop-Process -Id {int(launcher_pid)} -Force -ErrorAction SilentlyContinue")
    if server_pid:
        lines.append(f"Stop-Process -Id {int(server_pid)} -Force -ErrorAction SilentlyContinue")
    lines.append("Get-Process -Name 'TrainingCenter' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue")
    return "\n".join(lines)


def _purge_legacy_batch_files() -> None:
    scripts_root = get_scripts_root()
    for child in scripts_root.glob("*.bat"):
        child.unlink(missing_ok=True)


def _append_launcher_trace(message: str) -> None:
    try:
        log_path = get_logs_root() / 'restart_launcher.log'
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with log_path.open('a', encoding='utf-8') as fh:
            fh.write(f'[{stamp}] {message}\n')
    except Exception:
        pass


def _downloads_dir() -> Path:
    user_profile = Path(os.environ.get('USERPROFILE') or Path.home())
    downloads = user_profile / 'Downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads


def _write_launcher_cmd(script_path: Path) -> Path:
    launcher_path = script_path.with_suffix('.cmd')
    powershell_path = Path(r"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe")
    if not powershell_path.exists():
        powershell_path = Path('powershell.exe')
    launcher_contents = (
        '@echo off\r\n'
        'setlocal\r\n'
        f'cd /d "{script_path.parent}"\r\n'
        f'"{powershell_path}" -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{script_path}"\r\n'
    )
    launcher_path.write_text(launcher_contents, encoding='utf-8')
    return launcher_path


def build_apply_script(payload_dir: Path, target_dir: Path, version: str, package_type: str = "full", deleted_files: list[str] | None = None) -> Path:
    scripts_root = get_scripts_root()
    logs_root = get_logs_root()
    _purge_legacy_batch_files()
    script_path = scripts_root / "apply_local_update.ps1"
    restart_log_path = logs_root / "restart_attempt.log"
    relaunch_executable, relaunch_args, relaunch_working_dir = _relaunch_details()
    relaunch_args_ps = _ps_array(relaunch_args)
    stop_commands = _stop_runtime_commands_ps()
    deleted_files = deleted_files or []
    delete_commands: list[str] = []
    for rel_path in deleted_files:
        safe_rel = str(rel_path).replace('"', "").replace("/", "\\")
        delete_commands.append(
            f"$deletePath = Join-Path $TargetDir '{_ps_quote(safe_rel)}'\n"
            "if (Test-Path $deletePath) { Remove-Item -Path $deletePath -Force -ErrorAction SilentlyContinue }"
        )
    delete_section = "\n".join(delete_commands)
    package_label = "جزئي" if package_type == "partial" else "كامل"

    contents = f'''$PayloadDir = '{_ps_quote(payload_dir)}'
$TargetDir = '{_ps_quote(target_dir)}'
$RestartLog = '{_ps_quote(restart_log_path)}'
$RelaunchExe = '{_ps_quote(relaunch_executable)}'
$RelaunchArgs = {relaunch_args_ps}
$RelaunchWorkingDir = '{_ps_quote(relaunch_working_dir)}'

try {{
    New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($RestartLog)) | Out-Null
}} catch {{}}

try {{
    Remove-Item -Path $RestartLog -Force -ErrorAction SilentlyContinue
}} catch {{}}

function Write-RestartLog([string]$Message) {{
    try {{
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        Add-Content -Path $RestartLog -Value "[$stamp] $Message" -Encoding UTF8
    }} catch {{}}
}}

Write-RestartLog "startup_entered version={version} package_type={package_type}"
Write-RestartLog "payload=$PayloadDir"
Write-RestartLog "target=$TargetDir"
Write-RestartLog "relaunch_exe=$RelaunchExe"
Write-RestartLog "relaunch_working_dir=$RelaunchWorkingDir"

$script:StatusForm = $null
$script:StatusLabel = $null
$script:StatusProgress = $null
$script:StatusTimerLabel = $null

function Initialize-StatusWindow([string]$InitialText) {{
    try {{
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $script:StatusForm = New-Object System.Windows.Forms.Form
        $script:StatusForm.Text = "تطبيق التحديث"
        $script:StatusForm.StartPosition = 'CenterScreen'
        $script:StatusForm.Size = New-Object System.Drawing.Size(620, 220)
        $script:StatusForm.FormBorderStyle = 'FixedDialog'
        $script:StatusForm.MaximizeBox = $false
        $script:StatusForm.MinimizeBox = $false
        $script:StatusForm.TopMost = $true
        $script:StatusForm.RightToLeft = 'Yes'
        $script:StatusForm.RightToLeftLayout = $true

        $panel = New-Object System.Windows.Forms.TableLayoutPanel
        $panel.Dock = 'Fill'
        $panel.RowCount = 3
        $panel.ColumnCount = 1
        $panel.Padding = New-Object System.Windows.Forms.Padding(18)
        $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 55)))
        $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 30)))
        $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 26)))

        $script:StatusLabel = New-Object System.Windows.Forms.Label
        $script:StatusLabel.Dock = 'Fill'
        $script:StatusLabel.TextAlign = 'MiddleCenter'
        $script:StatusLabel.RightToLeft = 'Yes'
        $script:StatusLabel.Font = New-Object System.Drawing.Font('Segoe UI', 12)
        $script:StatusLabel.Text = $InitialText

        $script:StatusProgress = New-Object System.Windows.Forms.ProgressBar
        $script:StatusProgress.Dock = 'Fill'
        $script:StatusProgress.Style = 'Continuous'
        $script:StatusProgress.Minimum = 0
        $script:StatusProgress.Maximum = 100
        $script:StatusProgress.Value = 8

        $script:StatusTimerLabel = New-Object System.Windows.Forms.Label
        $script:StatusTimerLabel.Dock = 'Fill'
        $script:StatusTimerLabel.TextAlign = 'MiddleCenter'
        $script:StatusTimerLabel.RightToLeft = 'Yes'
        $script:StatusTimerLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
        $script:StatusTimerLabel.ForeColor = [System.Drawing.Color]::FromArgb(90, 90, 90)
        $script:StatusTimerLabel.Text = 'الوقت المتبقي التقريبي: أقل من دقيقة'

        $panel.Controls.Add($script:StatusLabel, 0, 0)
        $panel.Controls.Add($script:StatusProgress, 0, 1)
        $panel.Controls.Add($script:StatusTimerLabel, 0, 2)
        $script:StatusForm.Controls.Add($panel)
        $null = $script:StatusForm.Show()
        [System.Windows.Forms.Application]::DoEvents()
    }} catch {{
        Write-RestartLog ("status_window_init_failed=" + $_.Exception.Message)
    }}
}}

function Set-StatusState([string]$Text, [int]$Progress = -1, [string]$EtaText = '') {{
    try {{
        if ($script:StatusLabel) {{
            $script:StatusLabel.Text = $Text
        }}
        if ($script:StatusProgress -and $Progress -ge 0) {{
            $safeValue = [Math]::Max($script:StatusProgress.Minimum, [Math]::Min($Progress, $script:StatusProgress.Maximum))
            $script:StatusProgress.Value = $safeValue
        }}
        if ($script:StatusTimerLabel) {{
            if ([string]::IsNullOrWhiteSpace($EtaText)) {{
                $script:StatusTimerLabel.Text = 'الوقت المتبقي التقريبي: أقل من دقيقة'
            }} else {{
                $script:StatusTimerLabel.Text = $EtaText
            }}
        }}
        [System.Windows.Forms.Application]::DoEvents()
    }} catch {{
        Write-RestartLog ("status_window_update_failed=" + $_.Exception.Message)
    }}
}}

function Close-StatusWindow() {{
    try {{
        if ($script:StatusForm) {{
            $script:StatusForm.Close()
            $script:StatusForm.Dispose()
        }}
    }} catch {{}}
}}

try {{
    chcp 65001 | Out-Null
}} catch {{
    Write-RestartLog ("console_codepage_failed=" + $_.Exception.Message)
}}

try {{
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Console]::OutputEncoding = $utf8NoBom
}} catch {{
    Write-RestartLog ("console_output_encoding_failed=" + $_.Exception.Message)
}}

try {{
    [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
}} catch {{
    Write-RestartLog ("console_input_encoding_failed=" + $_.Exception.Message)
}}

try {{
    $Host.UI.RawUI.WindowTitle = "تطبيق التحديث"
}} catch {{
    Write-RestartLog ("rawui_windowtitle_failed=" + $_.Exception.Message)
}}

Write-RestartLog ("relaunch_args_count=" + $RelaunchArgs.Count)

Initialize-StatusWindow "جارٍ تجهيز التحديث المحلي للإصدار {version}`nنوع الحزمة: {package_label}"
Set-StatusState "جارٍ تجهيز التحديث المحلي للإصدار {version}`nنوع الحزمة: {package_label}" 8 "الوقت المتبقي التقريبي: حوالي 40 ثانية"

Write-RestartLog "pre_stop_sleep"
Set-StatusState "جارٍ إغلاق البرنامج الحالي ثم بدء تطبيق التحديث..." 18 "الوقت المتبقي التقريبي: حوالي 35 ثانية"
Start-Sleep -Seconds 3

Write-RestartLog "stopping_runtime"
{stop_commands}

Start-Sleep -Seconds 2

if (-not (Test-Path $PayloadDir)) {{
    Write-RestartLog "payload_missing"
    try {{ Write-Host "تعذر العثور على ملفات التحديث." -ForegroundColor Red }} catch {{}}
    exit 1
}}

if (-not (Test-Path $TargetDir)) {{
    Write-RestartLog "target_missing"
    try {{ Write-Host "تعذر العثور على مجلد البرنامج." -ForegroundColor Red }} catch {{}}
    exit 1
}}

{delete_section}

Write-RestartLog "starting_copy"
Set-StatusState "جارٍ نسخ الملفات الجديدة..." 52 "الوقت المتبقي التقريبي: حوالي 20 ثانية"

$robocopyArgs = @($PayloadDir, $TargetDir, '/E', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/XD', 'media', 'local_updates', '/XF', 'db.sqlite3', '.env', '.env.example', 'desktop_server.log')
& robocopy @robocopyArgs | Out-Null
$rc = $LASTEXITCODE
Write-RestartLog "robocopy_exit=$rc"

if ($rc -ge 8) {{
    Write-RestartLog "copy_failed"
    Set-StatusState "فشل نسخ ملفات التحديث." 100 "توقفت العملية بسبب خطأ في النسخ"
    try {{
        Add-Type -AssemblyName System.Windows.Forms
        Close-StatusWindow
        [System.Windows.Forms.MessageBox]::Show(
            "فشل تطبيق التحديث.`nيرجى المحاولة مرة أخرى أو التواصل مع الدعم.",
            "فشل التحديث",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    }} catch {{}}
    exit 1
}}

Set-StatusState "تم نسخ التحديث بنجاح." 80 "الوقت المتبقي التقريبي: حوالي 10 ثوان"
Write-RestartLog "copy_done"

try {{
    $VersionFile = Join-Path $TargetDir 'app_version.txt'
    Set-Content -Path $VersionFile -Value '{version}' -Encoding UTF8
    $ReleaseManifestFile = Join-Path $TargetDir 'release_manifest.json'
    $ReleaseManifest = @{{ version = '{version}' }} | ConvertTo-Json
    Set-Content -Path $ReleaseManifestFile -Value $ReleaseManifest -Encoding UTF8
    Write-RestartLog "version_file_written"
    Write-RestartLog "release_manifest_written"
}} catch {{
    Write-RestartLog ("version_file_write_failed=" + $_.Exception.Message)
}}

try {{
    $EnvPath = Join-Path $TargetDir '.env'
    if (Test-Path $EnvPath) {{
        $envLines = Get-Content -Path $EnvPath -ErrorAction SilentlyContinue
        if ($null -eq $envLines) {{ $envLines = @() }}
        $updated = $false
        $newLines = foreach ($line in $envLines) {{
            if ($line -match '^APP_VERSION=') {{
                $updated = $true
                'APP_VERSION={version}'
            }} else {{
                $line
            }}
        }}
        if (-not $updated) {{
            $newLines += 'APP_VERSION={version}'
        }}
        Set-Content -Path $EnvPath -Value $newLines -Encoding UTF8
        Write-RestartLog "env_version_updated"
    }}
}} catch {{
    Write-RestartLog ("env_version_update_failed=" + $_.Exception.Message)
}}

Start-Sleep -Seconds 3

if (-not (Test-Path $RelaunchExe)) {{
    Write-RestartLog "relaunch_executable_missing"
    Set-StatusText "تم تطبيق التحديث، لكن تعذر العثور على ملف التشغيل التلقائي."
    try {{
        Add-Type -AssemblyName System.Windows.Forms
        Close-StatusWindow
        [System.Windows.Forms.MessageBox]::Show(
            "تم تطبيق التحديث بنجاح، ولكن لم يتم العثور على ملف التشغيل.`nيرجى تشغيل البرنامج يدويًا.",
            "تم التحديث",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
    }} catch {{}}
    exit 0
}}

try {{
    Write-RestartLog "trying_start_process"
    if ($RelaunchArgs -and $RelaunchArgs.Count -gt 0) {{
        $proc = Start-Process -FilePath $RelaunchExe -ArgumentList $RelaunchArgs -WorkingDirectory $RelaunchWorkingDir -PassThru -ErrorAction Stop
    }} else {{
        $proc = Start-Process -FilePath $RelaunchExe -WorkingDirectory $RelaunchWorkingDir -PassThru -ErrorAction Stop
    }}
    Start-Sleep -Milliseconds 800
    if ($proc -and -not $proc.HasExited) {{
        Write-RestartLog ("start_process_ok pid=" + $proc.Id)
        Set-StatusState "تم تطبيق التحديث بنجاح وسيتم تشغيل البرنامج الآن." 100 "اكتملت العملية"
        Add-Type -AssemblyName System.Windows.Forms
        Close-StatusWindow
        [System.Windows.Forms.MessageBox]::Show(
            "تم تطبيق التحديث بنجاح وسيتم تشغيل البرنامج الآن.",
            "تم التحديث بنجاح",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )
        exit 0
    }}
    Write-RestartLog "start_process_returned_but_process_exited"
}} catch {{
    Write-RestartLog ("start_process_failed=" + $_.Exception.Message)
}}

try {{
    Write-RestartLog "start_process_failed_final"
    Set-StatusState "تم تطبيق التحديث، لكن تعذر إعادة تشغيل البرنامج تلقائيًا." 100 "اكتملت العملية جزئيًا"
    try {{
        Add-Type -AssemblyName System.Windows.Forms
        Close-StatusWindow
        [System.Windows.Forms.MessageBox]::Show(
            "تم تطبيق التحديث بنجاح، ولكن تعذر إعادة تشغيل البرنامج تلقائيًا.`nيرجى تشغيله يدويًا.",
            "تم التحديث",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
    }} catch {{}}
}} catch {{}}

exit 0
'''
    script_path.write_text(contents, encoding='utf-8-sig')
    return script_path

def build_installer_script(package_path: Path, version: str) -> Path:
    scripts_root = get_scripts_root()
    logs_root = get_logs_root()
    _purge_legacy_batch_files()
    script_path = scripts_root / "run_downloaded_update.ps1"
    installer_log_path = logs_root / "installer_attempt.log"
    stop_commands = _stop_runtime_commands_ps()

    contents = f'''$PackagePath = '{_ps_quote(package_path)}'
$InstallerLog = '{_ps_quote(installer_log_path)}'

try {{
    New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($InstallerLog)) | Out-Null
}} catch {{}}

try {{
    Remove-Item -Path $InstallerLog -Force -ErrorAction SilentlyContinue
}} catch {{}}

function Write-InstallerLog([string]$Message) {{
    try {{
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        Add-Content -Path $InstallerLog -Value "[$stamp] $Message" -Encoding UTF8
    }} catch {{}}
}}

Write-InstallerLog "startup_entered version={version}"
Write-InstallerLog "package=$PackagePath"

$script:StatusForm = $null
$script:StatusLabel = $null
$script:StatusProgress = $null
$script:StatusTimerLabel = $null

function Initialize-InstallerStatus([string]$InitialText) {{
    try {{
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $script:StatusForm = New-Object System.Windows.Forms.Form
        $script:StatusForm.Text = "تطبيق التحديث"
        $script:StatusForm.StartPosition = 'CenterScreen'
        $script:StatusForm.Size = New-Object System.Drawing.Size(620, 220)
        $script:StatusForm.FormBorderStyle = 'FixedDialog'
        $script:StatusForm.MaximizeBox = $false
        $script:StatusForm.MinimizeBox = $false
        $script:StatusForm.TopMost = $true
        $script:StatusForm.RightToLeft = 'Yes'
        $script:StatusForm.RightToLeftLayout = $true
        $panel = New-Object System.Windows.Forms.TableLayoutPanel
        $panel.Dock = 'Fill'
        $panel.RowCount = 3
        $panel.ColumnCount = 1
        $panel.Padding = New-Object System.Windows.Forms.Padding(18)
        $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 55)))
        $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 30)))
        $panel.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 26)))

        $script:StatusLabel = New-Object System.Windows.Forms.Label
        $script:StatusLabel.Dock = 'Fill'
        $script:StatusLabel.TextAlign = 'MiddleCenter'
        $script:StatusLabel.RightToLeft = 'Yes'
        $script:StatusLabel.Font = New-Object System.Drawing.Font('Segoe UI', 12)
        $script:StatusLabel.Text = $InitialText

        $script:StatusProgress = New-Object System.Windows.Forms.ProgressBar
        $script:StatusProgress.Dock = 'Fill'
        $script:StatusProgress.Style = 'Continuous'
        $script:StatusProgress.Minimum = 0
        $script:StatusProgress.Maximum = 100
        $script:StatusProgress.Value = 8

        $script:StatusTimerLabel = New-Object System.Windows.Forms.Label
        $script:StatusTimerLabel.Dock = 'Fill'
        $script:StatusTimerLabel.TextAlign = 'MiddleCenter'
        $script:StatusTimerLabel.RightToLeft = 'Yes'
        $script:StatusTimerLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
        $script:StatusTimerLabel.ForeColor = [System.Drawing.Color]::FromArgb(90, 90, 90)
        $script:StatusTimerLabel.Text = 'الوقت المتبقي التقريبي: أقل من دقيقة'

        $panel.Controls.Add($script:StatusLabel, 0, 0)
        $panel.Controls.Add($script:StatusProgress, 0, 1)
        $panel.Controls.Add($script:StatusTimerLabel, 0, 2)
        $script:StatusForm.Controls.Add($panel)
        $null = $script:StatusForm.Show()
        [System.Windows.Forms.Application]::DoEvents()
    }} catch {{
        Write-InstallerLog ("status_window_init_failed=" + $_.Exception.Message)
    }}
}}

function Set-InstallerStatus([string]$Text) {{
    try {{
        if ($script:StatusLabel) {{
            $script:StatusLabel.Text = $Text
            [System.Windows.Forms.Application]::DoEvents()
        }}
    }} catch {{
        Write-InstallerLog ("status_window_update_failed=" + $_.Exception.Message)
    }}
}}

function Close-InstallerStatus() {{
    try {{
        if ($script:StatusForm) {{
            $script:StatusForm.Close()
            $script:StatusForm.Dispose()
        }}
    }} catch {{}}
}}

try {{
    chcp 65001 | Out-Null
}} catch {{
    Write-InstallerLog ("console_codepage_failed=" + $_.Exception.Message)
}}

try {{
    $OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
}} catch {{
    Write-InstallerLog ("console_output_encoding_failed=" + $_.Exception.Message)
}}

try {{
    [Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
}} catch {{
    Write-InstallerLog ("console_input_encoding_failed=" + $_.Exception.Message)
}}

try {{
    $Host.UI.RawUI.WindowTitle = "تطبيق التحديث"
}} catch {{
    Write-InstallerLog ("rawui_windowtitle_failed=" + $_.Exception.Message)
}}

Initialize-InstallerStatus "جارٍ تشغيل مُثبت التحديث للإصدار {version}"
Set-InstallerStatus "جارٍ إغلاق البرنامج الحالي ثم بدء التثبيت..."

Start-Sleep -Seconds 3
Write-InstallerLog "stopping_runtime"
{stop_commands}
Start-Sleep -Seconds 2

if (-not (Test-Path $PackagePath)) {{
    Write-InstallerLog "package_missing"
    Set-InstallerStatus "تعذر العثور على ملف المُثبت الذي تم تنزيله."
    exit 1
}}

Write-InstallerLog "starting_installer"
Set-InstallerStatus "جارٍ تشغيل ملف التحديث الخارجي..."

try {{
    $proc = Start-Process -FilePath $PackagePath -PassThru -ErrorAction Stop
    Write-InstallerLog ("installer_started pid=" + $proc.Id)
    Close-InstallerStatus
    exit 0
}} catch {{
    Write-InstallerLog ("installer_start_failed=" + $_.Exception.Message)
    Set-InstallerStatus "تعذر تشغيل ملف التحديث الخارجي."
    exit 1
}}
'''
    script_path.write_text(contents, encoding='utf-8-sig')
    return script_path

def ensure_pending_script(state: dict[str, Any] | None) -> Path:
    if not state:
        raise ValueError("لا يوجد تحديث مجهز حاليًا لتطبيقه.")

    script_path_value = str(state.get("script_path") or "").strip()
    if script_path_value:
        script_path = Path(script_path_value)
        if script_path.exists():
            return script_path
    install_kind = str(state.get("install_kind") or "").strip().lower()
    version = str(state.get("version") or "").strip()

    if install_kind == "installer":
        package_path_value = str(state.get("zip_path") or "").strip()
        if not package_path_value:
            raise FileNotFoundError("ملف تشغيل التحديث الخارجي غير موجود.")
        package_path = Path(package_path_value)
        if not package_path.exists():
            raise FileNotFoundError("ملف التحديث الخارجي غير موجود.")
        rebuilt = build_installer_script(package_path, version)
    else:
        payload_dir_value = str(state.get("payload_dir") or "").strip()
        if not payload_dir_value:
            raise FileNotFoundError("ملفات التحديث المجهز غير مكتملة.")
        payload_dir = Path(payload_dir_value)
        if not payload_dir.exists():
            raise FileNotFoundError("مجلد ملفات التحديث غير موجود.")
        package_type = str(state.get("package_type") or "full").strip().lower() or "full"
        deleted_files_count = state.get("deleted_files_count", 0)
        # لا تتوفر قائمة deleted_files في الحالة القديمة دائماً، لذا نستخدم قائمة فارغة عند إعادة البناء.
        rebuilt = build_apply_script(payload_dir, get_runtime_root(), version, package_type=package_type, deleted_files=[])

    state["script_path"] = str(rebuilt)
    save_pending_state(state)
    return rebuilt

def save_pending_state(state: dict[str, Any]) -> None:
    get_state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def load_pending_state() -> dict[str, Any] | None:
    path = get_state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def clear_pending_state() -> None:
    get_state_path().unlink(missing_ok=True)
    cleanup_old_pending()
    scripts_root = get_scripts_root()
    for child in scripts_root.iterdir():
        child.unlink(missing_ok=True)


def launch_pending_update() -> dict[str, Any]:
    state = load_pending_state()
    script_path = ensure_pending_script(state)
    _purge_legacy_batch_files()

    restart_log = get_logs_root() / 'restart_attempt.log'
    restart_log.unlink(missing_ok=True)

    system_root = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
    powershell_exe = system_root if system_root.exists() else Path("powershell.exe")
    powershell_cmd = [
        str(powershell_exe),
        "-NoLogo",
        "-NoProfile",
        "-WindowStyle",
        "Hidden",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    ]

    _append_launcher_trace(f"launch_requested script={script_path}")
    _append_launcher_trace(f"script_exists={script_path.exists()}")
    _append_launcher_trace(f"cwd={script_path.parent}")
    _append_launcher_trace(f"powershell_exe={powershell_exe}")
    _append_launcher_trace(f"command={subprocess.list2cmdline(powershell_cmd)}")

    try:
        proc = subprocess.Popen(
            powershell_cmd,
            cwd=str(script_path.parent),
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            ),
        )
        _append_launcher_trace(f"launcher_spawned pid={getattr(proc, 'pid', 'unknown')}")
    except Exception as exc:
        _append_launcher_trace(f"launcher_spawn_failed={exc}")
        raise

    time.sleep(1.5)
    if restart_log.exists() and restart_log.stat().st_size > 0:
        _append_launcher_trace("restart_attempt_log_detected=direct")
        return state

    launcher_cmd_path = _write_launcher_cmd(script_path)
    fallback_cmd = ["cmd.exe", "/c", str(launcher_cmd_path)]
    _append_launcher_trace(f"fallback_command={subprocess.list2cmdline(fallback_cmd)}")
    try:
        proc2 = subprocess.Popen(
            fallback_cmd,
            cwd=str(script_path.parent),
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            ),
        )
        _append_launcher_trace(f"fallback_launcher_spawned pid={getattr(proc2, 'pid', 'unknown')}")
    except Exception as exc:
        _append_launcher_trace(f"fallback_launcher_failed={exc}")
        raise

    return state

def _build_state(*, version: str, notes: str, package_path: Path, script_path: Path, current_version: str, source: str, install_kind: str, extracted_dir: Path | None = None, payload_dir: Path | None = None, sha256: str = "", download_url: str = "", package_type: str = "full", changed_files_count: int = 0, deleted_files_count: int = 0) -> dict[str, Any]:
    is_newer = parse_version(version) > parse_version(current_version)
    state = {
        "version": version,
        "notes": notes,
        "zip_path": str(package_path),
        "script_path": str(script_path),
        "prepared_at": datetime.now().isoformat(timespec='seconds'),
        "is_newer": is_newer,
        "current_version": current_version,
        "source": source,
        "install_kind": install_kind,
        "sha256": sha256,
        "download_url": download_url,
        "package_type": package_type,
        "changed_files_count": changed_files_count,
        "deleted_files_count": deleted_files_count,
    }
    if extracted_dir:
        state["extracted_dir"] = str(extracted_dir)
    if payload_dir:
        state["payload_dir"] = str(payload_dir)
    save_pending_state(state)
    return state


def prepare_local_update(uploaded_file, current_version: str) -> dict[str, Any]:
    zip_path = save_uploaded_zip(uploaded_file)
    extracted_dir = get_extracted_root() / zip_path.stem
    _safe_extract(zip_path, extracted_dir)
    manifest = load_manifest(extracted_dir)
    payload_dir = find_payload_dir(extracted_dir)
    target_dir = get_runtime_root()
    package_type = str(manifest.get("package_type") or "full").strip().lower()
    changed_files = manifest.get("files") or []
    deleted_files = manifest.get("deleted_files") or []
    script_path = build_apply_script(payload_dir, target_dir, str(manifest.get("version", "")), package_type=package_type, deleted_files=deleted_files)
    return _build_state(
        version=str(manifest.get("version", "")).strip(),
        notes=str(manifest.get("notes", "")).strip(),
        package_path=zip_path,
        extracted_dir=extracted_dir,
        payload_dir=payload_dir,
        script_path=script_path,
        current_version=current_version,
        source="local_upload",
        install_kind="zip",
        sha256=calculate_sha256(zip_path),
        package_type=package_type,
        changed_files_count=len(changed_files),
        deleted_files_count=len(deleted_files),
    )


def download_remote_update_and_prepare(*, download_url: str, current_version: str, expected_version: str = "", expected_sha256: str = "", package_name: str = "", notes: str = "", request_headers: dict[str, str] | None = None) -> dict[str, Any]:
    package_path = _download_remote_package(download_url, package_name=package_name, request_headers=request_headers)
    actual_sha256 = calculate_sha256(package_path)
    if expected_sha256 and actual_sha256.lower() != expected_sha256.strip().lower():
        raise ValueError("ملف التحديث الذي تم تنزيله لا يطابق البصمة المتوقعة.")

    suffix = package_path.suffix.lower()
    if suffix == '.zip':
        extracted_dir = get_extracted_root() / package_path.stem
        _safe_extract(package_path, extracted_dir)
        manifest = load_manifest(extracted_dir)
        payload_dir = find_payload_dir(extracted_dir)
        version = str(manifest.get('version', '')).strip()
        if expected_version and version and parse_version(version) < parse_version(expected_version):
            raise ValueError("نسخة الحزمة التي تم تنزيلها أقدم من الإصدار المتوقع.")
        package_type = str(manifest.get("package_type") or "full").strip().lower()
        changed_files = manifest.get("files") or []
        deleted_files = manifest.get("deleted_files") or []
        script_path = build_apply_script(payload_dir, get_runtime_root(), version, package_type=package_type, deleted_files=deleted_files)
        return _build_state(
            version=version or expected_version or current_version,
            notes=str(manifest.get('notes', '')).strip() or notes,
            package_path=package_path,
            extracted_dir=extracted_dir,
            payload_dir=payload_dir,
            script_path=script_path,
            current_version=current_version,
            source="remote_download",
            install_kind="zip",
            sha256=actual_sha256,
            download_url=download_url,
            package_type=package_type,
            changed_files_count=len(changed_files),
            deleted_files_count=len(deleted_files),
        )

    version = expected_version.strip() or current_version
    script_path = build_installer_script(package_path, version)
    return _build_state(
        version=version,
        notes=notes,
        package_path=package_path,
        script_path=script_path,
        current_version=current_version,
        source="remote_download",
        install_kind="installer",
        sha256=actual_sha256,
        download_url=download_url,
    )
