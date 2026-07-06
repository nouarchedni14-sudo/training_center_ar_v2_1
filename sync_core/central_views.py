import os
import json
import hashlib
import subprocess
import sys
import uuid
import time
import tempfile
import shutil
import socket
from urllib.request import urlopen
from urllib.error import URLError
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.html import escape

from .forms import CentralOfficeControlForm, CentralOfficeCreateForm, CentralOfficeUserEditForm, CentralOfficeUserProvisionForm, CentralUpdateReleaseForm, DEFAULT_FEATURE_FLAGS
from .provisioning import create_or_update_central_user, create_user_provision_event, latest_user_payloads_for_office, payload_from_user_and_cleaned
from .models import CentralOffice, CentralSyncEvent, CentralUpdateRelease, CentralUpdateCheckLog, CentralDeviceRegistration, Commune, Wilaya
from .organization import build_database_name, build_data_dir, ensure_default_organization_units
from .services import generate_sync_token, mask_token




def _developer_central_url() -> str:
    """رابط الخادم المركزي باسم جهاز المطوّر بدل IP المتغير."""
    value = (os.getenv("CENTRAL_PUBLIC_URL") or getattr(settings, "CENTRAL_PUBLIC_URL", "") or "").strip().rstrip("/")
    if value:
        return value
    host = (os.getenv("CENTRAL_HOSTNAME") or socket.gethostname() or "localhost").strip()
    return f"http://{host}:9000"


def _central_update_packages_root() -> Path:
    root = Path(getattr(settings, "APP_DATA_DIR", settings.BASE_DIR)) / "central_updates" / "packages"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_update_filename(version: str, original_name: str) -> str:
    suffix = Path(original_name or "").suffix.lower() or ".zip"
    cleaned_version = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in str(version or "update"))[:80] or "update"
    return f"update_{cleaned_version}{suffix}"


def _save_central_update_package(update: CentralUpdateRelease, uploaded_file) -> None:
    if not uploaded_file:
        return
    package_dir = _central_update_packages_root() / str(update.pk)
    if package_dir.exists():
        shutil.rmtree(package_dir, ignore_errors=True)
    package_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_update_filename(update.version, getattr(uploaded_file, "name", "update.zip"))
    target = package_dir / filename
    digest = hashlib.sha256()
    size = 0
    with target.open("wb") as fh:
        for chunk in uploaded_file.chunks():
            digest.update(chunk)
            size += len(chunk)
            fh.write(chunk)
    suffix = target.suffix.lower()
    update.local_package_name = f"{update.pk}/{filename}"
    update.checksum_sha256 = digest.hexdigest()
    update.file_size_bytes = size
    if suffix in {".exe", ".msi"}:
        update.update_type = CentralUpdateRelease.TYPE_INSTALLER
    else:
        update.update_type = CentralUpdateRelease.TYPE_PATCH
    update.save(update_fields=["local_package_name", "checksum_sha256", "file_size_bytes", "update_type", "updated_at"])

def _developer_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url="/admin/login/")(view_func)



from .office_cleanup import (
    _office_provision_user_events,
    _usernames_in_provision_events,
    _delete_central_users_if_only_linked_to_office,
    _cleanup_orphan_office_users,
    cleanup_users_for_office_delete,
)


def _page(title: str, body: str) -> HttpResponse:
    trainee_manager_url = getattr(settings, "CENTRAL_TRAINEE_MANAGER_URL", "http://127.0.0.1:8000/developer/login/")
    html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
