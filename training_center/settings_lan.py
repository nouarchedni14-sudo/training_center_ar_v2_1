import os
import socket
from urllib.parse import urlparse
from pathlib import Path


def _load_env_file(env_path: Path) -> bool:
    if not env_path.exists():
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            # Override existing environment values so stale values do not win.
            os.environ[key] = value
    return True


BASE_DIR = Path(__file__).resolve().parent.parent
CENTRAL_APP_DATA_DIR = Path(r"C:\TrainingCenterData")

# Prefer an explicitly provided env file path if available.
explicit_env = os.getenv("ENV_FILE_PATH", "").strip()
app_data_env = os.getenv("APP_DATA_DIR", "").strip()
env_candidates = []
if explicit_env:
    env_candidates.append(Path(explicit_env))
if app_data_env:
    # مهم: كل مكتب يمكن أن يملك مجلد بيانات مستقل مثل
    # C:\TrainingCenterData_Tissemsilt، لذلك يجب البحث عن .env داخله
    # عند تشغيل manage.py أو أوامر التصحيح يدويًا مع APP_DATA_DIR فقط.
    app_data_path = Path(app_data_env)
    env_candidates.extend([
        app_data_path / ".env",
        app_data_path / ".env.lan",
    ])

env_candidates.extend([
    CENTRAL_APP_DATA_DIR / ".env",
    CENTRAL_APP_DATA_DIR / ".env.lan",
    BASE_DIR / ".env",
    BASE_DIR / ".env.lan",
    BASE_DIR / "runtime_lan" / ".env",
    BASE_DIR / "runtime_lan" / ".env.lan",
])

LOADED_ENV_FILE = None
for candidate in env_candidates:
    if _load_env_file(candidate):
        LOADED_ENV_FILE = candidate
        break

# Default to the central data directory when no value was provided.
if not os.getenv("APP_DATA_DIR", "").strip():
    os.environ["APP_DATA_DIR"] = str(CENTRAL_APP_DATA_DIR)

from .settings_base import *  # noqa: E402,F401,F403

DB_ENGINE = os.getenv("DB_ENGINE", "").strip().lower()
if DB_ENGINE not in {"postgres", "postgresql"}:
    raise RuntimeError(
        "وضع LAN يتطلب PostgreSQL. تأكد من تمرير ENV_FILE_PATH أو APP_DATA_DIR الصحيح لمجلد المكتب، "
        "وأن ملف .env يحتوي على DB_ENGINE=postgres."
    )

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1").strip() or "127.0.0.1"
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "training_center").strip() or "training_center"
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres").strip() or "postgres"
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

if not POSTGRES_PASSWORD:
    raise RuntimeError(
        "ملف البيئة تم تحميله لكن POSTGRES_PASSWORD فارغة. عدّل ملف .env الخاص بمجلد المكتب وضع كلمة مرور PostgreSQL."
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": POSTGRES_DB,
        "USER": POSTGRES_USER,
        "PASSWORD": POSTGRES_PASSWORD,
        "HOST": POSTGRES_HOST,
        "PORT": POSTGRES_PORT,
        "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "120")),
    }
}

APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", str(CENTRAL_APP_DATA_DIR)))
MEDIA_ROOT = APP_DATA_DIR / "media"
STATIC_ROOT = APP_DATA_DIR / "staticfiles"

def _current_lan_hosts() -> list[str]:
    hosts: set[str] = set()
    try:
        name = socket.gethostname().strip()
        if name:
            hosts.update({name, name.lower(), name.upper()})
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            ip = (info[4][0] or "").strip()
            if ip and not ip.startswith("127."):
                hosts.add(ip)
    except Exception:
        pass
    return [h for h in hosts if h]


ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]
for h in _current_lan_hosts():
    if h not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(h)

_lan_port_for_csrf = os.getenv("LAN_SERVER_PORT", "8000").strip() or "8000"
CSRF_TRUSTED_ORIGINS = [
    u.strip()
    for u in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", f"http://127.0.0.1:{_lan_port_for_csrf},http://localhost:{_lan_port_for_csrf}").split(",")
    if u.strip()
]
for h in _current_lan_hosts():
    origin = f"http://{h}:{_lan_port_for_csrf}"
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

# إذا تم نشر مكتب محلي عبر نطاق إنترنت أو VPN مع رابط عام، أضفه تلقائيًا
# إلى CSRF_TRUSTED_ORIGINS عند ضبط LAN_SERVER_PUBLIC_BASE_URL.
_public_base_candidates = [
    os.getenv("LAN_SERVER_PUBLIC_BASE_URL", ""),
    os.getenv("PUBLIC_BASE_URL", ""),
]
for _public_base in _public_base_candidates:
    _public_base = (_public_base or "").strip().rstrip("/")
    if not _public_base:
        continue
    _parsed = urlparse(_public_base)
    if _parsed.scheme and _parsed.netloc:
        _origin = f"{_parsed.scheme}://{_parsed.netloc}"
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "0") == "1"

LAN_SERVER_HOST = os.getenv("LAN_SERVER_HOST", "0.0.0.0").strip() or "0.0.0.0"
LAN_SERVER_PORT = int(os.getenv("LAN_SERVER_PORT", "8000"))
LAN_SERVER_PUBLIC_BASE_URL = os.getenv("LAN_SERVER_PUBLIC_BASE_URL", "http://127.0.0.1:8000").strip() or "http://127.0.0.1:8000"

# عزل جلسة كل مكتب محلي حسب المنفذ حتى لا تختلط مع جلسة الخادم المركزي 9000.
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", f"training_center_lan_{LAN_SERVER_PORT}_sessionid")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", f"training_center_lan_{LAN_SERVER_PORT}_csrftoken")
LAN_HEALTH_TOKEN = os.getenv("LAN_HEALTH_TOKEN", "")

WAITRESS_THREADS = int(os.getenv("WAITRESS_THREADS", "8"))
WAITRESS_CONNECTION_LIMIT = int(os.getenv("WAITRESS_CONNECTION_LIMIT", "100"))
WAITRESS_CHANNEL_TIMEOUT = int(os.getenv("WAITRESS_CHANNEL_TIMEOUT", "120"))
