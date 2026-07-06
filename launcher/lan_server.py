from __future__ import annotations

import json
import os
import signal
import socket
import secrets
import subprocess
import urllib.error
import urllib.request
import sys
import threading
import time
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2, which
from typing import Any



BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)

APP_NAME = "TrainingCenter"
SOURCE_ROOT = Path(__file__).resolve().parent.parent
CENTRAL_APP_DATA_DIR = Path(r"C:\TrainingCenterData")
LEGACY_RUNTIME_DIR = SOURCE_ROOT / "runtime_lan"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return SOURCE_ROOT


def bundled_root() -> Path:
    # عند العمل كـ EXE، ملفات Django والقوالب والملفات الثابتة تكون داخل مجلد PyInstaller المؤقت.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return SOURCE_ROOT


ROOT_DIR = project_root()
BUNDLED_ROOT = bundled_root()
if str(BUNDLED_ROOT) not in sys.path:
    sys.path.insert(0, str(BUNDLED_ROOT))


def load_dotenv_file(env_path: Path) -> bool:
    if not env_path.exists():
        return False
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")
    return True


def resolve_app_data_dir() -> Path:
    explicit = os.getenv("APP_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit).resolve()
    return CENTRAL_APP_DATA_DIR.resolve()


def preferred_env_candidates(app_data_dir: Path) -> list[Path]:
    env_file_path = os.getenv("ENV_FILE_PATH", "").strip()
    candidates: list[Path] = []
    if env_file_path:
        candidates.append(Path(env_file_path))
    candidates.extend([
        app_data_dir / ".env",
        app_data_dir / ".env.lan",
        CENTRAL_APP_DATA_DIR / ".env",
        CENTRAL_APP_DATA_DIR / ".env.lan",
        ROOT_DIR / ".env",
        ROOT_DIR / ".env.lan",
        LEGACY_RUNTIME_DIR / ".env",
        LEGACY_RUNTIME_DIR / ".env.lan",
    ])
    # preserve order while removing duplicates
    unique = []
    seen = set()
    for c in candidates:
        key = str(c).lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


APP_DATA_DIR = resolve_app_data_dir()
RUNTIME_DIR = APP_DATA_DIR / "runtime_state"
LOGS_DIR = APP_DATA_DIR / "logs"
STATUS_FILE = RUNTIME_DIR / "lan_status.json"
PID_FILE = RUNTIME_DIR / "lan_server.pid"
ENV_FILE = APP_DATA_DIR / ".env"
LEGACY_ENV_FILE = APP_DATA_DIR / ".env.lan"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_runtime_dirs() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("logs", "backups", "tmp_imports", "local_updates", "media", "staticfiles", "runtime_state"):
        (APP_DATA_DIR / name).mkdir(parents=True, exist_ok=True)


def append_startup_log(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with (LOGS_DIR / "lan_startup.log").open("a", encoding="utf-8") as fh:
        fh.write(f"[{utc_now()}] {message}\n")


def write_status(**payload: Any) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    current: dict[str, Any] = {}
    if STATUS_FILE.exists():
        try:
            current = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    current.update(payload)
    current["updated_at"] = utc_now()
    STATUS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_legacy_env_if_needed(app_data_dir: Path) -> None:
    legacy_env = LEGACY_RUNTIME_DIR / ".env"
    central_env = app_data_dir / ".env"
    if not central_env.exists() and legacy_env.exists():
        app_data_dir.mkdir(parents=True, exist_ok=True)
        copy2(legacy_env, central_env)


def ensure_env_file(app_data_dir: Path) -> Path:
    migrate_legacy_env_if_needed(app_data_dir)

    for candidate in preferred_env_candidates(app_data_dir):
        if candidate.exists():
            return candidate

    example_candidates = [
        ROOT_DIR / ".env.lan.example",
        ROOT_DIR / ".env.example",
        SOURCE_ROOT / ".env.lan.example",
        SOURCE_ROOT / ".env.example",
    ]
    central_env = app_data_dir / ".env"

    for example_path in example_candidates:
        if example_path.exists():
            content = example_path.read_text(encoding="utf-8")
            content = content.replace("APP_DATA_DIR=C:/TrainingCenterData", f"APP_DATA_DIR={app_data_dir.as_posix()}")
            content = content.replace("APP_DATA_DIR=C:\\TrainingCenterData", f"APP_DATA_DIR={app_data_dir.as_posix()}")
            central_env.write_text(content.rstrip() + "\n", encoding="utf-8")
            return central_env

    lines = [
        "DJANGO_ENV=lan",
        "DJANGO_DEBUG=0",
        "DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost",
        "DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000",
        "DJANGO_SECRET_KEY=change-me-for-lan-server",
        "DB_ENGINE=postgres",
        "POSTGRES_HOST=127.0.0.1",
        "POSTGRES_PORT=5432",
        "POSTGRES_DB=training_center",
        "POSTGRES_USER=postgres",
        "POSTGRES_PASSWORD=",
        f"APP_DATA_DIR={app_data_dir.as_posix()}",
        "LAN_SERVER_HOST=0.0.0.0",
        "LAN_SERVER_PORT=8000",
        "LAN_SERVER_PUBLIC_BASE_URL=",
        "WAITRESS_THREADS=8",
        "WAITRESS_CONNECTION_LIMIT=100",
        "WAITRESS_CHANNEL_TIMEOUT=120",
        "RUN_STARTUP_TASKS=1",
        "DJANGO_LOG_LEVEL=INFO",
        "DEV_LOGIN_ENABLED=0",
    ]
    central_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return central_env



def _read_env_pairs(env_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not env_path.exists():
        return data
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def _write_env_value(env_path: Path, updates: dict[str, str]) -> None:
    """Update/create .env keys while preserving existing comments as much as possible."""
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    new_lines: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and "=" in raw:
            key = raw.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                new_lines.append(raw)
        else:
            new_lines.append(raw)
    missing = [k for k in updates if k not in seen]
    if missing and new_lines and new_lines[-1].strip():
        new_lines.append("")
    for key in missing:
        new_lines.append(f"{key}={updates[key]}")
    env_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def _safe_slug(value: str) -> str:
    allowed = []
    for ch in value.lower():
        if ch.isalnum():
            allowed.append(ch)
        elif ch in {"-", "_", "."}:
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    return slug or "device"


def _normalize_env_path(value: str | os.PathLike | None) -> str:
    if not value:
        return ""
    try:
        return Path(str(value).strip().strip('"')).as_posix()
    except Exception:
        return str(value).strip().strip('"').replace("\\", "/")


def ensure_browser_env_defaults(env_path: Path, app_data_dir: Path, pairs: dict[str, str] | None = None) -> dict[str, str]:
    """Prepare automatic browser opening keys inside every office .env.

    إذا أنشئ مكتب جديد أو شغلنا مكتبًا قديمًا لا يملك مفاتيح Chrome،
    نضيفها تلقائيًا ونحاول اكتشاف chrome.exe من الجهاز نفسه.
    """
    pairs = pairs or _read_env_pairs(env_path)
    updates: dict[str, str] = {}

    if not pairs.get("AUTO_OPEN_BROWSER"):
        updates["AUTO_OPEN_BROWSER"] = "1"
    if not pairs.get("PREFER_CHROME_BROWSER"):
        updates["PREFER_CHROME_BROWSER"] = "1"
    if not pairs.get("AUTO_OPEN_BROWSER_DELAY_SECONDS"):
        updates["AUTO_OPEN_BROWSER_DELAY_SECONDS"] = "2"
    if not pairs.get("AUTO_OPEN_BROWSER_TIMEOUT_SECONDS"):
        updates["AUTO_OPEN_BROWSER_TIMEOUT_SECONDS"] = "45"
    if not pairs.get("AUTO_OPEN_BROWSER_URL"):
        port = pairs.get("LAN_SERVER_PORT") or os.getenv("LAN_SERVER_PORT", "8000") or "8000"
        updates["AUTO_OPEN_BROWSER_URL"] = f"http://127.0.0.1:{port}"

    # لا نكتب CHROME_EXE_PATH إذا كان المستخدم ضبطه يدويًا، أو إذا استعمل الاسم البديل.
    if not pairs.get("CHROME_EXE_PATH") and not pairs.get("GOOGLE_CHROME_PATH"):
        chrome = _find_google_chrome()
        if chrome:
            updates["CHROME_EXE_PATH"] = _normalize_env_path(chrome)

    return updates


def ensure_device_node_env(env_path: Path, app_data_dir: Path) -> None:
    """Prepare this installed copy as an independent device node.

    كل جهاز يجب أن يملك SERVER_ID مختلفًا، بينما OFFICE_ID و SYNC_TOKEN يبقيان موحدين
    داخل نفس المكتب حتى تتم مزامنة نفس البيانات عبر الخادم المركزي.
    """
    pairs = _read_env_pairs(env_path)
    updates: dict[str, str] = {}

    if not pairs.get("DJANGO_SECRET_KEY") or pairs.get("DJANGO_SECRET_KEY") in {"change-me", "change-me-for-lan-server"}:
        updates["DJANGO_SECRET_KEY"] = "tc-" + secrets.token_urlsafe(48)

    device_mode = str(pairs.get("DEVICE_NODE_MODE", "1")).strip().lower() in {"1", "true", "yes", "on"}
    server_id = str(pairs.get("SERVER_ID", "")).strip()
    initialized = str(pairs.get("DEVICE_NODE_INITIALIZED", "")).strip() == "1"
    placeholders = {"", "auto", "server-auto", "server-oran-01", "server-mostaganem-01", "change-me"}
    if device_mode and (not initialized or server_id.lower() in placeholders):
        host = _safe_slug(socket.gethostname())
        updates["SERVER_ID"] = f"device-{host}-{secrets.token_hex(4)}"
        updates["DEVICE_NODE_INITIALIZED"] = "1"

    if device_mode and not pairs.get("DEVICE_REQUEST_SECRET"):
        updates["DEVICE_REQUEST_SECRET"] = secrets.token_urlsafe(32)

    # في النسخة الآمنة لا نضع SYNC_TOKEN داخل المثبت. الجهاز يعمل محليًا أولًا،
    # ثم يطلب الاعتماد من جهاز المطوّر. بعد الاعتماد فقط يتم تفعيل المزامنة.
    if not pairs.get("SYNC_TOKEN") or str(pairs.get("SYNC_TOKEN", "")).startswith("change-"):
        updates.setdefault("CENTRAL_SYNC_ENABLED", "0")
        updates.setdefault("SYNC_WORKER_ENABLED", "0")
    else:
        updates.setdefault("CENTRAL_SYNC_ENABLED", pairs.get("CENTRAL_SYNC_ENABLED", "1") or "1")
        updates.setdefault("SYNC_WORKER_ENABLED", pairs.get("SYNC_WORKER_ENABLED", "1") or "1")
    updates.setdefault("SYNC_TRACKING_ENABLED", "1")
    updates.setdefault("SYNC_APPLY_INBOX_ENABLED", "1")
    updates.setdefault("IN_PROCESS_SYNC_WORKER_ENABLED", pairs.get("IN_PROCESS_SYNC_WORKER_ENABLED", "1") or "1")
    if not pairs.get("SYNC_TRACKED_MODELS"):
        updates["SYNC_TRACKED_MODELS"] = "trainees.حضوري_أولي,trainees.تمهين,trainees.دفعة,trainees.مسائي_ومعابر"
    if not pairs.get("SYNC_WORKER_INTERVAL_SECONDS"):
        updates["SYNC_WORKER_INTERVAL_SECONDS"] = "120"

    updates.update(ensure_browser_env_defaults(env_path, app_data_dir, pairs))

    if updates:
        _write_env_value(env_path, updates)

def python_executable() -> str:
    return sys.executable


def build_env(env_path: Path, app_data_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    load_dotenv_file(env_path)
    env.update(os.environ)
    env["DJANGO_SETTINGS_MODULE"] = "training_center.settings_lan"
    env["DJANGO_ENV"] = "lan"
    env["APP_DATA_DIR"] = str(app_data_dir)
    env["ENV_FILE_PATH"] = str(env_path)
    return env


def run_manage(args: list[str], env_path: Path, app_data_dir: Path) -> None:
    """Run Django management commands safely inside the frozen EXE.

    In a PyInstaller --noconsole build, sys.stdout/sys.stderr can be None.
    Django writes command output through self.stdout, so we redirect command
    output to a log file instead of displaying migrations in a black window.
    """
    import io
    import contextlib

    env = build_env(env_path, app_data_dir)
    os.environ.update(env)
    if str(BUNDLED_ROOT) not in sys.path:
        sys.path.insert(0, str(BUNDLED_ROOT))

    command_log = LOGS_DIR / "django_commands.log"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    capture = io.StringIO()

    old_stdout, old_stderr, old_argv = sys.stdout, sys.stderr, sys.argv[:]
    try:
        sys.stdout = capture
        sys.stderr = capture
        sys.argv = ["manage.py", *args, "--settings=training_center.settings_lan"]
        from django.core.management import execute_from_command_line
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            execute_from_command_line(sys.argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
        if code not in (0, None):
            raise RuntimeError(f"Django command failed with exit code {code}: {' '.join(args)}") from exc
    finally:
        output = capture.getvalue()
        if output.strip():
            with command_log.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(f"\n[{utc_now()}] manage.py {' '.join(args)}\n")
                fh.write(output)
                if not output.endswith("\n"):
                    fh.write("\n")
        sys.argv = old_argv
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def resolve_host_port() -> tuple[str, int]:
    host = os.getenv("LAN_SERVER_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.getenv("LAN_SERVER_PORT", "8000"))
    return host, port




def detect_local_ipv4() -> str:
    """Best-effort LAN IPv4 detection without requiring internet."""
    candidates: list[str] = []

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET, type=socket.SOCK_STREAM):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                candidates.append(ip)
    except Exception:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                candidates.insert(0, ip)
    except Exception:
        pass

    for ip in candidates:
        if ip and not ip.startswith("127."):
            return ip
    return "127.0.0.1"


def apply_dynamic_network_env(port: int) -> tuple[str, str]:
    """
    Detect the current LAN IPv4 and expose it through runtime environment variables.
    This keeps .env simple while making the public URL automatic on each device.
    """
    detected_ip = detect_local_ipv4()
    detected_public_url = f"http://{detected_ip}:{port}"

    os.environ["DETECTED_LAN_IP"] = detected_ip
    os.environ["LAN_SERVER_PUBLIC_BASE_URL"] = detected_public_url

    hostnames = {
        "127.0.0.1",
        "localhost",
        detected_ip,
        socket.gethostname(),
    }

    existing_hosts = {
        item.strip()
        for item in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    }
    merged_hosts = []
    for item in [*hostnames, *existing_hosts]:
        if item and item not in merged_hosts:
            merged_hosts.append(item)
    os.environ["DJANGO_ALLOWED_HOSTS"] = ",".join(merged_hosts)

    origin_candidates = {
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        detected_public_url,
        f"http://{socket.gethostname()}:{port}",
    }
    existing_origins = {
        item.strip()
        for item in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
        if item.strip()
    }
    merged_origins = []
    for item in [*origin_candidates, *existing_origins]:
        if item and item not in merged_origins:
            merged_origins.append(item)
    os.environ["DJANGO_CSRF_TRUSTED_ORIGINS"] = ",".join(merged_origins)

    return detected_ip, detected_public_url

def verify_tcp_socket(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP OK {host}:{port}"
    except Exception as exc:
        return False, f"TCP FAIL {host}:{port} -> {exc}"



def ensure_postgres_database_exists() -> None:
    """Create the configured PostgreSQL database automatically on first run.

    This is needed on office-server machines because the user should not run
    python manage.py migrate manually and Python may not even be installed.
    """
    db_engine = os.getenv("DB_ENGINE", "").strip().lower()
    if db_engine not in {"postgres", "postgresql"}:
        return

    db_name = os.getenv("POSTGRES_DB", "training_center").strip() or "training_center"
    db_user = os.getenv("POSTGRES_USER", "postgres").strip() or "postgres"
    db_password = os.getenv("POSTGRES_PASSWORD", "").strip()
    db_host = os.getenv("POSTGRES_HOST", "127.0.0.1").strip() or "127.0.0.1"
    db_port = int(os.getenv("POSTGRES_PORT", "5432"))

    append_startup_log(f"فحص قاعدة PostgreSQL المطلوبة: {db_name}")
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except Exception as exc:
        append_startup_log(f"تعذر استيراد psycopg2 لإنشاء قاعدة البيانات: {exc}")
        raise

    conn = psycopg2.connect(
        dbname="postgres",
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        connect_timeout=8,
    )
    try:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            exists = cur.fetchone() is not None
            if not exists:
                safe_db_name = '"' + db_name.replace('"', '""') + '"'
                cur.execute(f"CREATE DATABASE {safe_db_name} WITH ENCODING 'UTF8'")
                append_startup_log(f"تم إنشاء قاعدة البيانات: {db_name}")
            else:
                append_startup_log(f"قاعدة البيانات موجودة مسبقًا: {db_name}")
    finally:
        conn.close()
    write_status(stage="postgres_database_ready", postgres_db=db_name)


def setup_office_once(env_path: Path, app_data_dir: Path) -> None:
    """Prepare an office-server installation without serving HTTP."""
    startup_checks()
    ensure_postgres_database_exists()
    append_startup_log("بدء collectstatic --noinput ضمن setup-office")
    run_manage(["collectstatic", "--noinput"], env_path, app_data_dir)
    append_startup_log("نجاح collectstatic ضمن setup-office")
    append_startup_log("بدء migrate --noinput ضمن setup-office")
    run_manage(["migrate", "--noinput"], env_path, app_data_dir)
    append_startup_log("نجاح migrate ضمن setup-office")
    append_startup_log("بدء check ضمن setup-office")
    run_manage(["check"], env_path, app_data_dir)
    append_startup_log("نجاح check ضمن setup-office")
    if os.getenv("OFFICE_ID", "").strip() and os.getenv("SYNC_TOKEN", "").strip():
        append_startup_log("بدء init_office_identity ضمن setup-office")
        run_manage(["init_office_identity"], env_path, app_data_dir)
        append_startup_log("نجاح init_office_identity ضمن setup-office")
    else:
        append_startup_log("تم تجاوز init_office_identity لأن الجهاز ينتظر موافقة المطوّر ولا يملك SYNC_TOKEN بعد")
    ensure_developer_account(env_path, app_data_dir)
    write_status(status="ready", stage="setup_office_done")

def startup_checks() -> None:
    db_engine = os.getenv("DB_ENGINE", "").strip().lower()
    if db_engine not in {"postgres", "postgresql"}:
        raise SystemExit("وضع LAN يتطلب PostgreSQL. تحقق من ملف البيئة.")
    if not os.getenv("POSTGRES_PASSWORD", "").strip():
        raise SystemExit("ملف البيئة محمّل لكن POSTGRES_PASSWORD فارغة. عدّل C:\\TrainingCenterData\\.env")
    host = os.getenv("POSTGRES_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    ok, message = verify_tcp_socket(host, port)
    append_startup_log(message)
    write_status(stage="startup_checks", postgres_socket_ok=ok, postgres_socket_message=message)
    if not ok:
        raise SystemExit(2)


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_pid_lock() -> None:
    if PID_FILE.exists():
        try:
            existing_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            existing_pid = 0
        if existing_pid and is_process_running(existing_pid):
            raise SystemExit(f"يوجد سيرفر LAN يعمل بالفعل بالمعرّف PID={existing_pid}")
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def release_pid_lock() -> None:
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


def print_runtime_summary() -> None:
    host, port = resolve_host_port()
    public_url = os.getenv("LAN_SERVER_PUBLIC_BASE_URL", "").strip()
    if not public_url:
        detected_ip = os.getenv("DETECTED_LAN_IP", "").strip()
        if detected_ip:
            public_url = f"http://{detected_ip}:{port}"
        else:
            public_url = f"http://{socket.gethostname()}:{port}"

    print("=" * 72)
    print(f"{APP_NAME} LAN server")
    print(f"APP_DATA_DIR: {APP_DATA_DIR}")
    print(f"LISTEN: http://{host}:{port}")
    print(f"PUBLIC: {public_url}")
    print(f"DEVICE: {socket.gethostname()}")
    print(f"HEALTH: {public_url.rstrip('/')}/healthz/")
    print(f"READY:  {public_url.rstrip('/')}/readyz/")
    print("=" * 72)


def write_runtime_bootstrap_state(host: str, port: int, env_path: Path) -> None:
    write_status(
        pid=os.getpid(),
        status="starting",
        app_data_dir=str(APP_DATA_DIR),
        host=host,
        port=port,
        env_file=str(env_path),
        db_engine=os.getenv("DB_ENGINE", ""),
        startup_tasks_enabled=os.getenv("RUN_STARTUP_TASKS", "1") == "1",
        detected_lan_ip=os.getenv("DETECTED_LAN_IP", ""),
        public_base_url=os.getenv("LAN_SERVER_PUBLIC_BASE_URL", ""),
    )




def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _find_google_chrome() -> Path | None:
    """Return Google Chrome executable if installed on Windows, otherwise None.

    بعض الأجهزة لا تضع chrome.exe داخل PATH، لذلك لا يكفي البحث بـ which فقط.
    هنا نبحث بالترتيب في:
    1) مسار يدوي من ملف .env عند الحاجة
    2) Windows App Paths داخل Registry
    3) المسارات المعروفة Program Files / Program Files (x86) / LocalAppData
    4) PATH
    """
    candidates: list[Path] = []

    def add_candidate(value: str | os.PathLike | None) -> None:
        if not value:
            return
        try:
            candidate = Path(str(value).strip().strip('"'))
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        except Exception:
            return

    # اختيار يدوي اختياري من ملف .env إذا كان Chrome مثبتًا في مسار غير عادي.
    add_candidate(os.getenv("CHROME_EXE_PATH", ""))
    add_candidate(os.getenv("GOOGLE_CHROME_PATH", ""))

    # Windows Registry: هذا هو أدق مكان لمعرفة مسار Chrome الحقيقي إذا كان مثبتًا.
    if os.name == "nt":
        try:
            import winreg  # type: ignore
            registry_locations = (
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            )
            for hive, subkey in registry_locations:
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        value, _ = winreg.QueryValueEx(key, "")
                        add_candidate(value)
                except OSError:
                    continue
        except Exception:
            pass

    # المسارات المعروفة في ويندوز.
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.getenv(env_name, "").strip()
        if root:
            add_candidate(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")

    # احتمال إضافي إذا لم تكن LOCALAPPDATA موجودة في بيئة التشغيل.
    if os.name == "nt":
        user_profile = os.getenv("USERPROFILE", "").strip()
        if user_profile:
            add_candidate(Path(user_profile) / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe")

        # مسارات ثابتة احتياطية، مفيدة عندما تكون بيئة التشغيل لا تحتوي ProgramFiles بشكل صحيح.
        add_candidate(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        add_candidate(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")

    # PATH كحل أخير.
    found = which("chrome.exe") or which("chrome")
    if found:
        add_candidate(found)

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                append_startup_log(f"تم العثور على Google Chrome: {candidate}")
                return candidate
        except Exception:
            continue

    append_startup_log("لم يتم العثور على Google Chrome، سيتم استعمال المتصفح الافتراضي")
    return None


def _open_url_in_preferred_browser(url: str) -> None:
    """Open Chrome first when available, otherwise fall back to the default browser."""
    prefer_chrome = os.getenv("PREFER_CHROME_BROWSER", "1").strip().lower() in {"1", "true", "yes", "on"}
    if prefer_chrome:
        chrome = _find_google_chrome()
        if chrome:
            try:
                subprocess.Popen([str(chrome), "--new-tab", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                append_startup_log(f"تم فتح Google Chrome تلقائيًا: {url}")
                return
            except Exception as exc:
                append_startup_log(f"تعذر فتح Google Chrome، سيتم استعمال المتصفح الافتراضي: {exc}")

    try:
        if os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            webbrowser.open(url, new=1, autoraise=True)
        append_startup_log(f"تم فتح المتصفح الافتراضي تلقائيًا: {url}")
    except Exception as exc:
        append_startup_log(f"تعذر فتح المتصفح تلقائيًا: {exc}")


def _wait_for_server_then_open_browser(port: int) -> None:
    if _env_bool("OPENED_FROM_CENTRAL", "0"):
        append_startup_log("تم منع فتح المتصفح تلقائيًا لأن المكتب فُتح من لوحة المطور المركزية")
        return
    delay = float(os.getenv("AUTO_OPEN_BROWSER_DELAY_SECONDS", "2.0") or "2.0")
    timeout = float(os.getenv("AUTO_OPEN_BROWSER_TIMEOUT_SECONDS", "45") or "45")
    time.sleep(max(0.0, delay))

    deadline = time.time() + max(5.0, timeout)
    while time.time() < deadline:
        ok, _message = verify_tcp_socket("127.0.0.1", port, timeout=1.0)
        if ok:
            url = os.getenv("AUTO_OPEN_BROWSER_URL", "").strip() or f"http://127.0.0.1:{port}"
            _open_url_in_preferred_browser(url)
            return
        time.sleep(1.0)
    append_startup_log("انتهت مهلة فتح المتصفح تلقائيًا قبل أن يصبح الخادم جاهزًا")


def start_auto_open_browser_thread(port: int) -> None:
    if _env_bool("OPENED_FROM_CENTRAL", "0"):
        append_startup_log("تم تعطيل فتح المتصفح تلقائيًا لأن التشغيل جاء من لوحة المطور المركزية")
        return
    if not _env_bool("AUTO_OPEN_BROWSER", "1"):
        append_startup_log("تم تعطيل فتح المتصفح تلقائيًا AUTO_OPEN_BROWSER=0")
        return
    thread = threading.Thread(target=_wait_for_server_then_open_browser, args=(port,), daemon=True, name="TrainingCenterOpenBrowser")
    thread.start()
    append_startup_log("تم تجهيز فتح المتصفح تلقائيًا بعد جاهزية الخادم")



def ensure_developer_account(env_path: Path, app_data_dir: Path) -> None:
    # لا يتم إنشاء حساب المطوّر في أجهزة الموظفين إلا إذا فعّل المطوّر ذلك صراحةً
    # داخل ملف .env الخاص بجهازه فقط. لا نضع كلمة مرور المطوّر داخل مثبت الأجهزة.
    if os.getenv("DEV_LOGIN_ENABLED", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    if not (os.getenv("DEV_USERNAME", "").strip() and os.getenv("DEV_PASSWORD", "").strip()):
        return
    append_startup_log("بدء ensure_developer --reset-password")
    run_manage(["ensure_developer", "--reset-password"], env_path, app_data_dir)
    append_startup_log("نجاح ensure_developer")
    write_status(stage="ensure_developer_done")

def run_startup_tasks(env_path: Path, app_data_dir: Path) -> None:
    if os.getenv("RUN_STARTUP_TASKS", "1").strip() not in {"1", "true", "True", "yes", "on"}:
        append_startup_log("تم تجاوز collectstatic/migrate لأن RUN_STARTUP_TASKS=0")
        return
    ensure_postgres_database_exists()
    append_startup_log("بدء collectstatic --noinput")
    run_manage(["collectstatic", "--noinput"], env_path, app_data_dir)
    append_startup_log("نجاح collectstatic")
    write_status(stage="collectstatic_done")
    append_startup_log("بدء migrate --noinput")
    run_manage(["migrate", "--noinput"], env_path, app_data_dir)
    append_startup_log("نجاح migrate")
    append_startup_log("بدء check")
    run_manage(["check"], env_path, app_data_dir)
    append_startup_log("نجاح check")
    write_status(stage="migrate_check_done")
    ensure_developer_account(env_path, app_data_dir)




def _post_json_simple(url: str, payload: dict[str, Any], timeout: int = 15) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw or "{}")


def try_device_approval_exchange(env_path: Path, app_data_dir: Path) -> bool:
    """Register this device and poll for the approved sync configuration.

    Returns True if the device has SYNC_TOKEN and can sync, False if it is still pending.
    """
    pairs = _read_env_pairs(env_path)
    if (pairs.get("OFFICE_ID") or "").strip() and (pairs.get("SYNC_TOKEN") or "").strip() and not str(pairs.get("SYNC_TOKEN", "")).startswith("change-"):
        return True

    central_url = (pairs.get("CENTRAL_URL") or os.getenv("CENTRAL_URL", "")).strip().rstrip("/")
    if not central_url:
        try:
            for candidate in [Path(sys.executable).resolve().parent / "CENTRAL_URL_FOR_INSTALLER.txt", Path.cwd() / "CENTRAL_URL_FOR_INSTALLER.txt"]:
                if candidate.exists():
                    value = candidate.read_text(encoding="utf-8").strip().rstrip("/")
                    if value.startswith(("http://", "https://")):
                        central_url = value
                        _write_env_value(env_path, {"CENTRAL_URL": central_url})
                        pairs["CENTRAL_URL"] = central_url
                        break
        except Exception as exc:
            append_startup_log(f"central_url_fallback_error: {exc}")
    server_id = (pairs.get("SERVER_ID") or os.getenv("SERVER_ID", "")).strip()
    request_secret = (pairs.get("DEVICE_REQUEST_SECRET") or os.getenv("DEVICE_REQUEST_SECRET", "")).strip()
    if not central_url or not server_id or not request_secret or server_id.lower() == "auto":
        append_startup_log("device_approval_waiting: CENTRAL_URL/SERVER_ID/DEVICE_REQUEST_SECRET غير مكتملة")
        return False

    host, port = resolve_host_port()
    lan_ip = os.getenv("DETECTED_LAN_IP", "") or detect_local_ipv4()
    payload = {
        "server_id": server_id,
        "request_secret": request_secret,
        "hostname": socket.gethostname(),
        "device_label": socket.gethostname(),
        "lan_ip": lan_ip,
        "app_version": pairs.get("APP_VERSION") or os.getenv("APP_VERSION", ""),
        "central_url": central_url,
        "local_url": f"http://{lan_ip}:{port}",
    }
    try:
        reg = _post_json_simple(central_url + "/api/devices/register/", payload, timeout=10)
        append_startup_log("device_register_response: " + json.dumps(reg, ensure_ascii=False)[:1000])
        cfg = _post_json_simple(central_url + "/api/devices/config/", payload, timeout=10)
        append_startup_log("device_config_response: " + json.dumps({k: v for k, v in cfg.items() if k != "config"}, ensure_ascii=False)[:1000])
    except Exception as exc:
        append_startup_log(f"device_approval_exchange_error: {exc}")
        write_status(stage="device_approval_error", approval_error=str(exc))
        return False

    if cfg.get("ok") and cfg.get("status") == "approved" and isinstance(cfg.get("config"), dict):
        config = {str(k): str(v) for k, v in cfg["config"].items()}
        _write_env_value(env_path, config)
        load_dotenv_file(env_path)
        os.environ.update(config)
        # حدّث هوية المزامنة داخل قاعدة البيانات بعد كتابة .env.
        try:
            run_manage(["init_office_identity"], env_path, app_data_dir)
        except Exception as exc:
            append_startup_log(f"init_office_identity_after_approval_error: {exc}")
        write_status(stage="device_approved", office_id=config.get("OFFICE_ID"), server_id=config.get("SERVER_ID"))
        return True

    write_status(stage="device_pending_approval", server_id=server_id, approval_status=cfg.get("status", "pending"))
    return False

def _sync_worker_loop(env_path: Path, app_data_dir: Path) -> None:
    """Run push/pull/apply periodically inside the server process.

    هذا يجعل كل جهاز مستقل يرسل تعديلاته ويسحب تعديلات الأجهزة الأخرى تلقائيًا
    بدون تشغيل أمر Python منفصل وبدون تثبيت Python على الجهاز.
    """
    time.sleep(int(os.getenv("IN_PROCESS_SYNC_INITIAL_DELAY_SECONDS", "20")))
    while True:
        try:
            load_dotenv_file(env_path)
            approved = try_device_approval_exchange(env_path, app_data_dir)
            load_dotenv_file(env_path)
            if not approved:
                time.sleep(60)
                continue
            if os.getenv("SYNC_WORKER_ENABLED", "1").strip().lower() not in {"1", "true", "yes", "on"}:
                time.sleep(30)
                continue
            if not os.getenv("CENTRAL_URL", "").strip():
                time.sleep(60)
                continue
            os.environ.update(build_env(env_path, app_data_dir))
            from sync_core.worker import run_sync_once
            result = run_sync_once(push=True, pull=True, apply=True, force=True)
            append_startup_log("sync_worker_once: " + json.dumps(result, ensure_ascii=False, default=str)[:2000])
            write_status(stage="sync_worker_once", last_sync_result=result)
        except Exception as exc:
            append_startup_log(f"sync_worker_error: {exc}")
            write_status(stage="sync_worker_error", sync_error=str(exc))
        interval = int(os.getenv("SYNC_WORKER_INTERVAL_SECONDS", "300"))
        time.sleep(max(30, interval))


def start_in_process_sync_worker(env_path: Path, app_data_dir: Path) -> None:
    if os.getenv("IN_PROCESS_SYNC_WORKER_ENABLED", "1").strip().lower() not in {"1", "true", "yes", "on"}:
        append_startup_log("تم تعطيل عامل المزامنة الداخلي IN_PROCESS_SYNC_WORKER_ENABLED=0")
        return
    thread = threading.Thread(target=_sync_worker_loop, args=(env_path, app_data_dir), daemon=True, name="TrainingCenterSyncWorker")
    thread.start()
    append_startup_log("تم تشغيل عامل المزامنة الداخلي للأجهزة المستقلة")

def handle_exit(signum: int, _frame: Any) -> None:
    append_startup_log(f"استقبال إشارة إنهاء: {signum}")
    write_status(status="stopping", signal=signum)
    release_pid_lock()
    raise SystemExit(0)


def main() -> None:
    global APP_DATA_DIR, RUNTIME_DIR, LOGS_DIR, STATUS_FILE, PID_FILE, ENV_FILE, LEGACY_ENV_FILE

    APP_DATA_DIR = resolve_app_data_dir()
    RUNTIME_DIR = APP_DATA_DIR / "runtime_state"
    LOGS_DIR = APP_DATA_DIR / "logs"
    STATUS_FILE = RUNTIME_DIR / "lan_status.json"
    PID_FILE = RUNTIME_DIR / "lan_server.pid"
    ENV_FILE = APP_DATA_DIR / ".env"
    LEGACY_ENV_FILE = APP_DATA_DIR / ".env.lan"

    ensure_runtime_dirs()
    env_path = ensure_env_file(APP_DATA_DIR)
    ensure_device_node_env(env_path, APP_DATA_DIR)
    load_dotenv_file(env_path)

    os.environ["DJANGO_SETTINGS_MODULE"] = "training_center.settings_lan"
    os.environ["DJANGO_ENV"] = "lan"
    os.environ["APP_DATA_DIR"] = str(APP_DATA_DIR)
    os.environ["ENV_FILE_PATH"] = str(env_path)

    command = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "serve"
    if command in {"setup-office", "setup_office", "setup-device", "setup_device", "setup", "migrate", "init"}:
        host, port = resolve_host_port()
        detected_ip, detected_public_url = apply_dynamic_network_env(port)
        write_runtime_bootstrap_state(host, port, env_path)
        if command == "migrate":
            startup_checks()
            ensure_postgres_database_exists()
            run_manage(["migrate", "--noinput"], env_path, APP_DATA_DIR)
            run_manage(["check"], env_path, APP_DATA_DIR)
            write_status(status="ready", stage="migrate_check_done")
        else:
            setup_office_once(env_path, APP_DATA_DIR)
        print("تم تجهيز خادم المكتب بنجاح.")
        return

    signal.signal(signal.SIGTERM, handle_exit)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, handle_exit)

    acquire_pid_lock()
    host, port = resolve_host_port()
    detected_ip, detected_public_url = apply_dynamic_network_env(port)
    print(f"DETECTED_IP: {detected_ip}")
    print(f"DETECTED_PUBLIC_URL: {detected_public_url}")
    write_runtime_bootstrap_state(host, port, env_path)

    try:
        startup_checks()
        run_startup_tasks(env_path, APP_DATA_DIR)
        try_device_approval_exchange(env_path, APP_DATA_DIR)
        start_in_process_sync_worker(env_path, APP_DATA_DIR)
        print_runtime_summary()
        start_auto_open_browser_thread(port)
        append_startup_log(f"تشغيل waitress على {host}:{port}")
        write_status(status="running", stage="serve")

        from waitress import serve
        serve(
            __import__("training_center.wsgi", fromlist=["application"]).application,
            host=host,
            port=port,
            threads=int(os.getenv("WAITRESS_THREADS", "8")),
            connection_limit=int(os.getenv("WAITRESS_CONNECTION_LIMIT", "100")),
            channel_timeout=int(os.getenv("WAITRESS_CHANNEL_TIMEOUT", "120")),
            cleanup_interval=int(os.getenv("WAITRESS_CLEANUP_INTERVAL", "30")),
            ident=os.getenv("WAITRESS_IDENT", "TrainingCenterLAN"),
        )
    except Exception as exc:
        append_startup_log(f"فشل تشغيل سيرفر LAN: {exc}")
        write_status(status="failed", error=str(exc))
        raise
    finally:
        release_pid_lock()


if __name__ == "__main__":
    main()
