from __future__ import annotations

import os
import socket
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_ROOT = PROJECT_ROOT / "dist_office_server"
SETUP_NAME = "TrainingCenter_Office_Server_Setup.exe"
POSTGRES_DIR = PROJECT_ROOT / "third_party" / "postgresql"
POSTGRES_INSTALLER_EXE_ENV = os.getenv("POSTGRES_INSTALLER_EXE", "").strip().strip('"')
POSTGRES_DEFAULT_PASSWORD = os.getenv("POSTGRES_DEFAULT_PASSWORD", "123456")
POSTGRES_DEFAULT_PORT = os.getenv("POSTGRES_DEFAULT_PORT", "5432")
POSTGRES_FALLBACK_PORT = os.getenv("POSTGRES_FALLBACK_PORT", "5433")
SUPPORTED_POSTGRES_MAJORS = (18, 17, 16, 15)


def print_step(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72)


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(">", " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def project_python() -> str:
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable or "python"


def ensure_pyinstaller(py: str) -> None:
    try:
        subprocess.check_call([py, "-m", "PyInstaller", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    except Exception:
        pass
    print("PyInstaller غير مثبت. سيتم تثبيته الآن...")
    run([py, "-m", "pip", "install", "pyinstaller"])


def find_iscc() -> Path | None:
    env_value = os.getenv("ISCC_EXE", "").strip().strip('"')
    if env_value and Path(env_value).exists():
        return Path(env_value)
    for name in ("ISCC.exe", "ISCC"):
        found = shutil.which(name)
        if found:
            return Path(found)
    candidates = [
        Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    return next((p for p in candidates if p.exists()), None)


def add_data_arg(src: Path, dest: str) -> str:
    return f"{src};{dest}"


def clean_old() -> None:
    for target in (BUILD_ROOT, PROJECT_ROOT / "build", PROJECT_ROOT / "dist"):
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    spec = PROJECT_ROOT / "TrainingCenterOfficeServer.spec"
    if spec.exists():
        spec.unlink()


def common_pyinstaller_args(console: bool) -> list[str]:
    name = "TrainingCenterOfficeServer_console" if console else "TrainingCenterOfficeServer"
    cmd = [
        project_python(),
        "-m", "PyInstaller",
        "--clean",
        "--onefile",
        "--name", name,
        "--paths", str(PROJECT_ROOT),
        "--collect-submodules", "training_center",
        "--collect-submodules", "trainees",
        "--collect-submodules", "core",
        "--collect-submodules", "sync_core",
        "--collect-submodules", "django",
        "--hidden-import", "waitress",
        "--hidden-import", "psycopg2",
        "--hidden-import", "psycopg2_binary",
    ]
    if not console:
        cmd.append("--noconsole")

    icon = PROJECT_ROOT / "mfep.ico"
    if icon.exists() and icon.stat().st_size > 0:
        cmd += ["--icon", str(icon)]

    for folder in ("templates", "static", "core", "trainees", "sync_core", "training_center"):
        src = PROJECT_ROOT / folder
        if src.exists():
            cmd += ["--add-data", add_data_arg(src, folder)]
    for file_name in (".env.lan.example", ".env.example", "INSFP.jpg", "mfep.ico"):
        src = PROJECT_ROOT / file_name
        if src.exists():
            cmd += ["--add-data", add_data_arg(src, ".")]
    cmd.append(str(PROJECT_ROOT / "launcher" / "lan_server.py"))
    return cmd


def build_exe(console: bool) -> Path:
    run(common_pyinstaller_args(console), cwd=PROJECT_ROOT)
    exe_name = "TrainingCenterOfficeServer_console.exe" if console else "TrainingCenterOfficeServer.exe"
    exe = PROJECT_ROOT / "dist" / exe_name
    if not exe.exists():
        raise FileNotFoundError(f"فشل إنشاء {exe_name}")
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    final = BUILD_ROOT / exe_name
    shutil.copy2(exe, final)
    return final


def postgres_installer_major(path: Path) -> int:
    """Extract PostgreSQL major version from filenames like postgresql-17.5-1-windows-x64.exe."""
    match = re.search(r"postgresql-(\d+)(?:[.\-]|$)", path.name, flags=re.IGNORECASE)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


def find_postgres_installer() -> Path | None:
    """Find the bundled PostgreSQL installer. Env override wins; otherwise use the newest supported major."""
    if POSTGRES_INSTALLER_EXE_ENV:
        candidate = POSTGRES_DIR / POSTGRES_INSTALLER_EXE_ENV
        return candidate if candidate.exists() and candidate.is_file() else None

    candidates: list[Path] = []
    if POSTGRES_DIR.exists():
        patterns = [
            "postgresql-*-windows-x64.exe",
            "postgresql-*-windows-x64*.exe",
            "postgresql-*-x64.exe",
        ]
        seen: set[Path] = set()
        for pattern in patterns:
            for item in POSTGRES_DIR.glob(pattern):
                if item.is_file() and item not in seen:
                    seen.add(item)
                    major = postgres_installer_major(item)
                    if major in SUPPORTED_POSTGRES_MAJORS:
                        candidates.append(item)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: (postgres_installer_major(p), p.name.lower()), reverse=True)[0]


def postgres_installer_available() -> bool:
    return find_postgres_installer() is not None


def ensure_central_url_file() -> Path:
    """اكتب رابط الخادم المركزي في المثبت باستعمال اسم جهاز المطوّر بدل IP المتغيّر."""
    path = PROJECT_ROOT / "CENTRAL_URL_FOR_INSTALLER.txt"
    value = os.getenv("CENTRAL_URL_FOR_INSTALLER", "").strip()
    if not value:
        host = os.getenv("CENTRAL_HOSTNAME_FOR_INSTALLER", "").strip() or socket.gethostname().strip() or "localhost"
        value = f"http://{host}:9000"
    path.write_text(value.rstrip("/") + "\n", encoding="utf-8")
    return path

def inno_files_lines_for_postgres() -> str:
    installer = find_postgres_installer()
    lines = [
        f'Source: "{PROJECT_ROOT / "tools" / "install_postgresql_if_needed.ps1"}"; DestDir: "{{app}}\\tools"; Flags: ignoreversion',
        f'Source: "{PROJECT_ROOT / "tools" / "install_postgresql_if_needed.cmd"}"; DestDir: "{{app}}\\tools"; Flags: ignoreversion',
    ]
    if installer:
        lines.append(
            f'Source: "{installer}"; DestDir: "{{app}}\\third_party\\postgresql"; Flags: ignoreversion'
        )
    return "\n".join(lines)


def inno_run_lines_for_postgres() -> str:
    installer = find_postgres_installer()
    if not installer:
        return (
            "; PostgreSQL installer not bundled. ضع أي مثبت رسمي مدعوم هنا قبل البناء:\n"
            f"; {POSTGRES_DIR}\\postgresql-15/16/17/18-...-windows-x64.exe\n"
        )
    return (
        'Filename: "{app}\\tools\\install_postgresql_if_needed.cmd"; '
        f'Parameters: """{{app}}\\third_party\\postgresql\\{installer.name}"""; '
        'StatusMsg: "فحص PostgreSQL والاتصال بقاعدة البيانات..."; Flags: runhidden waituntilterminated\n'
    )

def write_inno_script() -> Path:
    iss = BUILD_ROOT / "TrainingCenter_Office_Server_Setup.iss"
    icon_line = f'SetupIconFile={PROJECT_ROOT / "mfep.ico"}' if (PROJECT_ROOT / "mfep.ico").exists() else ""
    iss.write_text(f'''; Auto-generated by tools/build_office_server_setup.py
#define MyAppName "Training Center Independent Device"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Training Center"
#define MyAppExeName "TrainingCenterOfficeServer.exe"

[Setup]
AppId={{{{7E6C5D9B-33E2-45C2-A9AC-72B65B4C7E10}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{autopf}}\\TrainingCenterOfficeServer
DefaultGroupName=Training Center
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=TrainingCenter_Office_Server_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
PrivilegesRequired=admin
{icon_line}

[Files]
Source: "{BUILD_ROOT / 'TrainingCenterOfficeServer.exe'}"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "{PROJECT_ROOT / '.env.lan.example'}"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "{PROJECT_ROOT / 'CONFIGURE_DEVICE_SYNC.ps1'}"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "{PROJECT_ROOT / 'CONFIGURE_DEVICE_SYNC.cmd'}"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "{ensure_central_url_file()}"; DestDir: "{{app}}"; Flags: ignoreversion
{inno_files_lines_for_postgres()}

[Dirs]
Name: "{{commonappdata}}\\TrainingCenterOfficeServer"
Name: "{{commonappdata}}\\TrainingCenterOfficeServer\\logs"

[Icons]
Name: "{{group}}\\تشغيل خادم المكتب"; Filename: "{{app}}\\TrainingCenterOfficeServer.exe"
Name: "{{group}}\\تجهيز قاعدة البيانات"; Filename: "{{app}}\\TrainingCenterOfficeServer.exe"; Parameters: "setup-device"
Name: "{{commondesktop}}\\Training Center Office Server"; Filename: "{{app}}\\TrainingCenterOfficeServer.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب"; GroupDescription: "اختصارات إضافية:"; Flags: unchecked

[Code]
function PostgresReady(): Boolean;
begin
  Result := FileExists(ExpandConstant('{{commonappdata}}\TrainingCenterOfficeServer\postgres_ready.ok'));
end;

function PostgresServiceExists(): Boolean;
begin
  Result :=
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\postgresql-x64-18') or
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\postgresql-x64-17') or
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\postgresql-x64-16') or
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\postgresql-x64-15') or
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\postgresql-x64-18-trainingcenter') or
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\postgresql-x64-17-trainingcenter') or
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\postgresql-x64-16-trainingcenter') or
    RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\postgresql-x64-15-trainingcenter');
end;

function NeedPostgresSetup(): Boolean;
begin
  Result := not PostgresReady() and not PostgresServiceExists();
end;

function CanRunDeviceSetup(): Boolean;
begin
  // setup-device must run only after the helper verified connection and wrote postgres_ready.ok
  Result := PostgresReady();
end;

procedure StopTrainingCenterServer();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{{cmd}}'), '/C taskkill /F /IM TrainingCenterOfficeServer.exe /T >nul 2>nul', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function InitializeSetup(): Boolean;
begin
  StopTrainingCenterServer();
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  StopTrainingCenterServer();
  Result := True;
end;

var
  LaunchAfterFinishDone: Boolean;

procedure LaunchTrainingCenterAfterFinish();
var
  ResultCode: Integer;
begin
  if LaunchAfterFinishDone then
    Exit;

  if CanRunDeviceSetup() and FileExists(ExpandConstant('{{app}}\TrainingCenterOfficeServer.exe')) then
  begin
    LaunchAfterFinishDone := True;
    Exec(ExpandConstant('{{app}}\TrainingCenterOfficeServer.exe'), '', ExpandConstant('{{app}}'), SW_HIDE, ewNoWait, ResultCode);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpFinished then
    LaunchTrainingCenterAfterFinish();
end;

[Run]
; Stop any running copy before post-install setup
Filename: "{{cmd}}"; Parameters: "/C taskkill /F /IM TrainingCenterOfficeServer.exe /T >nul 2>nul"; Flags: runhidden waituntilterminated
{inno_run_lines_for_postgres()}Filename: "{{app}}\TrainingCenterOfficeServer.exe"; Parameters: "setup-device"; StatusMsg: "تجهيز قاعدة البيانات وتشغيل migrations..."; Flags: runhidden waituntilterminated; Check: CanRunDeviceSetup

[UninstallRun]
Filename: "{{cmd}}"; Parameters: "/C taskkill /F /IM TrainingCenterOfficeServer.exe /T >nul 2>nul"; Flags: runhidden waituntilterminated; RunOnceId: "StopTrainingCenterOfficeServer"
''', encoding="utf-8")
    return iss


def build_inno() -> Path | None:
    iscc = find_iscc()
    if not iscc:
        print("تنبيه: لم أجد Inno Setup، سيتم الاكتفاء بملفات EXE داخل dist_office_server.")
        return None
    iss = write_inno_script()
    installer_dir = BUILD_ROOT / "installer"
    if installer_dir.exists():
        shutil.rmtree(installer_dir, ignore_errors=True)
    run([str(iscc), str(iss)], cwd=BUILD_ROOT)
    setup = installer_dir / SETUP_NAME
    return setup if setup.exists() else None


def main() -> int:
    py = project_python()
    print("Python المستخدم:", py)
    print_step("1) تجهيز PyInstaller")
    ensure_pyinstaller(py)
    print_step("2) فحص ملف PostgreSQL المدمج")
    pg_installer = find_postgres_installer()
    if pg_installer:
        print("سيتم تضمين مثبت PostgreSQL:", pg_installer)
        print("الإصدار الرئيسي المكتشف:", postgres_installer_major(pg_installer))
    else:
        print("تنبيه: لم أجد مثبت PostgreSQL 15/16/17/18 ولن يتم تضمينه داخل Setup.")
        print("ضع أي مثبت رسمي مدعوم داخل:", POSTGRES_DIR)
        print("مثال: postgresql-17.5-1-windows-x64.exe")
    print_step("3) تنظيف البناء القديم")
    clean_old()
    print_step("4) إنشاء نسخة خادم المكتب بواجهة مخفية")
    build_exe(console=False)
    if os.getenv("BUILD_DIAGNOSTIC_CONSOLE", "0").strip() == "1":
        print_step("5) إنشاء نسخة تشخيص Console للمطور فقط")
        build_exe(console=True)
    else:
        print_step("5) تخطي نسخة Console للتوزيع الرسمي")

    print_step("6) إنشاء مثبت Inno Setup عند توفره")
    setup = build_inno()
    print("\nالنتائج:")
    print("-", BUILD_ROOT / "TrainingCenterOfficeServer.exe")
    if setup:
        print("-", setup)
    else:
        print("- لم يتم إنشاء Setup لأن Inno Setup غير متوفر.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print("\nفشل أمر خارجي:", exc)
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print("\nخطأ:", exc)
        raise SystemExit(1)
