"""إعدادات الخادم المركزي للمزامنة والترخيص والتحديثات.

هذا الوضع لا يستخدم كخادم مكتب محلي. يستعمل عند المطور أو على VPS.
"""
import os
import socket
from urllib.parse import urlparse
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CENTRAL_APP_DATA_DIR = Path(os.getenv("CENTRAL_APP_DATA_DIR", r"C:\TrainingCenterCentralData"))


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
            os.environ[key] = value
    return True


# نحدد الوضع قبل تحميل settings_base حتى يختار ملف البيئة الصحيح عند الحاجة.
os.environ.setdefault("DJANGO_ENV", "central")
os.environ.setdefault("APP_DATA_DIR", str(CENTRAL_APP_DATA_DIR))

explicit_env = os.getenv("ENV_FILE_PATH", "").strip()
for candidate in [
    Path(explicit_env) if explicit_env else None,
    CENTRAL_APP_DATA_DIR / ".env",
    CENTRAL_APP_DATA_DIR / ".env.central",
    BASE_DIR / ".env.central",
    BASE_DIR / ".env",
]:
    if candidate and _load_env_file(candidate):
        break

from .settings_base import *  # noqa: E402,F401,F403

APP_MODE = "central_server"
SYNC_MODE = "central_server"
SYNC_TRACKING_ENABLED = False
CENTRAL_SYNC_API_ENABLED = True
CENTRAL_AUTO_REGISTER_OFFICES = env_bool("CENTRAL_AUTO_REGISTER_OFFICES", True)

# الخادم المركزي لا يحتاج فرض ترخيص المكتب المحلي على صفحات API.
LICENSE_ENFORCEMENT_ENABLED = False

APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", str(CENTRAL_APP_DATA_DIR)))
MEDIA_ROOT = APP_DATA_DIR / "media"
STATIC_ROOT = APP_DATA_DIR / "staticfiles"

def _current_lan_hosts() -> list[str]:
    """إضافة اسم جهاز المطوّر و IP الحالي تلقائيًا حتى لا يتعطل الخادم عند تغيّر DHCP."""
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


raw_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
if os.getenv("CENTRAL_ALLOW_ALL_HOSTS", "0") == "1":
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]
    for h in _current_lan_hosts():
        if h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h)

CSRF_TRUSTED_ORIGINS = [
    u.strip()
    for u in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:9000,http://localhost:9000").split(",")
    if u.strip()
]
for h in _current_lan_hosts():
    origin = f"http://{h}:9000"
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

# عند نشر الخادم المركزي على الإنترنت ضع CENTRAL_PUBLIC_URL مثل:
# https://updates.example.com؛ سنضيفه تلقائيًا إلى CSRF_TRUSTED_ORIGINS
# ونستخدمه أيضًا في تعليمات ربط المكاتب.
CENTRAL_PUBLIC_URL = (
    os.getenv("CENTRAL_PUBLIC_URL")
    or os.getenv("CENTRAL_PUBLIC_BASE_URL")
    or globals().get("CENTRAL_PUBLIC_URL", "")
).strip().rstrip("/")
if CENTRAL_PUBLIC_URL:
    parsed = urlparse(CENTRAL_PUBLIC_URL)
    if parsed.scheme and parsed.netloc:
        public_origin = f"{parsed.scheme}://{parsed.netloc}"
        if public_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(public_origin)

DB_ENGINE = os.getenv("DB_ENGINE", "postgres").strip().lower()
if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "training_center_central"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "120")),
        }
    }
else:
    sqlite_path = Path(os.getenv("SQLITE_NAME", str(APP_DATA_DIR / "central.sqlite3")))
    if not sqlite_path.is_absolute():
        sqlite_path = APP_DATA_DIR / sqlite_path
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": sqlite_path}}

# إعدادات تحديثات ة للمرحلة 4. ستُطوّر لاحقًا في مرحلة التحديثات.
CENTRAL_LATEST_VERSION = os.getenv("CENTRAL_LATEST_VERSION", APP_VERSION)
CENTRAL_UPDATE_DOWNLOAD_URL = os.getenv("CENTRAL_UPDATE_DOWNLOAD_URL", "")
CENTRAL_UPDATE_NOTES = os.getenv("CENTRAL_UPDATE_NOTES", "")

SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "0") == "1"

# عزل جلسات الخادم المركزي عن جلسات المكاتب المحلية على 127.0.0.1.
# بدون هذا العزل قد يقرأ منفذ 9000 كوكي منفذ 8003 أو العكس.
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "training_center_central_sessionid")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "training_center_central_csrftoken")
