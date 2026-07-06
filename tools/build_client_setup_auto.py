from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLIENT_DIR = PROJECT_ROOT / "dist_client_light"
FINAL_DIR = PROJECT_ROOT / "dist_client_setup"
SETUP_NAME = "TrainingCenter_Client_Setup.exe"


def print_step(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(">", " ".join(f'"{c}"' if " " in c else c for c in cmd))
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
        Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 5\ISCC.exe"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def pyinstaller_add_data_arg(path: Path) -> str:
    # Windows PyInstaller separator is semicolon.
    return f"{path.name};."


def build_client_package(py: str) -> None:
    builder = PROJECT_ROOT / "tools" / "build_light_client.py"
    if not builder.exists():
        raise FileNotFoundError(f"لم أجد الملف: {builder}")
    run([py, str(builder)], cwd=PROJECT_ROOT)


def build_client_exe(py: str) -> Path:
    launcher_py = CLIENT_DIR / "TrainingCenterClient.py"
    if not launcher_py.exists():
        raise FileNotFoundError(f"لم أجد الملف: {launcher_py}")

    # تنظيف بناء سابق حتى لا تختلط النتائج القديمة بالجديدة.
    for name in ("build", "dist"):
        target = CLIENT_DIR / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    spec_file = CLIENT_DIR / "TrainingCenterClient.spec"
    if spec_file.exists():
        spec_file.unlink()

    cmd = [
        py,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onefile",
        "--clean",
        "--name",
        "TrainingCenterClient",
    ]

    icon = CLIENT_DIR / "mfep.ico"
    if icon.exists() and icon.stat().st_size > 0:
        cmd += ["--icon", str(icon)]

    for asset_name in ("server_url.txt", "INSFP.jpg", "mfep.ico"):
        asset = CLIENT_DIR / asset_name
        if asset.exists() and asset.stat().st_size > 0:
            cmd += ["--add-data", pyinstaller_add_data_arg(asset)]

    cmd.append(str(launcher_py))
    run(cmd, cwd=CLIENT_DIR)

    exe = CLIENT_DIR / "dist" / "TrainingCenterClient.exe"
    if not exe.exists():
        raise FileNotFoundError("فشل إنشاء TrainingCenterClient.exe")
    return exe


def build_inno_setup() -> Path:
    iscc = find_iscc()
    if not iscc:
        raise FileNotFoundError(
            "لم أجد Inno Setup Compiler / ISCC.exe.\n"
            "ثبّت Inno Setup أو أضف مساره إلى PATH، ثم أعد تشغيل build_client_setup_auto.bat."
        )

    iss = CLIENT_DIR / "TrainingCenter_Client_Setup.iss"
    if not iss.exists():
        raise FileNotFoundError(f"لم أجد ملف Inno Setup: {iss}")

    installer_dir = CLIENT_DIR / "installer"
    if installer_dir.exists():
        shutil.rmtree(installer_dir, ignore_errors=True)

    run([str(iscc), str(iss)], cwd=CLIENT_DIR)

    installer = installer_dir / SETUP_NAME
    if not installer.exists():
        # fallback: search any generated setup with the expected name
        matches = list(CLIENT_DIR.rglob(SETUP_NAME))
        if matches:
            installer = matches[0]
        else:
            raise FileNotFoundError("تم تشغيل Inno Setup لكن لم أجد ملف المثبت الناتج.")
    return installer


def copy_final_outputs(exe: Path, installer: Path | None) -> None:
    if FINAL_DIR.exists():
        shutil.rmtree(FINAL_DIR, ignore_errors=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, FINAL_DIR / exe.name)
    shutil.copy2(CLIENT_DIR / "server_url.txt", FINAL_DIR / "server_url.txt")
    if installer and installer.exists():
        shutil.copy2(installer, FINAL_DIR / SETUP_NAME)


def main() -> int:
    py = project_python()
    print("Python المستخدم:", py)

    print_step("1) إنشاء ملفات العميل الخفيف من المشروع واكتشاف رابط السيرفر")
    build_client_package(py)

    server_url_file = CLIENT_DIR / "server_url.txt"
    if server_url_file.exists():
        print("رابط السيرفر داخل العميل:", server_url_file.read_text(encoding="utf-8").strip())

    print_step("2) تجهيز PyInstaller")
    ensure_pyinstaller(py)

    print_step("3) تحويل العميل الخفيف إلى EXE")
    exe = build_client_exe(py)
    print("تم إنشاء EXE:", exe)

    installer = None
    print_step("4) إنشاء ملف التثبيت بواسطة Inno Setup")
    try:
        installer = build_inno_setup()
        print("تم إنشاء المثبت:", installer)
    except FileNotFoundError as exc:
        print("تنبيه:", exc)
        print("تم إنشاء EXE فقط، ولم يتم إنشاء Setup لأن Inno Setup غير متوفر.")

    print_step("5) نسخ النتائج النهائية إلى dist_client_setup")
    copy_final_outputs(exe, installer)

    print("\nالنتائج النهائية:")
    print("-", FINAL_DIR / "TrainingCenterClient.exe")
    print("-", FINAL_DIR / "server_url.txt")
    if installer:
        print("-", FINAL_DIR / SETUP_NAME)
    else:
        print("- لم يتم إنشاء TrainingCenter_Client_Setup.exe لأن Inno Setup غير متوفر.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print("\nفشل تنفيذ أمر خارجي:", exc)
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print("\nخطأ:", exc)
        raise SystemExit(1)