body {{ font-family: Tahoma, Arial, sans-serif; margin: 24px; background:#f6f7fb; color:#111827; }}
a {{ color:#0f766e; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.card {{ background:white; border:1px solid #e5e7eb; border-radius:14px; padding:18px; margin:14px 0; box-shadow:0 1px 3px #0001; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; }}
.stat {{ background:#ffffff; border:1px solid #e5e7eb; border-radius:14px; padding:14px; }}
.stat b {{ display:block; font-size:28px; margin-top:6px; }}
table {{ width:100%; border-collapse:collapse; background:white; border-radius:12px; overflow:hidden; }}
th,td {{ padding:10px; border-bottom:1px solid #e5e7eb; text-align:right; vertical-align:top; }}
th {{ background:#eef2ff; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:999px; background:#e5e7eb; }}
.ok {{ background:#dcfce7; color:#166534; }}
.warn {{ background:#fef3c7; color:#92400e; }}
.bad {{ background:#fee2e2; color:#991b1b; }}
form p {{ margin:10px 0; }}
input, select, textarea {{ width:100%; max-width:760px; padding:8px; border:1px solid #d1d5db; border-radius:8px; box-sizing:border-box; }}
pre {{ direction:ltr; text-align:left; background:#111827; color:#f9fafb; padding:14px; border-radius:12px; overflow:auto; }}
.notice {{ background:#ecfdf5; border:1px solid #a7f3d0; color:#065f46; border-radius:14px; padding:14px; margin:14px 0; }}
input[type=checkbox] {{ width:auto; }}
button,.button {{ background:#0f766e; color:white; border:none; border-radius:10px; padding:9px 14px; cursor:pointer; display:inline-block; }}
.secondary {{ background:#374151; }}
.danger {{ background:#b91c1c; }}
.helptext {{ color:#6b7280; font-size:12px; display:block; }}
.errorlist {{ color:#b91c1c; }}
.nav {{ margin-bottom:16px; }}
.nav a {{ margin-left:12px; }}
.actions {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
.actions form {{ display:inline; margin:0; }}
.office-actions {{ display:grid; grid-template-columns:repeat(2, minmax(86px, 1fr)); gap:6px; align-items:stretch; min-width:190px; max-width:230px; direction:rtl; }}
.office-actions form {{ display:block; margin:0; }}
.office-actions .button,.office-actions button {{ width:100%; min-width:0; text-align:center; white-space:nowrap; box-shadow:0 1px 2px #0001; }}
.button.small, button.small {{ padding:6px 7px; font-size:11px; border-radius:8px; line-height:1.15; }}
.button.gold, button.gold {{ background:#a77d24; }}
.button.blue, button.blue {{ background:#2563eb; }}
.button.teal, button.teal {{ background:#0f766e; }}
.office-table td:last-child {{ min-width:210px; }}
.office-open-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px; }}
.office-open-card {{ background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:14px; box-shadow:0 1px 3px #0001; }}
.office-open-card h3 {{ margin:0 0 8px 0; }}
.office-open-card .meta {{ color:#6b7280; font-size:13px; line-height:1.8; }}
</style>
</head>
<body>
<div class="nav">
<a href="{reverse('central_dashboard')}">لوحة المطور</a>
<a href="{reverse('central_offices')}">إدارة المكاتب</a>
<a href="{reverse('central_devices')}">طلبات ربط الأجهزة</a>
<a href="{reverse('central_office_new')}">إضافة مكتب</a>
<a href="{reverse('central_updates')}">التحديثات</a>
<a href="{reverse('central_office_user_new')}">إضافة مستخدم لمكتب</a>
<a href="{reverse('central_trainee_manager_picker')}">برنامج تسيير المتكوّنين</a>
<a href="/admin/">إدارة الخادم المركزي</a>
<a href="/api/sync/status/">API Status</a>
</div>
{body}
<script>
function openOfficeInTab(url){{
  if(!url){{ return false; }}
  var a = document.createElement('a');
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(function(){{ try{{ document.body.removeChild(a); }}catch(e){{}} }}, 1000);
  return false;
}}
</script>
</body>
</html>"""
    return HttpResponse(html)


def _normalize_local_data_dir_path(value: str) -> str:
    """Normalize office data folder paths from the central UI.

    A value like TrainingCenterData_Tissemsilt used to be interpreted relative to
    the project folder because CREATE_NEW_OFFICE.ps1 runs from BASE_DIR. For
    office data this is confusing and unsafe, so we intentionally convert simple
    relative names to C:\\<name>. Absolute paths such as C:\\TrainingCenterData
    are kept unchanged.
    """
    raw = (value or "").strip().strip('"').strip("'")
    if not raw:
        return raw
    raw = raw.replace('/', '\\')
    # Windows drive path or UNC path.
    if len(raw) >= 3 and raw[1] == ':' and raw[2] in ('\\', '/'):
        return raw.rstrip('\\/')
    if raw.startswith('\\\\'):
        return raw.rstrip('\\/')
    return ("C:\\" + raw.lstrip('\\/')).rstrip('\\/')




def _safe_local_database_name(value: str, fallback: str = "training_center_office") -> str:
    raw = (value or fallback or "training_center_office").strip().strip('"').strip("'")
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in raw)
    while "__" in safe:
        safe = safe.replace("__", "_")
    safe = safe.strip("_") or fallback
    if safe[0].isdigit():
        safe = "db_" + safe
    return safe[:60]

def _office_local_database(office: CentralOffice) -> str:
    flags = office.feature_flags or {}
    suffix = (office.office_id or "office").replace("office-", "")
    default = f"training_center_{''.join(ch if ch.isalnum() else '_' for ch in suffix).strip('_') or 'office'}"
    return _safe_local_database_name(flags.get("local_database") or default, default)

def _read_env_value(path: str, key: str, default: str = "") -> str:
    try:
        if not os.path.exists(path):
            return default
        prefix = key + "="
        value = default
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            for line in fh:
                if line.startswith(prefix):
                    value = line[len(prefix):].strip()
        return value
    except Exception:
        return default

def _postgres_tools_from_central_env() -> tuple[str, str, str]:
    env_path = os.environ.get("ENV_FILE_PATH") or r"C:\TrainingCenterCentralData\.env"
    pg_user = _read_env_value(env_path, "POSTGRES_USER", os.environ.get("POSTGRES_USER", "postgres"))
    pg_password = _read_env_value(env_path, "POSTGRES_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "123456"))
    psql = r"C:\Program Files\PostgreSQL\16\bin\psql.exe"
    if not os.path.exists(psql):
        psql = "psql"
    return psql, pg_user, pg_password

def _drop_local_database_if_exists(database: str) -> tuple[bool, str]:
    database = _safe_local_database_name(database)
    psql, pg_user, pg_password = _postgres_tools_from_central_env()
    env = os.environ.copy()
    env["PGPASSWORD"] = pg_password
    sql = (
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{database}' AND pid <> pg_backend_pid(); "
        f"DROP DATABASE IF EXISTS {database};"
    )
    try:
        result = subprocess.run([psql, "-U", pg_user, "-d", "postgres", "-c", sql], cwd=str(getattr(settings, "BASE_DIR", os.getcwd())), env=env, capture_output=True, text=True, timeout=120)
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        return result.returncode == 0, output.strip()
    except Exception as exc:
        return False, f"تعذر حذف قاعدة البيانات {database}: {exc}"

def _delete_file_or_folder(path: str) -> tuple[bool, str]:
    path = (path or "").strip()
    if not path:
        return True, ""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=False)
            return True, f"تم حذف المجلد: {path}"
        if os.path.exists(path):
            os.remove(path)
            return True, f"تم حذف الملف: {path}"
        return True, f"غير موجود: {path}"
    except Exception as exc:
        return False, f"فشل حذف {path}: {exc}"

def _office_safe_suffix(office_or_id) -> str:
    """Suffix ثابت وآمن لاستعماله في أسماء الملفات والمجلدات."""
    value = getattr(office_or_id, "office_id", office_or_id) or "office"
    value = str(value).replace("office-", "")
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in value).strip("-_")
    return safe or "office"


def _generated_office_scripts_dir() -> str:
    """مجلد واحد مرتب لملفات تشغيل المكاتب المولدة تلقائيًا."""
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    return os.path.join(base_dir, "generated_office_scripts")


def _generated_office_script_paths(office: CentralOffice, port: int | None = None) -> tuple[str, str]:
    port = int(port or _office_local_port(office))
    safe = _office_safe_suffix(office).upper()
    scripts_dir = _generated_office_scripts_dir()
    return (
        os.path.join(scripts_dir, f"START_OFFICE_{safe}_{port}.bat"),
        os.path.join(scripts_dir, f"START_SYNC_{safe}_ONCE.bat"),
    )


def _safe_windows_folder_name(value: str, fallback: str = "office") -> str:
    """اسم مجلد آمن داخل المشروع، مع الحفاظ على العربية."""
    raw = (value or fallback or "office").strip().strip('"').strip("'")
    for ch in '<>:"/\\|?*':
        raw = raw.replace(ch, "_")
    raw = " ".join(raw.split()).strip(" ._")
    return raw or fallback or "office"


def _office_project_shortcuts_dir(office: CentralOffice) -> str:
    """مجلد روابط تشغيل المكتب داخل مسار المشروع نفسه."""
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    office_label = office.office_name or office.office_id or _office_safe_suffix(office)
    folder_name = _safe_windows_folder_name(office_label, _office_safe_suffix(office))
    return os.path.join(base_dir, "مكاتب_التشغيل", folder_name)


def _write_office_project_shortcuts(office: CentralOffice) -> None:
    """ينشئ مجلد المكتب داخل المشروع وفيه ملف تشغيل ورابط المكتب.

    يتم استدعاؤه عند فتح المكتب من لوحة المطور، لذلك حتى لو حُذفت الروابط
    سيعيد النظام إنشاءها تلقائيًا.
    """
    try:
        base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
        env_path = _office_local_env_path(office)
        app_data_dir = os.path.dirname(env_path.rstrip("\\/"))
        port = int(_office_local_port(office))
        public_url = f"http://127.0.0.1:{port}/"
        dev_url = f"http://127.0.0.1:{port}/developer/login/"
        folder = _office_project_shortcuts_dir(office)
        os.makedirs(folder, exist_ok=True)

        start_bat = os.path.join(folder, "تشغيل_المكتب.bat")
        sync_bat = os.path.join(folder, "مزامنة_المكتب_مرة_واحدة.bat")
        url_file = os.path.join(folder, "رابط_المكتب.url")
        txt_file = os.path.join(folder, "رابط_المكتب.txt")

        office_name = office.office_name or office.office_id or "Office"
        start_lines = [
            "@echo off",
            "chcp 65001 >nul",
            f"cd /d \"{base_dir}\"",
            f"set \"ENV_FILE_PATH={env_path}\"",
            f"set \"APP_DATA_DIR={app_data_dir}\"",
            "set \"AUTO_OPEN_BROWSER=1\"",
            f"set \"AUTO_OPEN_BROWSER_URL={public_url}\"",
            "set \"PREFER_CHROME_BROWSER=1\"",
            "echo ==========================================",
            f"echo Starting {office_name} on port {port}",
            "echo ENV_FILE_PATH=%ENV_FILE_PATH%",
            "echo APP_DATA_DIR=%APP_DATA_DIR%",
            f"echo URL: {public_url}",
            "echo ==========================================",
            "\".venv\\Scripts\\python.exe\" launcher\\lan_server.py",
            "pause",
            "",
        ]
        sync_lines = [
            "@echo off",
            "chcp 65001 >nul",
            f"cd /d \"{base_dir}\"",
            f"set \"ENV_FILE_PATH={env_path}\"",
            f"set \"APP_DATA_DIR={app_data_dir}\"",
            "echo ==========================================",
            f"echo Sync {office_name} once",
            "echo ENV_FILE_PATH=%ENV_FILE_PATH%",
            "echo APP_DATA_DIR=%APP_DATA_DIR%",
            "echo ==========================================",
            "\".venv\\Scripts\\python.exe\" manage.py sync_worker --once --settings=training_center.settings_lan",
            "pause",
            "",
        ]
        Path(start_bat).write_text("\r\n".join(start_lines), encoding="utf-8-sig")
        Path(sync_bat).write_text("\r\n".join(sync_lines), encoding="utf-8-sig")
        Path(url_file).write_text(f"[InternetShortcut]\r\nURL={public_url}\r\n", encoding="utf-8")
        Path(txt_file).write_text(
            f"الكود الرسمي للمؤسسة:\r\n{office.office_code or office.office_id}\r\n\r\n"
            f"الاسم الرسمي:\r\n{office.office_display_name or office.office_name or office.office_id}\r\n\r\n"
            f"رابط دخول المكتب:\r\n{public_url}\r\n\r\n"
            f"رابط دخول المطور إلى المكتب:\r\n{dev_url}\r\n\r\n"
            f"ملف الإعدادات:\r\n{env_path}\r\n",
            encoding="utf-8-sig",
        )
    except Exception:
        return


def _office_local_env_path(office: CentralOffice) -> str:
    """مسار .env الخاص بمكتب محلي على جهاز المطور.

    لا نعتمد على أسماء ثابتة مثل وهران/مستغانم؛ كل مكتب يأخذ مساره من feature_flags.
    إذا لم يوجد مسار محفوظ، يتم اشتقاق مسار مرتب من Office ID داخل C:\\TrainingCenterData_<suffix>.
    """
    flags = office.feature_flags or {}
    custom = (flags.get("env_file_path") or flags.get("local_env_path") or "").strip()
    if custom:
        custom = custom.replace('/', '\\')
        if custom.lower().endswith('\\.env'):
            folder = custom[:-5]
            return _normalize_local_data_dir_path(folder) + r"\.env"
        if custom.lower().endswith('.env'):
            return custom
        return _normalize_local_data_dir_path(custom) + r"\.env"

    safe_id = _office_safe_suffix(office)
    return rf"C:\TrainingCenterData_{safe_id}\.env"


def _write_env_values(path: str, updates: dict[str, str]) -> None:
    """تحديث مفاتيح داخل ملف .env مع الحفاظ على باقي الأسطر قدر الإمكان."""
    if not path:
        return
    env_path = Path(path)
    try:
        lines = env_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines() if env_path.exists() else []
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
        missing = [key for key in updates if key not in seen]
        if missing and new_lines and new_lines[-1].strip():
            new_lines.append("")
        for key in missing:
            new_lines.append(f"{key}={updates[key]}")
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    except Exception:
        # لا نوقف فتح المكتب بسبب فشل تحديث ملف .env؛ سيُظهر التشغيل خطأه إن وُجد.
        return


def _central_developer_credentials() -> dict[str, str]:
    """قراءة حساب المطور من بيئة الخادم المركزي لتمكينه داخل المكتب عند الفتح من لوحة المطور."""
    username = (os.getenv("DEV_USERNAME", "") or "").strip()
    password = os.getenv("DEV_PASSWORD", "") or ""
    email = (os.getenv("DEV_EMAIL", "") or "").strip()
    if not username or not password:
        return {}
    return {
        "DEV_LOGIN_ENABLED": "1",
        "DEV_USERNAME": username,
        "DEV_PASSWORD": password,
        "DEV_EMAIL": email,
        "CENTRAL_DASHBOARD_URL": _developer_central_url().rstrip("/") + "/central/",
    }


def _sync_developer_login_to_office_env(office: CentralOffice) -> None:
    """يجعل مكتب المطور المحلي يقبل حساب المطور عند فتحه من لوحة 9000.

    صفحة http://127.0.0.1:PORT/ تبقى دائمًا صفحة دخول المستخدمين العاديين،
    أما المطور فيدخل من /developer/login/.
    """
    updates = _central_developer_credentials()
    if not updates:
        return
    _write_env_values(_office_local_env_path(office), updates)


def _office_local_port(office: CentralOffice) -> int:
    """منفذ المكتب المحلي من feature_flags أولًا، ثم 8003 كافتراضي.

    ألغينا التخمين حسب اسم المكتب حتى لا يحدث خلط بين وهران/تيسمسيلت/مستغانم.
    """
    flags = office.feature_flags or {}
    try:
        port = int(flags.get("local_port") or 0)
        if port:
            return port
    except Exception:
        pass
    return 8003


def _office_developer_url(office: CentralOffice) -> str:
    """رابط دخول المطوّر إلى مكتب محدد من جهاز المطوّر الرئيسي فقط.

    ملاحظة مهمة:
    - إذا فُتح المكتب من لوحة المطوّر المركزية يجب أن يذهب إلى /developer/login/.
    - أما فتح http://127.0.0.1:8003/ مباشرة فيبقى صفحة دخول المستخدمين العاديين.
    لذلك حتى لو كان داخل إعدادات المكتب رابط مخصص للصفحة الرئيسية فقط، نضيف له
    /developer/login/ تلقائيًا ما لم يكن يحتويها أصلًا.
    """
    flags = office.feature_flags or {}
    custom = (flags.get("developer_url") or flags.get("local_developer_url") or "").strip()
    if custom:
        if "/developer/login" in custom.rstrip("/"):
            return custom
        return custom.rstrip("/") + "/developer/login/"
    port = _office_local_port(office)
    return f"http://127.0.0.1:{port}/developer/login/"


def _office_local_public_url(office: CentralOffice) -> str:
    """رابط اختبار جاهزية المكتب محليًا من جهاز المطور."""
    flags = office.feature_flags or {}
    custom = (flags.get("local_public_url") or flags.get("public_url") or "").strip()
    if custom:
        return custom.rstrip("/")
    return f"http://127.0.0.1:{_office_local_port(office)}"


def _office_start_bat_path(office: CentralOffice) -> str:
    """مسار ملف تشغيل المكتب المولد آليًا داخل generated_office_scripts.

    لا نستعمل ملفات START_OFFICE القديمة الموجودة في جذر المشروع لأنها تسبب خلطًا وتكرار CMD.
    """
    flags = office.feature_flags or {}
    bat = (flags.get("start_office_bat") or "").strip()
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    if bat:
        return bat if os.path.isabs(bat) else os.path.join(base_dir, bat)
    return _generated_office_script_paths(office)[0]


def _office_sync_bat_path(office: CentralOffice) -> str:
    flags = office.feature_flags or {}
    bat = (flags.get("start_sync_bat") or "").strip()
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    if bat:
        return bat if os.path.isabs(bat) else os.path.join(base_dir, bat)
    return _generated_office_script_paths(office)[1]


def _office_is_running(office: CentralOffice, timeout: float = 1.2) -> bool:
    url = _office_local_public_url(office).rstrip("/") + "/readyz/"
    try:
        with urlopen(url, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 500
    except Exception:
        # جرّب الصفحة الرئيسية إذا لم يوجد readyz لسبب ما
        try:
            with urlopen(_office_local_public_url(office), timeout=timeout) as response:
                return 200 <= getattr(response, "status", 200) < 500
        except Exception:
            return False

def _pids_listening_on_port(port: int) -> list[int]:
    """يعيد PIDs التي تستمع على منفذ مكتب محلي معين."""
    try:
        port = int(port)
    except Exception:
        return []

    if port <= 0:
        return []

    pids: set[int] = set()

    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            for raw in output.splitlines():
                line = raw.strip()
                if not line.upper().startswith("TCP"):
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                local_addr = parts[1]
                state = parts[-2].upper()
                pid_text = parts[-1]
                if state != "LISTENING":
                    continue
                if not local_addr.rsplit(":", 1)[-1] == str(port):
                    continue
                try:
                    pid = int(pid_text)
                    if pid > 0:
                        pids.add(pid)
                except Exception:
                    continue
        except Exception:
            return []
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            for item in (result.stdout or "").split():
                try:
                    pid = int(item.strip())
                    if pid > 0:
                        pids.add(pid)
                except Exception:
                    continue
        except Exception:
            return []

    return sorted(pids)


def _stop_office_server(office: CentralOffice) -> tuple[bool, str]:
    """إيقاف خادم مكتب محلي من لوحة المطور حسب المنفذ فقط.

    لا نحاول إيقاف المنفذ 9000 لأنه خاص بلوحة المطور المركزية.
    """
    port = int(_office_local_port(office))
    if port == 9000:
        return False, "لا يمكن إيقاف منفذ لوحة المطور 9000 من زر إيقاف المكاتب."

    pids = _pids_listening_on_port(port)
    if not pids:
        return True, f"المكتب غير شغال حاليًا على المنفذ {port}."

    killed: list[int] = []
    errors: list[str] = []
    for pid in pids:
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            else:
                result = subprocess.run(
                    ["kill", "-TERM", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            if result.returncode == 0:
                killed.append(pid)
            else:
                output = ((result.stdout or "") + " " + (result.stderr or "")).strip()
                errors.append(f"PID {pid}: {output or 'فشل الإيقاف'}")
        except Exception as exc:
            errors.append(f"PID {pid}: {exc}")

    # مهلة قصيرة حتى يتحرر المنفذ.
    for _ in range(10):
        time.sleep(0.3)
        if not _pids_listening_on_port(port):
            break

    remaining = _pids_listening_on_port(port)
    if remaining:
        msg = f"تمت محاولة إيقاف المكتب على المنفذ {port}، لكن ما زال يعمل PID: {', '.join(map(str, remaining))}."
        if errors:
            msg += "\n" + "\n".join(errors[-5:])
        return False, msg

    if killed:
        return True, f"تم إيقاف المكتب على المنفذ {port}. PID: {', '.join(map(str, killed))}."
    return True, f"تم إيقاف المكتب على المنفذ {port}."



def _start_office_server(office: CentralOffice) -> tuple[bool, str]:
    """يشغل خادم المكتب المحلي مباشرة من .env الصحيح بدون الاعتماد على BAT قديم.

    هذا يمنع:
    - تشغيل مكتب خاطئ بسبب ملف START_OFFICE قديم.
    - فتح نافذتي CMD.
    - فتح تبويبين في المتصفح.
    """
    # أنشئ/حدّث دائمًا مجلد روابط المكتب داخل المشروع.
    _write_office_project_shortcuts(office)

    # قبل الفتح من لوحة 9000 نضمن أن مكتب جهاز المطور يعرف حساب المطور.
    # هذا لا يغيّر صفحة الدخول العادية للمكتب: / تبقى للمستخدمين، و /developer/login/ للمطور.
    _sync_developer_login_to_office_env(office)

    if _office_is_running(office):
        return True, "المكتب يعمل مسبقًا. إذا لم تقبل صفحة دخول المطور الحساب بعد، أعد تشغيل خادم هذا المكتب مرة واحدة."

    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    env_path = _office_local_env_path(office)
    if not os.path.exists(env_path):
        return False, f"لم يتم العثور على ملف إعدادات المكتب: {env_path}. افتح تحكم المكتب واضغط تجهيز/تعديل المكتب المحلي الآن."

    app_data_dir = os.path.dirname(env_path.rstrip("\\/"))
    port = _office_local_port(office)
    lock_path = os.path.join(tempfile.gettempdir(), f"training_center_start_office_{office.pk}_{port}.lock")

    try:
        if os.path.exists(lock_path) and (time.time() - os.path.getmtime(lock_path)) < 60:
            for _ in range(30):
                time.sleep(0.5)
                if _office_is_running(office, timeout=0.6):
                    return True, "كان خادم المكتب قيد التشغيل وأصبح جاهزًا."
            return True, "خادم المكتب قيد التشغيل بالفعل، انتظر ثواني قليلة ثم أعد فتح الصفحة."
        with open(lock_path, "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except Exception:
        pass

    env = os.environ.copy()
    env["ENV_FILE_PATH"] = env_path
    env["APP_DATA_DIR"] = app_data_dir
    env["AUTO_OPEN_BROWSER"] = "0"
    env["AUTO_OPEN_BROWSER_URL"] = ""
    env["OPENED_FROM_CENTRAL"] = "1"
    for key, value in _central_developer_credentials().items():
        env[key] = value

    # pythonw على Windows يمنع ظهور نافذة سوداء. إن لم يوجد نستعمل Python الحالي مع إخفاء النافذة.
    python_exe = sys.executable
    if sys.platform == "win32":
        candidate = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(candidate):
            python_exe = candidate
    launcher_path = os.path.join("launcher", "lan_server.py")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            [python_exe, launcher_path],
            cwd=base_dir,
            env=env,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        msg = f"تم تشغيل المكتب مباشرة من ملف الإعدادات: {env_path}"
    except Exception as exc:
        try:
            os.remove(lock_path)
        except Exception:
            pass
        return False, f"تعذر تشغيل خادم المكتب: {exc}"

    for _ in range(30):
        time.sleep(0.5)
        if _office_is_running(office, timeout=0.6):
            try:
                os.remove(lock_path)
            except Exception:
                pass
            return True, msg + "، وأصبح جاهزًا."
    try:
        os.remove(lock_path)
    except Exception:
        pass
    return True, msg + "، لكن قد يحتاج ثواني إضافية حتى يفتح."


def _pull_office_audit_once(office: CentralOffice) -> tuple[bool, str]:
    """يسحب سجلات التدقيق من خادم مكتب موجود على جهاز/شبكة أخرى."""
    if not (office.office_api_url or "").strip():
        return False, "لم يتم ضبط رابط خادم المكتب للسحب office_api_url. ضع مثلًا: http://192.168.1.20:8000"
    try:
        from io import StringIO
        out = StringIO()
        call_command("pull_office_audit", "--office-id", office.office_id, stdout=out)
        return True, out.getvalue().strip()[-1000:] or "تم سحب السجلات."
    except Exception as exc:
        return False, f"فشل سحب السجلات: {exc}"


def _run_office_sync_once(office: CentralOffice) -> tuple[bool, str]:
    """يشغل sync_worker --once للمكتب من لوحة المطور المركزية.

    هذا يعمل عندما يكون خادم المكتب المحلي موجودًا على نفس جهاز المطور.
    إذا كان المكتب على جهاز آخر، الأفضل لاحقًا تشغيل المزامنة عبر Task Scheduler داخل ذلك الجهاز.
    """
    env_path = _office_local_env_path(office)
    if not os.path.exists(env_path):
        return False, f"لم يتم العثور على ملف إعدادات المكتب: {env_path}"

    app_data_dir = os.path.dirname(env_path.rstrip("\\/"))
    env = os.environ.copy()
    env["ENV_FILE_PATH"] = env_path
    env["APP_DATA_DIR"] = app_data_dir

    cmd = [sys.executable, "manage.py", "sync_worker", "--once", "--settings=training_center.settings_lan"]
    try:
        result = subprocess.run(
            cmd,
            cwd=getattr(settings, "BASE_DIR", os.getcwd()),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception as exc:
        return False, f"تعذر تشغيل المزامنة: {exc}"

    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    output = output.strip()
    if result.returncode == 0:
        return True, output or "تم تنفيذ المزامنة بنجاح."
    return False, output or f"فشل أمر المزامنة برمز خروج {result.returncode}."


def _run_office_auto_setup(office: CentralOffice, *, port: int, database: str, data_dir: str, token: str) -> tuple[bool, str]:
    """يشغل CREATE_NEW_OFFICE.ps1 لتجهيز مكتب جديد كاملًا على نفس جهاز المطور."""
    base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
    script_path = os.path.join(base_dir, "CREATE_NEW_OFFICE.ps1")
    if not os.path.exists(script_path):
        return False, f"لم يتم العثور على السكريبت: {script_path}"

    database = _safe_local_database_name(database, f"training_center_{(office.office_id or 'office').replace('office-', '').replace('-', '_')}")
    data_dir = _normalize_local_data_dir_path(data_dir)
    shell = "powershell.exe"
    if sys.platform != "win32":
        shell = "pwsh"
    cmd = [
        shell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script_path,
        "-OfficeName", office.office_name or office.office_id,
        "-OfficeId", office.office_id,
        "-ServerId", office.server_id,
        "-Port", str(port),
        "-Database", database,
        "-DataDir", data_dir,
        "-SyncToken", token,
        "-CentralUrl", _developer_central_url(),
        "-WilayaCode", office.wilaya.code if office.wilaya_id else "",
        "-CommuneCode", office.commune.code if office.commune_id else "",
        "-OfficeCode", office.office_code or "",
        "-OfficeAlias", office.office_alias or "",
        "-OfficeDisplayName", office.office_display_name or office.office_name or "",
        "-EstablishmentType", office.establishment_type or "",
        "-EstablishmentNumber", office.establishment_number or "",
        "-SkipCentralRegister",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except Exception as exc:
        return False, f"تعذر تشغيل سكريبت تجهيز المكتب: {exc}"

    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    output = output.strip()
    return result.returncode == 0, output or f"انتهى السكريبت برمز خروج {result.returncode}."


def _status_badge(office: CentralOffice) -> str:
    if not office.is_active:
        return '<span class="badge bad">معطل</span>'
    if office.is_license_expired:
        return '<span class="badge bad">الترخيص منتهي</span>'
    if office.license_status == CentralOffice.LICENSE_SUSPENDED:
        return '<span class="badge bad">موقوف</span>'
    if office.license_status == CentralOffice.LICENSE_TRIAL:
        return '<span class="badge warn"></span>'
    return '<span class="badge ok">نشط</span>'


@_developer_required
def central_dashboard(request):
    total_offices = CentralOffice.objects.count()
    active_offices = CentralOffice.objects.filter(is_active=True).count()
    disabled_offices = CentralOffice.objects.filter(Q(is_active=False) | Q(license_status=CentralOffice.LICENSE_SUSPENDED)).count()
    total_events = CentralSyncEvent.objects.count()
    active_updates = CentralUpdateRelease.objects.filter(is_active=True).count()
    update_checks = CentralUpdateCheckLog.objects.count()
    pending_devices = CentralDeviceRegistration.objects.filter(status=CentralDeviceRegistration.STATUS_PENDING).count()
    recent_events = CentralSyncEvent.objects.order_by("-id")[:10]
    recent_rows = "".join(
        f"<tr><td>#{e.id}</td><td>{escape(e.source_office_id)}</td><td>{escape(e.operation)}</td><td>{escape(e.app_label)}.{escape(e.model_name)}</td><td>{escape(str(e.object_pk))}</td><td>{e.received_at:%Y-%m-%d %H:%M}</td></tr>"
        for e in recent_events
    ) or '<tr><td colspan="6">لا توجد أحداث بعد</td></tr>'
    body = f"""
<h1>لوحة المطور المركزية</h1>
<div class="notice"><b>هذه هي واجهة المطور الرئيسية.</b> الخادم المركزي يعمل عادة على المنفذ 9000، أما المنافذ 8000 و8002 فهي مكاتب محلية للتجربة أو للعمل داخل كل مكتب.</div>
<div class="grid">
<div class="stat">عدد المكاتب<b>{total_offices}</b></div>
<div class="stat">المكاتب المفعلة<b>{active_offices}</b></div>
<div class="stat">المكاتب المعطلة/الموقوفة<b>{disabled_offices}</b></div>
<div class="stat">أحداث المزامنة<b>{total_events}</b></div>
<div class="stat">التحديثات المنشورة<b>{active_updates}</b></div>
<div class="stat">فحوصات التحديث<b>{update_checks}</b></div>
<div class="stat">أجهزة تنتظر الربط<b>{pending_devices}</b></div>
</div>
<div class="card">
<h2>خطوات العمل الصحيحة</h2>
<ol>
<li>أنشئ المكاتب من <b>إدارة المكاتب</b> أو زر <b>إضافة مكتب</b>.</li>
<li>انسخ القيم الناتجة إلى ملف .env الخاص بالمكتب المحلي.</li>
<li>شغّل خادم المكتب المحلي، ثم شغّل عامل المزامنة.</li>
<li>إدارة التراخيص والتحديثات تتم من هنا. ولإدارة المتكوّنين والمستخدمين داخل المكتب اضغط زر برنامج تسيير المتكوّنين.</li>
</ol>
</div>
<div class="card">
<h2>أحدث أحداث المزامنة</h2>
<table>
<tr><th>المؤشر</th><th>المكتب</th><th>العملية</th><th>النموذج</th><th>السجل</th><th>وقت الوصول</th></tr>
{recent_rows}
</table>
</div>
"""
    return _page("لوحة المطور المركزية", body)


@_developer_required
def central_devices(request):
    msg_html = "".join(f'<div class="card">{escape(m.message)}</div>' for m in messages.get_messages(request))
    devices = CentralDeviceRegistration.objects.select_related("assigned_office").order_by("status", "-requested_at")
    offices = list(CentralOffice.objects.filter(is_active=True).order_by("office_id"))
    office_options = "".join(f'<option value="{o.pk}">{escape(o.office_name or o.office_id)} - {escape(o.office_id)}</option>' for o in offices)
    rows = []
    for d in devices:
        badge_class = "warn" if d.status == CentralDeviceRegistration.STATUS_PENDING else ("ok" if d.status == CentralDeviceRegistration.STATUS_APPROVED else "bad")
        assigned = d.assigned_office.office_name if d.assigned_office else "-"
        if d.status == CentralDeviceRegistration.STATUS_PENDING:
            actions = f'''
<form method="post" action="{reverse('central_device_approve', args=[d.pk])}">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<select name="office_id" required>
<option value="">اختر المكتب...</option>
{office_options}
</select>
<button class="teal small" type="submit">اعتماد الجهاز</button>
</form>
<form method="post" action="{reverse('central_device_reject', args=[d.pk])}">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="danger small" type="submit">رفض</button>
</form>
'''
        else:
            revoke_label = "إلغاء الاعتماد" if d.status == CentralDeviceRegistration.STATUS_APPROVED else "إرجاع إلى الانتظار"
            actions = f'''
<div class="actions">
<span>{escape(assigned)}</span>
<form method="post" action="{reverse('central_device_reject', args=[d.pk])}">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="secondary small" type="submit">{revoke_label}</button>
</form>
<form method="post" action="{reverse('central_device_delete', args=[d.pk])}" onsubmit="return confirm('هل تريد حذف طلب/جهاز الربط هذا من الخادم المركزي؟ لن يحذف البرنامج من الجهاز نفسه.');">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="danger small" type="submit">حذف الجهاز</button>
</form>
</div>
'''
        rows.append(f'''
<tr>
<td><b>{escape(d.hostname or d.device_label or d.server_id)}</b><br><small dir="ltr">{escape(d.server_id)}</small></td>
<td>{escape(str(d.lan_ip or '-'))}</td>
<td>{escape(d.app_version or '-')}</td>
<td><span class="badge {badge_class}">{escape(d.get_status_display())}</span></td>
<td>{escape(assigned)}</td>
<td>{escape(str(d.requested_at or '-'))}<br><small>آخر اتصال: {escape(str(d.last_seen_at or '-'))}</small></td>
<td>{actions}</td>
</tr>
''')
    body = f'''
<h1>طلبات ربط الأجهزة</h1>
{msg_html}
<div class="notice">
ثبّت البرنامج على الجهاز الآخر ثم شغّله. سيظهر الجهاز هنا بدون SYNC_TOKEN. اختر المكتب واضغط <b>اعتماد الجهاز</b>، وبعدها يحصل الجهاز تلقائيًا على OFFICE_ID و SYNC_TOKEN ويبدأ بالمزامنة.
</div>
<table>
<tr><th>الجهاز</th><th>IP</th><th>النسخة</th><th>الحالة</th><th>المكتب</th><th>الوقت</th><th>الإجراء</th></tr>
{''.join(rows) if rows else '<tr><td colspan="7">لا توجد أجهزة تنتظر الربط حاليًا.</td></tr>'}
</table>
'''
    return _page("طلبات ربط الأجهزة", body)


@_developer_required
def central_device_approve(request, pk: int):
    if request.method != "POST":
        return redirect("central_devices")
    device = get_object_or_404(CentralDeviceRegistration, pk=pk)
    office = get_object_or_404(CentralOffice, pk=int(request.POST.get("office_id") or 0))
    device.approve_for_office(office)
    # لا نغيّر SERVER_ID الخاص بالمكتب المحلي عند اعتماد جهاز موظف.
    messages.success(request, f"تم اعتماد الجهاز {device.hostname or device.server_id} وربطه بـ {office.office_name or office.office_id}.")
    return redirect("central_devices")


@_developer_required
def central_device_reject(request, pk: int):
    if request.method != "POST":
        return redirect("central_devices")
    device = get_object_or_404(CentralDeviceRegistration, pk=pk)
    old_office = device.assigned_office
    device.status = CentralDeviceRegistration.STATUS_REJECTED
    device.assigned_office = None
    device.device_token = ""
    device.config_delivered_at = None
    device.save(update_fields=["status", "assigned_office", "device_token", "config_delivered_at"])
    # لا نمسح SERVER_ID الخاص بالمكتب عند إلغاء اعتماد جهاز موظف.
    messages.warning(request, f"تم إلغاء/رفض الجهاز {device.hostname or device.server_id}.")
    return redirect("central_devices")


@_developer_required
def central_device_delete(request, pk: int):
    if request.method != "POST":
        return redirect("central_devices")
    device = get_object_or_404(CentralDeviceRegistration, pk=pk)
    label = device.hostname or device.device_label or device.server_id
    old_office = device.assigned_office
    server_id = device.server_id
    device.delete()
    # لا نمسح SERVER_ID الخاص بالمكتب عند حذف جهاز موظف.
    messages.success(request, f"تم حذف جهاز الربط {label} من الخادم المركزي.")
    return redirect("central_devices")


@_developer_required
def central_trainee_manager_picker(request):
    """صفحة اختيار المكتب قبل فتح برنامج تسيير المتكوّنين من جهاز المطور الرئيسي."""
    offices = CentralOffice.objects.select_related("wilaya", "commune").order_by("office_code", "office_id")
    msg_html = "".join(f'<div class="card">{escape(m.message)}</div>' for m in messages.get_messages(request))
    cards = []
    option_rows = []
    for office in offices:
        port = _office_local_port(office)
        status = _status_badge(office)
        users_count = len(latest_user_payloads_for_office(office))
        open_url = reverse("central_office_open", args=[office.pk])
        stop_url = reverse("central_office_stop", args=[office.pk])
        label = f"{office.office_name or office.office_id} - {office.office_id} - منفذ {port}"
        option_rows.append(
            f'<option value="{escape(open_url)}" data-stop-url="{escape(stop_url)}">{escape(label)}</option>'
        )
        cards.append(f"""
<div class="office-open-card">
<h3>{escape(office.office_name or office.office_id)}</h3>
<div class="meta">
<b>Office ID:</b> <span dir="ltr">{escape(office.office_id)}</span><br>
<b>Server:</b> <span dir="ltr">{escape(office.server_id or '-')}</span><br>
<b>المنفذ:</b> <span dir="ltr">{port}</span><br>
<b>المستخدمون:</b> {users_count}<br>
<b>الحالة:</b> {status}
</div>
</div>
""")
    csrf_token = get_token(request)
    body = f"""
<h1>اختيار مكتب لفتح برنامج تسيير المتكوّنين</h1>
<div class="notice">
اختر المكتب الذي تريد تشغيله أو إيقافه من القائمة. زر <b>تشغيل المكتب</b> يشغل المكتب المختار ويفتح صفحة دخول المطور في تبويب جديد داخل نفس Chrome. زر <b>إيقاف المكتب</b> لا يعمل حتى تختار مكتبًا أولًا.
</div>
{msg_html}
<div class="card">
<form method="get" onsubmit="return false;">
<input type="hidden" id="office-csrf" value="{csrf_token}">
<label for="office-select"><b>اختيار سريع:</b></label>
<select id="office-select">
<option value="">اختر مكتبًا...</option>
{''.join(option_rows)}
</select>
<div class="actions" style="margin-top:10px">
<button class="button" type="button" onclick="return startSelectedOffice();">تشغيل المكتب</button>
<button class="danger" type="button" onclick="return stopSelectedOffice();">إيقاف المكتب</button>
</div>
</form>
</div>
<div class="office-open-grid">
{''.join(cards) if cards else '<div class="card">لا توجد مكاتب بعد.</div>'}
</div>
<script>
function selectedOfficeOption(){{
  var s = document.getElementById('office-select');
  if(!s || !s.value){{
    alert('الرجاء اختيار مكتب أولًا.');
    return null;
  }}
  return s.options[s.selectedIndex];
}}
function startSelectedOffice(){{
  var opt = selectedOfficeOption();
  if(!opt){{ return false; }}
  return openOfficeInTab(opt.value);
}}
function stopSelectedOffice(){{
  var opt = selectedOfficeOption();
  if(!opt){{ return false; }}
  var stopUrl = opt.getAttribute('data-stop-url');
  if(!stopUrl){{
    alert('تعذر تحديد رابط إيقاف المكتب المختار.');
    return false;
  }}
  if(!confirm('هل تريد إيقاف المكتب المختار الآن؟')){{ return false; }}
  var form = document.createElement('form');
  form.method = 'post';
  form.action = stopUrl;
  var csrf = document.createElement('input');
  csrf.type = 'hidden';
  csrf.name = 'csrfmiddlewaretoken';
  csrf.value = document.getElementById('office-csrf').value;
  form.appendChild(csrf);
  document.body.appendChild(form);
  form.submit();
  return false;
}}
</script>
"""
    return _page("اختيار مكتب", body)


@_developer_required
def central_office_open(request, pk: int):
    """تشغيل/تجهيز المكتب المحلي عند الحاجة ثم فتحه للمطور."""
    office = get_object_or_404(CentralOffice, pk=pk)

    # إذا كان المكتب لم يُجهز محليًا بعد، جهزه تلقائيًا عند أول فتح من لوحة 9000.
    env_path = _office_local_env_path(office)
    if not os.path.exists(env_path):
        flags = office.feature_flags or {}
        port = int(_office_local_port(office))
        data_dir = _normalize_local_data_dir_path(flags.get("local_data_dir") or os.path.dirname(env_path) or rf"C:\TrainingCenterData_{_office_safe_suffix(office)}")
        database = _office_local_database(office)
        token = office.sync_token or generate_sync_token()
        if not office.sync_token:
            office.sync_token = token
            office.save(update_fields=["sync_token", "updated_at"])

        ok_setup, setup_output = _run_office_auto_setup(
            office,
            port=port,
            database=database,
            data_dir=data_dir,
            token=token,
        )
        flags = office.feature_flags or {}
        flags.update({
            "env_file_path": rf"{data_dir}\.env",
            "local_data_dir": data_dir,
            "local_database": database,
            "local_port": port,
            "start_office_bat": os.path.relpath(_generated_office_script_paths(office, port)[0], str(getattr(settings, "BASE_DIR", os.getcwd()))),
            "start_sync_bat": os.path.relpath(_generated_office_script_paths(office, port)[1], str(getattr(settings, "BASE_DIR", os.getcwd()))),
            "last_local_setup_output": (setup_output or "")[-4000:],
            "last_local_setup_ok": ok_setup,
        })
        office.feature_flags = flags
        office.save(update_fields=["feature_flags", "updated_at"])
        if not ok_setup:
            messages.error(request, "فشل تجهيز المكتب المحلي تلقائيًا عند الفتح. راجع مخرجات التجهيز من صفحة تحكم المكتب.\n" + (setup_output or "")[-1500:])
            return redirect("central_trainee_manager_picker")
        messages.success(request, "تم تجهيز ملفات المكتب المحلي تلقائيًا لأول مرة.")

    # حتى إذا كان المكتب مجهزًا سابقًا، أعد إنشاء مجلد الروابط داخل المشروع عند كل فتح.
    _write_office_project_shortcuts(office)

    ok, message = _start_office_server(office)
    if ok:
        messages.success(request, message)
        return redirect(_office_developer_url(office))
    messages.error(request, message)
    return redirect("central_trainee_manager_picker")


@_developer_required
def central_office_stop(request, pk: int):
    """إيقاف خادم مكتب محلي من لوحة المطور."""
    if request.method != "POST":
        return redirect("central_trainee_manager_picker")

    office = get_object_or_404(CentralOffice, pk=pk)
    ok, message = _stop_office_server(office)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect(request.META.get("HTTP_REFERER") or reverse("central_trainee_manager_picker"))


@_developer_required
def central_offices_stop_all(request):
    """إيقاف كل خوادم المكاتب المحلية المعروفة من لوحة المطور."""
    if request.method != "POST":
        return redirect("central_offices")

    offices = list(CentralOffice.objects.order_by("office_id"))
    stopped: list[str] = []
    failed: list[str] = []
    for office in offices:
        ok, message = _stop_office_server(office)
        label = office.office_name or office.office_id
        if ok:
            stopped.append(f"{label}: {message}")
        else:
            failed.append(f"{label}: {message}")

    if stopped:
        messages.success(request, "تمت محاولة إيقاف المكاتب:\n" + "\n".join(stopped[-12:]))
    if failed:
        messages.error(request, "تعذر إيقاف بعض المكاتب:\n" + "\n".join(failed[-8:]))
    if not stopped and not failed:
        messages.info(request, "لا توجد مكاتب لإيقافها.")
    return redirect(request.META.get("HTTP_REFERER") or reverse("central_offices"))


@_developer_required
def central_offices(request):
    msg_html = "".join(f'<div class="card">{escape(m.message)}</div>' for m in messages.get_messages(request))
    offices = CentralOffice.objects.order_by("office_id")
    rows = []
    for office in offices:
        users_count = len(latest_user_payloads_for_office(office))
        rows.append(f"""
<tr>
<td><span dir="ltr">{escape(office.office_code or office.office_id)}</span><br><small>{escape(office.office_display_name or office.office_name or "")}</small><br><small dir="ltr">{escape(office.office_id)}</small></td>
<td>{escape(office.server_id or "-")}</td>
<td>{_status_badge(office)}</td>
<td>{escape(str(office.license_expires_at or "-"))}</td>
<td>{office.max_users}</td>
<td>{users_count}</td>
<td>{escape(str(office.last_seen_at or "-"))}<br><small>آخر سحب: {escape(str(office.last_pull_at or "-"))}</small></td>
<td>
<div class="office-actions">
<a class="button small" href="{reverse('central_office_edit', args=[office.pk])}">تعديل المكتب</a>
<a class="button secondary small" href="{reverse('central_office_edit', args=[office.pk])}#control">تحكم</a>
<a class="button secondary small" href="{reverse('central_office_users', args=[office.pk])}">تعديل المستخدمين</a>
<a class="button danger small" href="{reverse('central_office_delete', args=[office.pk])}">حذف المكتب</a>
<a class="button danger small" href="{reverse('central_office_root_delete', args=[office.pk])}">حذف من الجذور</a>
<form method="post" action="{reverse('central_office_sync_now', args=[office.pk])}">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="gold small" type="submit" title="تشغيل مزامنة هذا المكتب الآن">مزامنة الآن</button>
</form>
<form method="post" action="{reverse('central_office_stop', args=[office.pk])}" onsubmit="return confirm('هل تريد إيقاف هذا المكتب الآن؟');">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="danger small" type="submit" title="إيقاف خادم هذا المكتب المحلي">إيقاف المكتب</button>
</form>
</div>
</td>
</tr>""")
    body = f"""
<h1>إدارة المكاتب</h1>
{msg_html}
<div class="card">
<p>من هنا يتحكم المطور في المكاتب والمستخدمين المرتبطين بكل مكتب. عند إضافة مكتب يتم توليد رمز المزامنة تلقائيًا، ويجب نسخ القيم الناتجة إلى ملف .env الخاص بالمكتب.</p>
<a class="button" href="{reverse('central_office_new')}">إضافة مكتب جديد</a>
<a class="button secondary" href="{reverse('central_office_user_new')}">إضافة مستخدم إلى مكتب</a>
<form method="post" action="{reverse('central_cleanup_orphan_office_users')}" style="display:inline">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="danger" type="submit" onclick="return confirm('سيتم حذف مستخدمي المكاتب المحذوفة وسجلات إرسالهم. هل أنت متأكد؟')">تنظيف مستخدمي المكاتب المحذوفة</button>
</form>
<a class="button secondary" href="/admin/auth/user/">المستخدمون في إدارة الخادم المركزي</a>
<a class="button" href="{reverse('central_trainee_manager_picker')}">فتح برنامج تسيير المتكوّنين</a>
<form method="post" action="{reverse('central_offices_stop_all')}" style="display:inline" onsubmit="return confirm('هل تريد إيقاف كل المكاتب المحلية الآن؟');">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="danger" type="submit">إيقاف كل المكاتب</button>
</form>
<a class="button gold" href="{reverse('central_devices')}">طلبات ربط الأجهزة</a>
</div>
<table class="office-table">
<tr><th>المؤسسة / المكتب</th><th>الخادم</th><th>الحالة</th><th>انتهاء الترخيص</th><th>حد المستخدمين</th><th>مستخدمون مرتبطون</th><th>آخر اتصال</th><th>إجراء</th></tr>
{''.join(rows) if rows else '<tr><td colspan="8">لا توجد مكاتب مسجلة بعد</td></tr>'}
</table>
"""
    return _page("إدارة المكاتب", body)


@_developer_required
def central_cleanup_orphan_office_users(request):
    if request.method != "POST":
        return redirect("central_offices")
    with transaction.atomic():
        deleted_users, deleted_events, orphan_offices = _cleanup_orphan_office_users()
    messages.success(
        request,
        f"تم تنظيف مستخدمي المكاتب المحذوفة: حذف {deleted_users} مستخدم، وحذف {deleted_events} سجل إرسال مستخدمين، من {orphan_offices} مكتب محذوف."
    )
    return redirect("central_offices")


@_developer_required
def central_office_delete(request, pk: int):
    office = get_object_or_404(CentralOffice, pk=pk)
    linked_devices = CentralDeviceRegistration.objects.filter(assigned_office=office).order_by("hostname", "server_id")
    linked_devices_count = linked_devices.count()
    sync_events_count = CentralSyncEvent.objects.filter(source_office_id=office.office_id).count()
    update_logs_count = CentralUpdateCheckLog.objects.filter(Q(office_ref=office) | Q(office_id=office.office_id)).count()
    user_events_qs = _office_provision_user_events(office.office_id)
    linked_usernames = _usernames_in_provision_events(user_events_qs)
    linked_users_count = len(linked_usernames)

    if request.method == "POST":
        confirm_text = (request.POST.get("confirm_text") or "").strip()
        if confirm_text != office.office_id:
            messages.error(request, "لم يتم الحذف. اكتب Office ID كما هو للتأكيد.")
            return redirect("central_office_delete", pk=office.pk)

        delete_devices = request.POST.get("delete_devices") == "1"
        # حسب طلبك: حذف مستخدمي المكتب أصبح إجباريًا عند حذف أي مكتب،
        # حتى لا يبقى المستخدم ظاهرًا في صفحة إدارة المستخدمين والصلاحيات.
        delete_users = True
        delete_events = request.POST.get("delete_events") == "1"
        office_id = office.office_id
        office_name = office.office_name or office.office_id

        with transaction.atomic():
            removed_devices = 0
            if delete_devices:
                removed_devices, _ = CentralDeviceRegistration.objects.filter(assigned_office=office).delete()
            else:
                CentralDeviceRegistration.objects.filter(assigned_office=office).update(
                    assigned_office=None,
                    status=CentralDeviceRegistration.STATUS_PENDING,
                    device_token="",
                    config_delivered_at=None,
                )

            removed_users, removed_user_events = cleanup_users_for_office_delete(office_id)

            removed_events = 0
            if delete_events:
                removed_events, _ = CentralSyncEvent.objects.filter(source_office_id=office_id).delete()
                CentralUpdateCheckLog.objects.filter(Q(office_ref=office) | Q(office_id=office_id)).delete()
            else:
                CentralUpdateCheckLog.objects.filter(office_ref=office).update(office_ref=None)

            office.delete()
            # تنظيف إضافي بعد حذف المكتب: يزيل أي مستخدم عالق لم يعد له مكتب صالح.
            extra_deleted_users, extra_deleted_events, _ = _cleanup_orphan_office_users()
            removed_users += extra_deleted_users
            removed_user_events += extra_deleted_events

        msg = f"تم حذف المكتب {office_name}."
        if delete_devices:
            msg += f" تم حذف/تنظيف {removed_devices} سجل من الأجهزة المرتبطة."
        else:
            msg += " تم فك ارتباط الأجهزة المرتبطة وإرجاعها إلى انتظار الاعتماد."
        msg += f" تم حذف {removed_users} مستخدم مركزي مرتبط بهذا المكتب وحذف {removed_user_events} سجل إرسال مستخدمين."
        if delete_events:
            msg += f" وتم حذف {removed_events} من أحداث المزامنة الخاصة بالمكتب."
        messages.success(request, msg)
        return redirect("central_offices")

    devices_rows = ""
    for d in linked_devices:
        devices_rows += f"""
<tr>
<td>{escape(d.hostname or d.device_label or d.server_id)}<br><small dir="ltr">{escape(d.server_id)}</small></td>
<td>{escape(d.get_status_display())}</td>
<td>{escape(str(d.lan_ip or '-'))}</td>
<td>{escape(str(d.last_seen_at or '-'))}</td>
</tr>
"""
    body = f"""
<h1>حذف مكتب</h1>
<div class="card">
<p><b>المكتب:</b> {escape(office.office_name or office.office_id)}</p>
<p><b>Office ID:</b> <span dir="ltr">{escape(office.office_id)}</span></p>
<div class="notice">
هذه العملية تخص الخادم المركزي فقط. لا تحذف البرنامج من أجهزة الموظفين ولا تحذف PostgreSQL من تلك الأجهزة.
للاختبار النظيف، بعد حذف المكتب احذف أيضًا C:\\TrainingCenterData من أجهزة الاختبار ثم ثبّت البرنامج من جديد أو اطلب ربط الجهاز مرة أخرى.
</div>
</div>
<div class="card">
<h2>الأجهزة المرتبطة بهذا المكتب</h2>
<p>عدد الأجهزة المرتبطة: <b>{linked_devices_count}</b></p>
<table>
<tr><th>الجهاز</th><th>الحالة</th><th>IP</th><th>آخر اتصال</th></tr>
{devices_rows or '<tr><td colspan="4">لا توجد أجهزة مرتبطة بهذا المكتب.</td></tr>'}
</table>
</div>
<div class="card">
<h2>تأكيد الحذف</h2>
<p>أحداث المزامنة الخاصة بهذا المكتب: <b>{sync_events_count}</b></p>
<p>سجلات فحص التحديثات الخاصة بهذا المكتب: <b>{update_logs_count}</b></p>
<p>المستخدمون المرتبطون بهذا المكتب: <b>{linked_users_count}</b></p>
<form method="post">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<label><input type="checkbox" name="delete_devices" value="1" checked> حذف الأجهزة المرتبطة بهذا المكتب من قائمة طلبات/اعتماد الأجهزة</label><br>
<div class="notice">سيتم حذف المستخدمين المرتبطين بهذا المكتب تلقائيًا من إدارة المستخدمين والصلاحيات، إذا لم يكونوا مرتبطين بمكتب آخر موجود.</div>
<label><input type="checkbox" name="delete_events" value="1"> حذف أحداث المزامنة وسجلات التحديث الخاصة بهذا المكتب أيضًا</label>
<p>للتأكيد اكتب Office ID كما هو:</p>
<input
    name="confirm_text"
    dir="ltr"
    value="{escape(office.office_id)}"
    autocomplete="off"
    spellcheck="false"
    required>
<p>
<button class="danger" type="submit">حذف المكتب الآن</button>
<a class="button secondary" href="{reverse('central_offices')}">إلغاء ورجوع</a>
</p>
</form>
</div>
"""
    return _page("حذف مكتب", body)



@_developer_required
def central_office_root_delete(request, pk: int):
    office = get_object_or_404(CentralOffice, pk=pk)
    flags = office.feature_flags or {}
    data_dir = _normalize_local_data_dir_path(flags.get("local_data_dir") or os.path.dirname(_office_local_env_path(office)))
    database = _office_local_database(office)
    start_bat = _office_start_bat_path(office)
    start_sync_bat = _office_sync_bat_path(office)

    if request.method == "POST":
        confirm_text = (request.POST.get("confirm_text") or "").strip()
        if confirm_text != office.office_id:
            messages.error(request, "لم يتم الحذف من الجذور. اكتب Office ID كما هو للتأكيد.")
            return redirect("central_office_root_delete", pk=office.pk)

        office_id = office.office_id
        office_name = office.office_name or office.office_id
        report = []
        with transaction.atomic():
            removed_users, removed_user_events = cleanup_users_for_office_delete(office_id)
            devices_count, _ = CentralDeviceRegistration.objects.filter(assigned_office=office).delete()
            events_count, _ = CentralSyncEvent.objects.filter(source_office_id=office_id).delete()
            logs_count, _ = CentralUpdateCheckLog.objects.filter(Q(office_ref=office) | Q(office_id=office_id)).delete()
            office.delete()
            extra_users, extra_events, _ = _cleanup_orphan_office_users()
            removed_users += extra_users
            removed_user_events += extra_events
        report.append(f"تم حذف المكتب مركزيًا: {office_name}")
        report.append(f"مستخدمون محذوفون: {removed_users}، سجلات إرسال مستخدمين: {removed_user_events}")
        report.append(f"أجهزة محذوفة: {devices_count}، أحداث مزامنة: {events_count}، سجلات تحديث: {logs_count}")

        ok_db, out_db = _drop_local_database_if_exists(database)
        report.append(("تم حذف قاعدة البيانات المحلية" if ok_db else "فشل حذف قاعدة البيانات المحلية") + f": {database}")
        if out_db:
            report.append(out_db[-1200:])

        for item_path in [data_dir, start_bat, start_sync_bat]:
            ok, msg = _delete_file_or_folder(item_path)
            if msg:
                report.append(msg)

        messages.success(request, "تم تنفيذ حذف المكتب من الجذور.\n" + "\n".join(report[-10:]))
        return redirect("central_offices")

    body = f"""
<h1>حذف مكتب من الجذور</h1>
<div class="card">
<div class="notice">
هذه العملية مخصصة للتجارب النظيفة. ستحذف المكتب من الخادم المركزي وتحاول حذف قاعدة البيانات المحلية ومجلد البيانات وملفات التشغيل.
</div>
<p><b>المكتب:</b> {escape(office.office_name or office.office_id)}</p>
<p><b>Office ID:</b> <span dir="ltr">{escape(office.office_id)}</span></p>
<p><b>قاعدة البيانات المحلية:</b> <span dir="ltr">{escape(database)}</span></p>
<p><b>مجلد البيانات:</b> <span dir="ltr">{escape(data_dir)}</span></p>
<p><b>ملف التشغيل:</b> <span dir="ltr">{escape(start_bat)}</span></p>
<p><b>ملف مزامنة مرة واحدة:</b> <span dir="ltr">{escape(start_sync_bat or '-')}</span></p>
<form method="post">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<p>للتأكيد اكتب Office ID كما هو:</p>
<input name="confirm_text" dir="ltr" value="{escape(office.office_id)}" readonly required>
<p>
<button class="danger" type="submit">حذف من الجذور الآن</button>
<a class="button secondary" href="{reverse('central_offices')}">إلغاء</a>
</p>
</form>
</div>
"""
    return _page("حذف مكتب من الجذور", body)


@_developer_required
def central_office_pull_audit(request, pk: int):
    office = get_object_or_404(CentralOffice, pk=pk)
    if request.method != "POST":
        return redirect("central_offices")
    ok, message = _pull_office_audit_once(office)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("central_offices")


@_developer_required
def central_office_new(request):
    """إضافة مكتب جديد من لوحة المطور مع إمكانية تجهيزه كاملًا على نفس الجهاز."""
    created_office = None
    created_token = ""
    env_text = ""
    setup_output = ""
    setup_ok = None
    if request.method == "POST":
        form = CentralOfficeCreateForm(request.POST)
        if form.is_valid():
            created_office = form.save(commit=False)
            # إذا ترك المستخدم معرف الخادم فارغًا، ننشئ قيمة افتراضية مستقرة.
            if not (created_office.server_id or "").strip():
                safe_suffix = (created_office.office_id or "office").replace("office-", "")
                safe_suffix = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in safe_suffix).strip("-_") or "office"
                created_office.server_id = f"server-{safe_suffix}-01"
            created_token = generate_sync_token() if form.cleaned_data.get("generate_token") else (created_office.sync_token or generate_sync_token())
            created_office.sync_token = created_token
            flags = created_office.feature_flags or DEFAULT_FEATURE_FLAGS.copy()
            if form.cleaned_data.get("auto_prepare_local"):
                port = int(form.cleaned_data["local_port"])
                data_dir = (form.cleaned_data.get("local_data_dir") or "").strip()
                database = _safe_local_database_name((form.cleaned_data.get("local_database") or "").strip(), f"training_center_{created_office.office_id.replace('office-', '').replace('-', '_')}")
                data_dir = _normalize_local_data_dir_path(data_dir)
                flags.update({
                    "env_file_path": rf"{data_dir}\.env",
                    "local_data_dir": data_dir,
                    "local_database": database,
                    "local_port": port,
                    "start_office_bat": os.path.relpath(_generated_office_script_paths(created_office, port)[0], str(getattr(settings, "BASE_DIR", os.getcwd()))),
                    "start_sync_bat": os.path.relpath(_generated_office_script_paths(created_office, port)[1], str(getattr(settings, "BASE_DIR", os.getcwd()))),
                })
            created_office.feature_flags = flags
            created_office.save()
            ensure_default_organization_units(created_office)

            env_text = f"""# ضع هذه القيم في ملف .env الخاص بخادم المكتب المحلي
WILAYA_CODE={created_office.wilaya.code if created_office.wilaya_id else ''}
COMMUNE_CODE={created_office.commune.code if created_office.commune_id else ''}
OFFICE_CODE={created_office.office_code or ''}
OFFICE_ALIAS={created_office.office_alias or ''}
OFFICE_NAME={created_office.office_name}
OFFICE_DISPLAY_NAME={created_office.office_display_name or created_office.office_name}
INSTITUTION_TYPE={created_office.establishment_type or ''}
INSTITUTION_SERIAL={created_office.establishment_number or ''}
OFFICE_ID={created_office.office_id}
SERVER_ID={created_office.server_id}
CENTRAL_URL={_developer_central_url()}
CENTRAL_SYNC_ENABLED=1
SYNC_WORKER_ENABLED=1
SYNC_TOKEN={created_token}
SYNC_TRACKING_ENABLED=1
SYNC_TRACKED_MODELS=trainees.حضوري_أولي,trainees.تمهين,trainees.دفعة,trainees.مسائي_ومعابر
"""
            if form.cleaned_data.get("auto_prepare_local"):
                setup_ok, setup_output = _run_office_auto_setup(
                    created_office,
                    port=int(form.cleaned_data["local_port"]),
                    database=_safe_local_database_name((form.cleaned_data.get("local_database") or "").strip(), f"training_center_{created_office.office_id.replace('office-', '').replace('-', '_')}"),
                    data_dir=_normalize_local_data_dir_path((form.cleaned_data.get("local_data_dir") or "").strip()),
                    token=created_token,
                )
                if setup_ok:
                    _write_office_project_shortcuts(created_office)
                    messages.success(request, "تم إنشاء المكتب وتجهيزه كاملًا على هذا الجهاز: قاعدة البيانات، .env، ملفات التشغيل، migrations، وهوية المكتب، ومجلد روابط المكتب داخل المشروع.")
                else:
                    messages.error(request, "تم إنشاء المكتب مركزيًا، لكن فشل التجهيز المحلي. راجع المخرجات أسفل الصفحة.")
            else:
                messages.success(request, "تم إنشاء المكتب. انسخ إعدادات .env إلى جهاز المكتب أو فعّل خيار التجهيز الكامل عند إنشاء مكتب يعمل على نفس الجهاز.")
    else:
        # اقتراح منفذ جديد بعد المنافذ المستخدمة حاليًا
        used_ports = []
        for office in CentralOffice.objects.all():
            flags = office.feature_flags or {}
            try:
                used_ports.append(int(flags.get("local_port") or 0))
            except Exception:
                pass
        next_port = 8003
        while next_port in used_ports or next_port in (8000, 8002, 9000):
            next_port += 1
        form = CentralOfficeCreateForm(initial={
            "is_active": True,
            "allow_push": True,
            "allow_pull": True,
            "license_status": CentralOffice.LICENSE_ACTIVE,
            "license_plan": "standard",
            "max_users": 5,
            "establishment_number": "01",
            "local_port": next_port,
        })

    msg_html = "".join(f'<div class="card">{escape(m.message)}</div>' for m in messages.get_messages(request))
    result_html = ""
    if created_office:
        setup_html = ""
        if setup_output:
            setup_class = "notice" if setup_ok else "card"
            setup_html = f"""
<div class="{setup_class}">
<h3>مخرجات تجهيز المكتب المحلي</h3>
<pre>{escape(setup_output[-6000:])}</pre>
</div>
"""
        result_html = f"""
<div class="card">
<h2>تم إنشاء المكتب</h2>
<p><b>OFFICE_CODE:</b> <span dir="ltr">{escape(created_office.office_code or '-')}</span></p>
<p><b>OFFICE_ALIAS:</b> <span dir="ltr">{escape(created_office.office_alias or '-')}</span></p>
<p><b>Office ID:</b> <span dir="ltr">{escape(created_office.office_id)}</span></p>
<p><b>Server ID:</b> <span dir="ltr">{escape(created_office.server_id)}</span></p>
<p><b>الاسم الرسمي:</b> {escape(created_office.office_display_name or created_office.office_name or '-')}</p>
<p><b>Sync Token:</b> <span dir="ltr">{escape(created_token)}</span></p>
<p><b>Token masked:</b> <span dir="ltr">{escape(mask_token(created_token))}</span></p>
<h3>إعدادات المكتب المحلية</h3>
<pre>{escape(env_text)}</pre>
<p>إذا فعلت التجهيز الكامل فستجد ملفات التشغيل الجديدة داخل مجلد المشروع. إذا لم تفعله، انسخ القيم إلى ملف المكتب ثم شغّل migrate و init_office_identity.</p>
<div class="actions">
<a class="button" href="{reverse('central_office_edit', args=[created_office.pk])}">فتح تحكم المكتب</a>
<a class="button secondary" href="{reverse('central_offices')}">رجوع إلى المكاتب</a>
</div>
</div>
{setup_html}
"""
    commune_payload = [
        {
            "id": c.id,
            "code": c.code,
            "wilaya_id": c.wilaya_id,
            "wilaya_code": c.wilaya.code,
            "name_ar": c.name_ar,
            "name_latin": c.name_latin,
        }
        for c in Commune.objects.filter(is_active=True).select_related("wilaya").order_by("wilaya__code", "code")
    ]
    office_payload = [
        {
            "office_code": o.office_code or "",
            "commune_id": o.commune_id,
            "establishment_type": o.establishment_type or "",
            "establishment_number": o.establishment_number or "",
            "local_port": int((o.feature_flags or {}).get("local_port") or 0) if str((o.feature_flags or {}).get("local_port") or "").isdigit() else 0,
        }
        for o in CentralOffice.objects.all().only("office_code", "commune", "establishment_type", "establishment_number", "feature_flags")
    ]
    form_js = rf"""
<style>
.generated-field {{ background:#f8fafc; color:#0f172a; font-family:Consolas, 'Times New Roman', monospace; direction:ltr; }}
.autofill-note {{ color:#64748b; font-size:12px; margin-top:-8px; }}
</style>
<script>
(function() {{
  const communes = {json.dumps(commune_payload, ensure_ascii=False)};
  const offices = {json.dumps(office_payload, ensure_ascii=False)};
  const reservedPorts = new Set([8000, 8002, 9000]);
  offices.forEach(o => {{ if (o.local_port) reservedPorts.add(Number(o.local_port)); }});
  const $ = (id) => document.getElementById('id_' + id);
  const typeArabic = {{
    INSFP: 'المعهد الوطني المتخصص في التكوين المهني',
    CFPA: 'مركز التكوين المهني والتمهين',
    ANNEXE: 'ملحقة التكوين المهني',
    DIRECTION: 'مديرية التكوين والتعليم المهنيين',
    OTHER: 'مؤسسة التكوين المهني'
  }};
  function pad2(v) {{ v = String(v || '1').replace(/\D/g, '') || '1'; return v.padStart(2, '0').slice(-4); }}
  function normalizeType(v) {{ v = String(v || '').toUpperCase().replace('-', '_'); if (v === 'ANNEX') return 'ANNEXE'; return v || ''; }}
  function safeAscii(v, lower) {{
    v = String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9_]+/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '') || 'office';
    return lower ? v.toLowerCase() : v;
  }}
  function latinAlias(v) {{
    v = String(v || '').toUpperCase().replace(/[^A-Z0-9]+/g, ' ').trim();
    if (!v) return 'LOC';
    const parts = v.split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 3) || 'LOC';
    let alias = parts.map(p => p[0]).join('').slice(0, 3);
    if (alias.length < 3) alias = (alias + parts[0]).slice(0, 3);
    return alias || 'LOC';
  }}
  function buildCode(commune, type, num) {{ return commune ? ('DZ' + commune.wilaya_code + '-' + commune.code + '-' + type + num) : ''; }}
  function buildAlias(commune, type, num) {{ return commune ? ('DZ' + commune.wilaya_code + '-' + latinAlias(commune.name_latin) + '-' + type + num) : ''; }}
  function buildOfficeName(commune, type, num) {{ return commune ? (safeAscii(commune.name_latin, false).replace(/_/g, '') + '_' + type + num) : ''; }}
  function buildOfficeId(code) {{ return 'office_' + safeAscii(String(code || '').replace('DZ', 'dz'), true); }}
  function buildServerId(code) {{ return 'server_' + safeAscii(String(code || '').replace('DZ', 'dz'), true) + '_main'; }}
  function buildDb(code) {{ return ('training_center_' + safeAscii(String(code || '').replace(/-/g, '_'), true)).slice(0, 60).replace(/_+$/g, ''); }}
  function buildDir(code) {{ return 'C:\\TrainingCenterData_' + safeAscii(String(code || 'office').replace(/-/g, '_'), false); }}
  function buildDisplay(commune, type, num) {{
    if (!commune || !type) return '';
    let base = typeArabic[type] || typeArabic.OTHER;
    let label = base + ' - ' + commune.name_ar;
    if (num && num !== '01') label += ' ' + num;
    return label;
  }}
  function nextPort() {{ let p = 8003; while (reservedPorts.has(p)) p++; return p; }}
  function selectedCommune() {{ const el = $('commune'); const id = el ? Number(el.value || 0) : 0; return communes.find(c => Number(c.id) === id) || null; }}
  function fillCommunes() {{
    const w = $('wilaya'), c = $('commune');
    if (!w || !c) return;
    const current = c.value;
    const wid = Number(w.value || 0);
    c.innerHTML = '';
    c.add(new Option('---------', ''));
    if (!wid) {{ updateGenerated(); return; }}
    communes.filter(x => Number(x.wilaya_id) === wid).forEach(x => {{
      c.add(new Option(x.code + ' - ' + x.name_ar, String(x.id)));
    }});
    if (current && Array.from(c.options).some(o => o.value === current)) c.value = current;
  }}
  function nextNumber(commune, type) {{
    if (!commune || !type) return '01';
    const used = new Set(offices.filter(o => Number(o.commune_id) === Number(commune.id) && normalizeType(o.establishment_type) === type).map(o => String(o.establishment_number || '').padStart(2, '0')));
    const usedCodes = new Set(offices.map(o => o.office_code));
    for (let i = 1; i < 1000; i++) {{
      const n = pad2(i);
      const code = buildCode(commune, type, n);
      if (!used.has(n) && !usedCodes.has(code)) return n;
    }}
    return '01';
  }}
  function setValue(name, value, force) {{ const el = $(name); if (!el) return; if (force || !el.value || el.dataset.generated === '1') {{ el.value = value || ''; el.dataset.generated = '1'; }} }}
  function updateGenerated() {{
    const commune = selectedCommune();
    const type = normalizeType(($('establishment_type') || {{}}).value || '');
    const num = nextNumber(commune, type);
    const code = buildCode(commune, type, num);
    setValue('establishment_number', num, true);
    setValue('office_code', code, true);
    setValue('office_alias', buildAlias(commune, type, num), true);
    setValue('office_name', buildOfficeName(commune, type, num), true);
    setValue('office_id', code ? buildOfficeId(code) : '', true);
    setValue('server_id', code ? buildServerId(code) : '', true);
    setValue('local_database', code ? buildDb(code) : '', true);
    setValue('local_data_dir', code ? buildDir(code) : '', true);
    setValue('local_port', String(nextPort()), true);
    const display = $('office_display_name');
    if (display && (!display.value || display.dataset.generated === '1')) {{ display.value = buildDisplay(commune, type, num); display.dataset.generated = '1'; }}
  }}
  ['wilaya','commune','establishment_type'].forEach(name => {{ const el = $(name); if (el) el.addEventListener('change', function() {{ if (name === 'wilaya') fillCommunes(); updateGenerated(); }}); }});
  const display = $('office_display_name');
  if (display) display.addEventListener('input', function() {{ display.dataset.generated = display.value ? '0' : '1'; }});
  fillCommunes();
  updateGenerated();
}})();
</script>
"""

    body = f"""
<h1>إضافة مكتب جديد</h1>
{msg_html}
<div class="notice">
<b>الأفضل للمكاتب الجديدة على نفس الجهاز:</b> فعّل خيار <b>تجهيز المكتب كاملًا على هذا الجهاز</b>. سيقوم النظام بإنشاء قاعدة البيانات، مجلد البيانات، ملف .env، ملفات التشغيل، ثم تشغيل migrations تلقائيًا. هذه العملية قد تكون بطيئة لأنها تنشئ قاعدة بيانات جديدة وتطبق كل الجداول.
</div>
<div class="card">
<form method="post">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
{form.as_p()}
<div class="actions">
<button type="submit">إنشاء المكتب</button>
<button type="submit" class="gold" onclick="document.getElementById('id_auto_prepare_local').checked=true;">إنشاء وتجهيز المكتب كاملًا</button>
<a class="button secondary" href="{reverse('central_offices')}">رجوع</a>
</div>
</form>
</div>
{form_js}
<div class="card">
<h2>سكريبت بديل من PowerShell</h2>
<p>يمكنك أيضًا إضافة مكتب مستقبلًا من PowerShell عبر السكريبت <b>CREATE_NEW_OFFICE.ps1</b> بأمر واحد فقط.</p>
<pre>./CREATE_NEW_OFFICE.ps1 -WilayaCode "38" -CommuneCode "03801" -OfficeCode "DZ38-03801-INSFP01" -OfficeAlias "DZ38-TIS-INSFP01" -OfficeName "Tissemsilt_INSFP01" -OfficeDisplayName "المعهد الوطني المتخصص في التكوين المهني الشهيد تاج الدين حامد عبد الوهاب - تيسمسيلت" -OfficeId "office_dz38_03801_insfp01" -ServerId "server_dz38_03801_insfp01_main" -Port 8003 -Database "training_center_dz38_03801_insfp01" -DataDir "C:\\TrainingCenterData_DZ38_03801_INSFP01"</pre>
</div>
{result_html}
"""
    return _page("إضافة مكتب جديد", body)


@_developer_required
def central_office_edit(request, pk: int):
    office = get_object_or_404(CentralOffice, pk=pk)
    if request.method == "POST":
        action = request.POST.get("_action", "save")
        if action == "disable":
            office.is_active = False
            office.disabled_reason = request.POST.get("disabled_reason") or office.disabled_reason or "تم التعطيل من لوحة المطور"
            office.save(update_fields=["is_active", "disabled_reason", "updated_at"])
            messages.success(request, "تم تعطيل المكتب.")
            return redirect("central_office_edit", pk=office.pk)
        if action == "enable":
            office.is_active = True
            office.disabled_reason = ""
            office.license_status = CentralOffice.LICENSE_ACTIVE
            office.save(update_fields=["is_active", "disabled_reason", "license_status", "updated_at"])
            messages.success(request, "تم تفعيل المكتب.")
            return redirect("central_office_edit", pk=office.pk)
        if action == "prepare_local":
            try:
                port = int(request.POST.get("local_port") or (office.feature_flags or {}).get("local_port") or 8003)
            except Exception:
                port = 8003
            suffix = (office.office_id or "office").replace("office-", "")
            safe_suffix = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in suffix).strip("-_") or "office"
            database = _safe_local_database_name((request.POST.get("local_database") or (office.feature_flags or {}).get("local_database") or f"training_center_{safe_suffix.replace('-', '_')}").strip(), f"training_center_{safe_suffix.replace('-', '_')}")
            data_dir = (request.POST.get("local_data_dir") or (office.feature_flags or {}).get("local_data_dir") or rf"C:\TrainingCenterData_{safe_suffix}").strip()
            data_dir = _normalize_local_data_dir_path(data_dir)
            ok, output = _run_office_auto_setup(office, port=port, database=database, data_dir=data_dir, token=office.sync_token)
            flags = office.feature_flags or {}
            flags.update({
                "env_file_path": rf"{data_dir}\.env",
                "local_data_dir": data_dir,
                "local_database": database,
                "local_port": port,
                "start_office_bat": os.path.relpath(_generated_office_script_paths(office, port)[0], str(getattr(settings, "BASE_DIR", os.getcwd()))),
                "start_sync_bat": os.path.relpath(_generated_office_script_paths(office, port)[1], str(getattr(settings, "BASE_DIR", os.getcwd()))),
                "last_local_setup_output": output[-4000:] if output else "",
                "last_local_setup_ok": ok,
            })
            office.feature_flags = flags
            office.save(update_fields=["feature_flags", "updated_at"])
            if ok:
                _write_office_project_shortcuts(office)
                messages.success(request, "تم تجهيز/تحديث المكتب المحلي بنجاح، وتم إنشاء/تحديث مجلد روابط المكتب داخل المشروع.")
            else:
                messages.error(request, "فشل تجهيز المكتب المحلي. راجع مخرجات السكريبت في أسفل الصفحة.")
            return redirect("central_office_edit", pk=office.pk)

        form = CentralOfficeControlForm(request.POST, instance=office)
        if form.is_valid():
            saved_office = form.save()
            ensure_default_organization_units(saved_office)
            messages.success(request, "تم حفظ إعدادات المكتب وتحديث الهيكل الإداري الافتراضي إذا كان ناقصًا.")
            return redirect("central_office_edit", pk=office.pk)
    else:
        if not office.feature_flags:
            office.feature_flags = DEFAULT_FEATURE_FLAGS
        form = CentralOfficeControlForm(instance=office)

    msg_html = "".join(f'<div class="card">{escape(m.message)}</div>' for m in messages.get_messages(request))
    body = f"""
<h1>تحكم المكتب: {escape(office.office_name or office.office_id)}</h1>
{msg_html}
<div class="card">
<p><b>OFFICE_CODE:</b> <span dir="ltr">{escape(office.office_code or '-')}</span></p>
<p><b>OFFICE_ALIAS:</b> <span dir="ltr">{escape(office.office_alias or '-')}</span></p>
<p><b>Office ID:</b> <span dir="ltr">{escape(office.office_id)}</span></p>
<p><b>الاسم الرسمي:</b> {escape(office.office_display_name or office.office_name or '-')}</p>
<p><b>الولاية / البلدية:</b> {escape(str(office.wilaya or '-'))} / {escape(str(office.commune or '-'))}</p>
<p><b>Sync token:</b> <span dir="ltr">{escape(office.sync_token)}</span></p>
<p><b>آخر اتصال:</b> {escape(str(office.last_seen_at or "-"))}</p>
<p><b>الحالة الحالية:</b> {_status_badge(office)}</p>
<p>
<a class="button" href="{reverse('central_office_user_new')}?office={office.pk}">إضافة مستخدم لهذا المكتب</a>
<a class="button secondary" href="{reverse('central_office_users', args=[office.pk])}">تعديل المستخدمين</a>
<form method="post" action="{reverse('central_office_sync_now', args=[office.pk])}" style="display:inline">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="secondary" type="submit">مزامنة الآن</button>
</form>
</p>
</div>
<div class="card" id="control">
<form method="post">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
{form.as_p()}
<button type="submit" name="_action" value="save">حفظ التغييرات</button>
<a class="button secondary" href="{reverse('central_offices')}">رجوع</a>
</form>
</div>
<div class="card" id="local-setup">
<h2>تجهيز أو تعديل ملفات المكتب المحلي</h2>
<p>استعمل هذا القسم إذا فشل التجهيز عند إنشاء المكتب أو إذا أردت تعديل المنفذ/قاعدة البيانات/مجلد البيانات ثم إعادة إنشاء ملفات التشغيل وملف .env وتشغيل migrations.</p>
<form method="post">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<input type="hidden" name="_action" value="prepare_local">
<p><label>منفذ المكتب المحلي</label><input name="local_port" type="number" value="{escape(str((office.feature_flags or {}).get('local_port') or '8003'))}"></p>
<p><label>اسم قاعدة البيانات المحلية</label><input name="local_database" dir="ltr" value="{escape(str((office.feature_flags or {}).get('local_database') or ''))}"></p>
<p><label>مجلد بيانات المكتب</label><input name="local_data_dir" dir="ltr" value="{escape(str((office.feature_flags or {}).get('local_data_dir') or ''))}"></p>
<button class="gold" type="submit">تجهيز/تعديل المكتب المحلي الآن</button>
</form>
</div>
<div class="card">
<h2>إجراءات سريعة</h2>
<form method="post" style="display:inline">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button class="danger" type="submit" name="_action" value="disable">تعطيل المكتب</button>
</form>
<form method="post" style="display:inline">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
<button type="submit" name="_action" value="enable">تفعيل المكتب</button>
</form>
</div>
<div class="card">
<h2>آخر مخرجات تجهيز المكتب المحلي</h2>
<pre>{escape(str((office.feature_flags or {}).get('last_local_setup_output') or 'لا توجد مخرجات بعد.'))}</pre>
</div>
"""
    return _page("تحكم المكتب", body)



@_developer_required
def central_office_sync_now(request, pk: int):
    """زر مزامنة الآن من لوحة المطور المركزية لكل مكتب."""
    office = get_object_or_404(CentralOffice, pk=pk)
    if request.method != "POST":
        return redirect("central_offices")

    ok, output = _run_office_sync_once(office)
    short_output = output[-2500:] if output else ""
    if ok:
        messages.success(request, f"تم تشغيل مزامنة المكتب {office.office_name or office.office_id} بنجاح.\n{short_output}")
    else:
        messages.error(request, f"فشل تشغيل مزامنة المكتب {office.office_name or office.office_id}.\n{short_output}")
    return redirect(request.META.get("HTTP_REFERER") or reverse("central_offices"))


@_developer_required
def central_office_user_new(request):
    """ينشئ/يعدل المطور مستخدمًا داخل مكتب محدد عبر حدث مزامنة موجه لذلك المكتب.

    هذه الصفحة مرتبطة كذلك بمستخدمي إدارة الخادم المركزي: عند الحفظ يتم إنشاء/تحديث
    المستخدم في قاعدة الخادم المركزي، ثم إنشاء حدث مزامنة للمكتب المختار.
    """
    created_event = None
    target_office = None
    if request.method == "POST":
        form = CentralOfficeUserProvisionForm(request.POST)
        if form.is_valid():
            target_office = form.cleaned_data["office"]
            username = (form.cleaned_data["username"] or "").strip()
            password = form.cleaned_data["password"] or ""
            User = get_user_model()
            existing_user = User.objects.filter(username=username).first()
            user = create_or_update_central_user(
                username=username,
                password=password,
                email=form.cleaned_data.get("email") or "",
                first_name=form.cleaned_data.get("first_name") or "",
                last_name=form.cleaned_data.get("last_name") or "",
                is_active=bool(form.cleaned_data.get("is_active")),
                # لا نعرض حقول is_staff/can_* هنا؛ نحافظ على القيمة الحالية إن وجدت.
                is_staff=bool(getattr(existing_user, "is_staff", False)),
                is_superuser=False,
            )
            payload = payload_from_user_and_cleaned(user, form.cleaned_data, target_office)
            created_event = create_user_provision_event(target_office=target_office, user=user, payload=payload, kind="user_provision_from_central_page")
            messages.success(request, f"تم إنشاء/تحديث المستخدم {username} مركزيًا وإنشاء حدث مزامنة للمكتب {target_office.office_name or target_office.office_id}. شغّل عامل المزامنة في المكتب ليصل الحساب.")
            return redirect("central_office_users", pk=target_office.pk)
    else:
        initial = {}
        office_pk = (request.GET.get("office") or "").strip()
        if office_pk.isdigit():
            initial["office"] = int(office_pk)
        form = CentralOfficeUserProvisionForm(initial=initial)

    msg_html = "".join(f'<div class="card">{escape(m.message)}</div>' for m in messages.get_messages(request))
    body = f"""
<h1>إضافة مستخدم إلى مكتب</h1>
<div class="notice">هذه الصفحة تنشئ/تعدل المستخدم في الخادم المركزي، ثم تنشئ حدثًا موجّهًا للمكتب المختار. بعد ذلك شغّل عامل المزامنة في المكتب حتى يظهر المستخدم محليًا.</div>
{msg_html}
<div class="card">
<form method="post">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
{form.as_p()}
<button type="submit">حفظ المستخدم وإرساله للمكتب</button>
<a class="button secondary" href="{reverse('central_offices')}">رجوع</a>
</form>
</div>
"""
    return _page("إضافة مستخدم إلى مكتب", body)


@_developer_required
def central_office_users(request, pk: int):
    """قائمة المستخدمين المرتبطين بمكتب معيّن من أحداث المزامنة المركزية."""
    office = get_object_or_404(CentralOffice, pk=pk)
    payloads = latest_user_payloads_for_office(office)
    rows = []
    for username, data in sorted(payloads.items()):
        payload = data["payload"]
        perms = payload.get("permissions") or {}
        rows.append(f"""
<tr>
<td>{escape(username)}</td>
<td>{escape(payload.get('email') or '-')}</td>
<td>{'نعم' if payload.get('is_active', True) else 'لا'}</td>
<td>{escape(str(perms.get('role_code') or '-'))}</td>
<td>{'نعم' if perms.get('can_admin_panel') else 'لا'}</td>
<td>{escape(str(data['event'].received_at or '-'))}</td>
<td><a class="button" href="{reverse('central_office_user_edit', args=[office.pk, username])}">تعديل</a></td>
</tr>""")
    body = f"""
<h1>مستخدمو المكتب: {escape(office.office_name or office.office_id)}</h1>
<div class="card">
<a class="button" href="{reverse('central_office_user_new')}?office={office.pk}">إضافة مستخدم لهذا المكتب</a>
<a class="button secondary" href="{reverse('central_office_edit', args=[office.pk])}">رجوع إلى تحكم المكتب</a>
<a class="button secondary" href="/admin/auth/user/">فتح مستخدمي إدارة الخادم المركزي</a>
</div>
<table>
<tr><th>اسم المستخدم</th><th>البريد</th><th>مفعّل</th><th>الدور</th><th>يدخل الإدارة</th><th>آخر إرسال</th><th>إجراء</th></tr>
{''.join(rows) if rows else '<tr><td colspan="7">لا يوجد مستخدمون مرتبطون بهذا المكتب بعد.</td></tr>'}
</table>
"""
    return _page("مستخدمو المكتب", body)


@_developer_required
def central_office_user_edit(request, pk: int, username: str):
    """تعديل مستخدم مكتب وإرسال التعديل عبر المزامنة."""
    office = get_object_or_404(CentralOffice, pk=pk)
    payloads = latest_user_payloads_for_office(office)
    current = payloads.get(username, {}).get("payload", {})
    perms = current.get("permissions") or {}
    initial = {
        "office": office.pk,
        "username": username,
        "email": current.get("email") or "",
        "first_name": current.get("first_name") or "",
        "last_name": current.get("last_name") or "",
        "is_active": current.get("is_active", True),
        "notes": current.get("notes") or "",
    }
    if request.method == "POST":
        form = CentralOfficeUserEditForm(request.POST)
        if form.is_valid():
            target_office = form.cleaned_data["office"]
            username_value = (form.cleaned_data["username"] or username).strip()
            password = form.cleaned_data.get("password") or ""
            User = get_user_model()
            existing_user = User.objects.filter(username=username_value).first()
            user = create_or_update_central_user(
                username=username_value,
                password=password,
                email=form.cleaned_data.get("email") or "",
                first_name=form.cleaned_data.get("first_name") or "",
                last_name=form.cleaned_data.get("last_name") or "",
                is_active=bool(form.cleaned_data.get("is_active")),
                # لا نعرض حقول is_staff/can_* هنا؛ نحافظ على القيمة الحالية إن وجدت.
                is_staff=bool(getattr(existing_user, "is_staff", False)),
                is_superuser=False,
            )
            payload = payload_from_user_and_cleaned(user, form.cleaned_data, target_office)
            event = create_user_provision_event(target_office=target_office, user=user, payload=payload, kind="user_update_from_central_page")
            messages.success(request, f"تم إنشاء حدث تحديث للمستخدم {username_value}. رقم الحدث: {event.id}. شغّل عامل المزامنة في المكتب لتطبيق التعديل.")
            return redirect("central_office_users", pk=target_office.pk)
    else:
        form = CentralOfficeUserEditForm(initial=initial)
    msg_html = "".join(f'<div class="card">{escape(m.message)}</div>' for m in messages.get_messages(request))
    body = f"""
<h1>تعديل مستخدم المكتب: {escape(username)}</h1>
<div class="notice">اترك كلمة المرور فارغة إذا كنت تريد تعديل الصلاحيات فقط دون تغيير كلمة المرور في المكتب المحلي.</div>
{msg_html}
<div class="card">
<form method="post">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
{form.as_p()}
<button type="submit">حفظ التعديل وإرساله للمكتب</button>
<a class="button secondary" href="{reverse('central_office_users', args=[office.pk])}">رجوع إلى مستخدمي المكتب</a>
</form>
</div>
"""
    return _page("تعديل مستخدم مكتب", body)


def _update_badge(update: CentralUpdateRelease) -> str:
    if not update.is_active:
        return '<span class="badge warn">غير منشور</span>'
    if update.is_required:
        return '<span class="badge bad">إجباري</span>'
    return '<span class="badge ok">منشور</span>'


@_developer_required
def central_updates(request):
    updates = CentralUpdateRelease.objects.order_by("-published_at", "-created_at")
    rows = []
    for update in updates:
        target = "كل المكاتب" if update.rollout_all_offices else ", ".join(update.allowed_office_ids or []) or "لا يوجد"
        rows.append(f"""
<tr>
<td>{escape(update.version)}<br><small>{escape(update.title or "")}</small></td>
<td>{escape(update.channel)}</td>
<td>{escape(update.update_type)}</td>
<td>{_update_badge(update)}</td>
<td>{escape(target)}</td>
<td>{escape(str(update.published_at or "-"))}</td>
<td><a class="button" href="{reverse('central_update_edit', args=[update.pk])}">تعديل</a></td>
</tr>""")

    recent_checks = CentralUpdateCheckLog.objects.order_by("-created_at")[:10]
    check_rows = "".join(
        f"<tr><td>{escape(c.office_id)}</td><td>{escape(c.current_version or '-')}</td><td>{escape(c.offered_version or '-')}</td><td>{'نعم' if c.has_update else 'لا'}</td><td>{c.created_at:%Y-%m-%d %H:%M}</td></tr>"
        for c in recent_checks
    ) or '<tr><td colspan="5">لا توجد فحوصات بعد</td></tr>'

    body = f"""
<h1>إدارة التحديثات المركزية</h1>
<div class="card">
<p>من هنا ينشر المطور تحديثًا جديدًا، ويحدد هل يصل إلى كل المكاتب أو إلى مكاتب محددة فقط.</p>
<a class="button" href="{reverse('central_update_new')}">إضافة تحديث جديد</a>
</div>
<table>
<tr><th>النسخة</th><th>القناة</th><th>النوع</th><th>الحالة</th><th>المكاتب</th><th>تاريخ النشر</th><th>إجراء</th></tr>
{''.join(rows) if rows else '<tr><td colspan="7">لا توجد تحديثات بعد</td></tr>'}
</table>
<div class="card">
<h2>آخر فحوصات التحديث من المكاتب</h2>
<table>
<tr><th>المكتب</th><th>النسخة الحالية</th><th>النسخة المعروضة</th><th>يوجد تحديث</th><th>وقت الفحص</th></tr>
{check_rows}
</table>
</div>
"""
    return _page("إدارة التحديثات", body)


@_developer_required
def central_update_edit(request, pk: int | None = None):
    update = get_object_or_404(CentralUpdateRelease, pk=pk) if pk else CentralUpdateRelease()
    if request.method == "POST":
        form = CentralUpdateReleaseForm(request.POST, request.FILES, instance=update)
        if form.is_valid():
            saved_update = form.save()
            try:
                _save_central_update_package(saved_update, form.cleaned_data.get("package_file"))
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f"تم حفظ بيانات التحديث، لكن فشل حفظ ملف الحزمة: {exc}")
                return redirect("central_update_edit", pk=saved_update.pk)
            messages.success(request, "تم حفظ التحديث. إذا رفعت ملفًا فسيتم تقديمه للمكاتب من الخادم المركزي مباشرة.")
            return redirect("central_updates")
    else:
        form = CentralUpdateReleaseForm(instance=update)

    msg_html = "".join(f'<div class="card">{escape(m.message)}</div>' for m in messages.get_messages(request))
    title = "تعديل تحديث" if update.pk else "إضافة تحديث جديد"
    current_package = ""
    if update.pk and getattr(update, "local_package_name", ""):
        current_package = f'<div class="notice">الملف المرفوع حاليًا: <code>{escape(update.local_package_name)}</code><br>رابط تنزيل داخلي للمكاتب: <code>{escape(_developer_central_url().rstrip() + reverse("updates_download_api", args=[update.pk]))}</code></div>'
    body = f"""
<h1>{title}</h1>
{msg_html}
<div class="card">
{current_package}
<form method="post" enctype="multipart/form-data">
<input type="hidden" name="csrfmiddlewaretoken" value="{get_token(request)}">
{form.as_p()}
<style>
.central-update-file-picker {{
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 8px 0 4px;
  direction: rtl;
}}
.central-update-file-input {{
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  opacity: 0 !important;
  overflow: hidden !important;
  pointer-events: none !important;
}}
.central-update-file-button {{
  background:#0f766e;
  color:#fff;
  border:none;
  border-radius:10px;
  padding:10px 16px;
  cursor:pointer;
  font-weight:700;
  box-shadow:0 4px 14px #0001;
}}
.central-update-file-button:hover {{ background:#0b5f59; }}
.central-update-file-name {{
  display:inline-flex;
  align-items:center;
  min-height:40px;
  padding:8px 12px;
  border:1px solid #d1d5db;
  border-radius:10px;
  background:#f9fafb;
  color:#374151;
  min-width:220px;
  word-break:break-word;
}}
.central-update-file-name.has-file {{
  color:#065f46;
  border-color:#a7f3d0;
  background:#ecfdf5;
  font-weight:700;
}}
</style>
<script>
document.addEventListener("DOMContentLoaded", function () {{
  var input = document.getElementById("id_package_file");
  if (!input) {{ return; }}

  input.classList.add("central-update-file-input");
  input.setAttribute("accept", ".zip,.exe,.msi");

  var nativeLabel = document.querySelector('label[for="id_package_file"]');
  if (nativeLabel) {{ nativeLabel.style.display = "none"; }}

  var picker = document.createElement("div");
  picker.className = "central-update-file-picker";

  var button = document.createElement("button");
  button.type = "button";
  button.className = "central-update-file-button";
  button.textContent = "اختر ملف التحديث";

  var fileName = document.createElement("span");
  fileName.className = "central-update-file-name";
  fileName.textContent = "لم يتم اختيار أي ملف";

  picker.appendChild(button);
  picker.appendChild(fileName);
  input.parentNode.insertBefore(picker, input);

  button.addEventListener("click", function () {{ input.click(); }});
  input.addEventListener("change", function () {{
    if (input.files && input.files.length > 0) {{
      fileName.textContent = input.files[0].name;
      fileName.classList.add("has-file");
    }} else {{
      fileName.textContent = "لم يتم اختيار أي ملف";
      fileName.classList.remove("has-file");
    }}
  }});
}});
</script>
<button type="submit">حفظ</button>
<a class="button secondary" href="{reverse('central_updates')}">رجوع</a>
</form>
</div>
"""
    return _page(title, body)
