from __future__ import annotations

import json
import os
import shutil
import socket
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", r"C:\TrainingCenterData"))
OUTPUT_DIR = PROJECT_ROOT / "dist_client_light"
DEFAULT_PORT = 8000


def read_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        return data
    return data


def detect_lan_ip() -> str:
    """Best-effort LAN IPv4 detection for the SERVER machine."""
    forced = os.getenv("LAN_SERVER_PUBLIC_IP", "").strip()
    if forced:
        return forced

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def detect_server_url() -> str:
    """Detect the URL that client devices should open."""
    # 1) Prefer the URL written by launcher/lan_server.py while the LAN server is running.
    status_file = APP_DATA_DIR / "runtime_state" / "lan_status.json"
    if status_file.exists():
        try:
            status = json.loads(status_file.read_text(encoding="utf-8"))
            url = str(status.get("public_base_url") or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                return url.rstrip("/")
            ip = str(status.get("detected_lan_ip") or "").strip()
            port = int(status.get("port") or DEFAULT_PORT)
            if ip:
                return f"http://{ip}:{port}"
        except Exception:
            pass

    # 2) Then use C:\TrainingCenterData\.env if it has an explicit public URL.
    env = read_env_file(APP_DATA_DIR / ".env")
    url = env.get("LAN_SERVER_PUBLIC_BASE_URL", "").strip()
    if url:
        return url.rstrip("/")

    # 3) Otherwise detect the server machine IP and use the configured/default port.
    port_raw = env.get("LAN_SERVER_PORT", "") or read_env_file(PROJECT_ROOT / ".env.lan.example").get("LAN_SERVER_PORT", "")
    try:
        port = int(port_raw or DEFAULT_PORT)
    except ValueError:
        port = DEFAULT_PORT
    return f"http://{detect_lan_ip()}:{port}"


def find_asset(*relative_paths: str) -> Path | None:
    for rel in relative_paths:
        p = PROJECT_ROOT / rel
        if p.exists():
            return p
    return None


def write_client_launcher_py(path: Path) -> None:
    path.write_text(textwrap.dedent(r'''
        from __future__ import annotations

        import os
        import subprocess
        import sys
        import webbrowser
        from pathlib import Path
        import tkinter as tk
        from tkinter import messagebox


        APP_TITLE = "برنامج تسيير المتكونين"


        def resource_path(name: str) -> Path:
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            return base / name


        def read_server_url() -> str:
            candidates = [
                Path(__file__).resolve().parent / "server_url.txt",
                resource_path("server_url.txt"),
                Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "TrainingCenterClient" / "server_url.txt",
            ]
            for path in candidates:
                if path.exists():
                    value = path.read_text(encoding="utf-8").strip()
                    if value:
                        return value.rstrip("/")
            return "http://127.0.0.1:8000"


        def chrome_candidates() -> list[Path]:
            env_paths = [
                os.getenv("PROGRAMFILES", ""),
                os.getenv("PROGRAMFILES(X86)", ""),
                os.getenv("LOCALAPPDATA", ""),
            ]
            candidates: list[Path] = []
            for base in env_paths:
                if not base:
                    continue
                candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
            candidates.extend([
                Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            ])
            return candidates


        def open_url() -> None:
            url = read_server_url()
            # Try Google Chrome first.
            for chrome in chrome_candidates():
                if chrome.exists():
                    try:
                        subprocess.Popen([str(chrome), url], shell=False)
                        return
                    except Exception:
                        pass

            # Fallback: Windows default browser / any installed browser.
            try:
                os.startfile(url)  # type: ignore[attr-defined]
                return
            except Exception:
                pass

            try:
                webbrowser.open(url)
            except Exception as exc:
                messagebox.showerror(APP_TITLE, f"تعذر فتح المتصفح.\nالرابط: {url}\n\n{exc}")


        def main() -> None:
            root = tk.Tk()
            root.title(APP_TITLE)
            root.geometry("420x360")
            root.resizable(False, False)
            root.configure(bg="#f8fafc")

            icon_path = resource_path("mfep.ico")
            if icon_path.exists():
                try:
                    root.iconbitmap(str(icon_path))
                except Exception:
                    pass

            tk.Label(
                root,
                text=APP_TITLE,
                bg="#f8fafc",
                fg="#0f172a",
                font=("Times New Roman", 20, "bold"),
            ).pack(pady=(18, 8))

            image_path = resource_path("INSFP.jpg")
            if image_path.exists():
                try:
                    img = tk.PhotoImage(file=str(image_path))
                    # Keep a reference so Tkinter does not garbage-collect it.
                    root.logo_img = img  # type: ignore[attr-defined]
                    tk.Label(root, image=img, bg="#f8fafc").pack(pady=6)
                except Exception:
                    tk.Label(root, text="", bg="#f8fafc").pack(pady=35)
            else:
                tk.Label(root, text="", bg="#f8fafc").pack(pady=35)

            tk.Button(
                root,
                text="تشغيل البرنامج",
                command=open_url,
                bg="#15803d",
                fg="white",
                activebackground="#166534",
                activeforeground="white",
                font=("Times New Roman", 18, "bold"),
                width=18,
                height=2,
                relief="flat",
                cursor="hand2",
            ).pack(pady=22)

            tk.Label(
                root,
                text="يفتح Google Chrome أولًا، وإذا لم يجده يفتح المتصفح الافتراضي.",
                bg="#f8fafc",
                fg="#475569",
                font=("Times New Roman", 10),
            ).pack(pady=(0, 8))

            root.mainloop()


        if __name__ == "__main__":
            main()
    ''').strip() + "\n", encoding="utf-8")


def write_build_bat(path: Path) -> None:
    path.write_text(textwrap.dedent(r'''
        @echo off
        setlocal
        cd /d "%~dp0"

        if exist "..\.venv\Scripts\python.exe" (
          set "PYTHON_EXE=..\.venv\Scripts\python.exe"
        ) else (
          set "PYTHON_EXE=python"
        )

        "%PYTHON_EXE%" -m pip show pyinstaller >nul 2>nul
        if errorlevel 1 (
          echo PyInstaller غير مثبت. سيتم تثبيته الآن...
          "%PYTHON_EXE%" -m pip install pyinstaller
        )

        "%PYTHON_EXE%" -m PyInstaller ^
          --noconsole ^
          --onefile ^
          --name TrainingCenterClient ^
          --icon mfep.ico ^
          --add-data "server_url.txt;." ^
          --add-data "INSFP.jpg;." ^
          --add-data "mfep.ico;." ^
          TrainingCenterClient.py

        echo.
        echo تم إنشاء الملف هنا:
        echo %cd%\dist\TrainingCenterClient.exe
        echo.
        pause
    ''').strip() + "\n", encoding="utf-8")


def write_inno_script(path: Path) -> None:
    path.write_text(textwrap.dedent(r'''
        ; Inno Setup script for Training Center light client
        ; Build steps:
        ; 1) Run build_exe.bat first to create dist\TrainingCenterClient.exe
        ; 2) Open this .iss file with Inno Setup and Compile

        [Setup]
        AppId={{8D6684D5-5B5B-4F37-A933-TrainingCenterClient}}
        AppName=Training Center Client
        AppVersion=1.0.0
        AppPublisher=Training Center
        DefaultDirName={localappdata}\Training Center Client
        DefaultGroupName=Training Center Client
        OutputDir=installer
        OutputBaseFilename=TrainingCenter_Client_Setup
        Compression=lzma
        SolidCompression=yes
        WizardStyle=modern
        PrivilegesRequired=lowest
        SetupIconFile=mfep.ico

        [Languages]
        Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
        Name: "english"; MessagesFile: "compiler:Default.isl"

        [Files]
        Source: "dist\TrainingCenterClient.exe"; DestDir: "{app}"; Flags: ignoreversion
        Source: "server_url.txt"; DestDir: "{app}"; Flags: ignoreversion
        Source: "mfep.ico"; DestDir: "{app}"; Flags: ignoreversion

        [Icons]
        Name: "{userdesktop}\برنامج تسيير المتكونين"; Filename: "{app}\TrainingCenterClient.exe"; IconFilename: "{app}\mfep.ico"
        Name: "{group}\برنامج تسيير المتكونين"; Filename: "{app}\TrainingCenterClient.exe"; IconFilename: "{app}\mfep.ico"

        [Run]
        Filename: "{app}\TrainingCenterClient.exe"; Description: "تشغيل برنامج تسيير المتكونين"; Flags: nowait postinstall skipifsilent
    ''').strip() + "\n", encoding="utf-8")


def main() -> None:
    server_url = detect_server_url()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUTPUT_DIR / "server_url.txt").write_text(server_url + "\n", encoding="utf-8")
    write_client_launcher_py(OUTPUT_DIR / "TrainingCenterClient.py")
    write_build_bat(OUTPUT_DIR / "build_exe.bat")
    write_inno_script(OUTPUT_DIR / "TrainingCenter_Client_Setup.iss")

    image = find_asset("trainees/static/branding/INSFP.jpg", "INSFP.jpg")
    if image:
        shutil.copy2(image, OUTPUT_DIR / "INSFP.jpg")
    else:
        # Tkinter PhotoImage needs an existing file only if display is wanted; create tiny fallback text note.
        (OUTPUT_DIR / "INSFP.jpg").write_bytes(b"")

    icon = find_asset("trainees/static/branding/mfep.ico", "mfep.ico")
    if icon:
        shutil.copy2(icon, OUTPUT_DIR / "mfep.ico")

    readme = f"""
تم إنشاء حزمة العميل الخفيف بنجاح.

الرابط الذي سيفتحه العميل:
{server_url}

الملفات المهمة:
- TrainingCenterClient.py : كود الواجهة الصغيرة
- server_url.txt : رابط السيرفر للأجهزة الأخرى
- build_exe.bat : يحول العميل إلى EXE بواسطة PyInstaller
- TrainingCenter_Client_Setup.iss : سكربت Inno Setup لإنشاء ملف تثبيت

الخطوات على جهاز التطوير:
1) شغّل build_exe.bat داخل هذا المجلد.
2) افتح TrainingCenter_Client_Setup.iss ببرنامج Inno Setup واضغط Compile.
3) ستجد المثبت داخل مجلد installer باسم TrainingCenter_Client_Setup.exe.
4) التثبيت الآن لكل مستخدم داخل LocalAppData، ويضع الاختصار على سطح مكتب المستخدم الحالي بدل Public Desktop.
""".strip()
    (OUTPUT_DIR / "README_CLIENT_AR.txt").write_text(readme + "\n", encoding="utf-8")

    print("تم إنشاء ملفات العميل الخفيف داخل:")
    print(OUTPUT_DIR)
    print("رابط السيرفر:", server_url)
    print("الخطوة التالية: افتح dist_client_light ثم شغل build_exe.bat وبعدها Compile لملف Inno Setup.")


if __name__ == "__main__":
    main()
