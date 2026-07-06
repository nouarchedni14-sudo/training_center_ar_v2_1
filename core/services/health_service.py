import traceback
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone
import os
from core.models import SystemConfiguration, SystemErrorLog, SystemHealthLog


def log_health(component: str, level: str, message: str, details=None):
    return SystemHealthLog.objects.create(
        component=component,
        level=level,
        message=message,
        details=details or {},
    )


def record_runtime_error(exc: Exception, request=None, source: str = "runtime"):
    user_display = ""
    path = ""
    details = {}
    if request is not None:
        path = getattr(request, "path", "") or ""
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            user_display = getattr(user, "username", "") or ""
        details["method"] = getattr(request, "method", "")
    return SystemErrorLog.objects.create(
        source=source,
        path=path,
        user_display=user_display,
        error_type=exc.__class__.__name__,
        message=str(exc),
        traceback_text=traceback.format_exc(),
        details=details,
    )


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        log_health("database", SystemHealthLog.LEVEL_OK, "الاتصال بقاعدة البيانات سليم")
        return {
            "component": "database",
            "ok": True,
            "level": SystemHealthLog.LEVEL_OK,
            "label": "قاعدة البيانات",
            "message": "الاتصال بقاعدة البيانات يعمل بشكل سليم.",
            "details": {},
        }
    except Exception as exc:  # noqa: BLE001
        message = f"تعذر فحص قاعدة البيانات: {exc}"
        log_health("database", SystemHealthLog.LEVEL_ERROR, message)
        return {
            "component": "database",
            "ok": False,
            "level": SystemHealthLog.LEVEL_ERROR,
            "label": "قاعدة البيانات",
            "message": message,
            "details": {"error": str(exc)},
        }


def _check_directory(path_value, component, label):
    path_obj = Path(path_value)
    details = {"path": str(path_obj)}

    try:
        exists = path_obj.exists()

        writable = exists and path_obj.is_dir() and os.access(path_obj, os.W_OK)
    except Exception as exc:  # noqa: BLE001
        message = f"تعذر الوصول إلى {label}: {exc}"
        log_health(component, SystemHealthLog.LEVEL_ERROR, message, details)
        return {
            "component": component,
            "ok": False,
            "level": SystemHealthLog.LEVEL_ERROR,
            "label": label,
            "message": message,
            "details": details | {"error": str(exc)},
        }

    if not exists:
        message = f"المجلد غير موجود: {path_obj}"
        log_health(component, SystemHealthLog.LEVEL_WARNING, message, details)
        return {
            "component": component,
            "ok": False,
            "level": SystemHealthLog.LEVEL_WARNING,
            "label": label,
            "message": message,
            "details": details | {"writable": False},
        }

    if not path_obj.is_dir():
        message = f"المسار ليس مجلدًا: {path_obj}"
        log_health(component, SystemHealthLog.LEVEL_ERROR, message, details)
        return {
            "component": component,
            "ok": False,
            "level": SystemHealthLog.LEVEL_ERROR,
            "label": label,
            "message": message,
            "details": details | {"writable": False},
        }

    if not writable:
        message = f"المجلد موجود لكن لا يملك صلاحية كتابة: {path_obj}"
        log_health(component, SystemHealthLog.LEVEL_WARNING, message, details)
        return {
            "component": component,
            "ok": False,
            "level": SystemHealthLog.LEVEL_WARNING,
            "label": label,
            "message": message,
            "details": details | {"writable": False},
        }

    message = f"المجلد متاح وقابل للكتابة: {path_obj}"
    log_health(component, SystemHealthLog.LEVEL_OK, message, details)
    return {
        "component": component,
        "ok": True,
        "level": SystemHealthLog.LEVEL_OK,
        "label": label,
        "message": message,
        "details": details | {"writable": True},
    }


def _check_updates(config):
    central_url = (getattr(settings, "CENTRAL_URL", "") or "").strip().rstrip("/")
    central_sync_enabled = bool(getattr(settings, "CENTRAL_SYNC_ENABLED", False))
    has_central_identity = bool(central_url and getattr(settings, "OFFICE_ID", "") and getattr(settings, "SYNC_TOKEN", ""))
    has_external_update_server = bool((config.update_server_url or "").strip())
    effective_remote_updates = bool(config.allow_remote_updates or has_central_identity or has_external_update_server)
    details = {
        "allow_remote_updates": config.allow_remote_updates,
        "central_url": central_url,
        "central_sync_enabled": central_sync_enabled,
        "has_central_identity": has_central_identity,
        "update_server_url": config.update_server_url,
        "effective_remote_updates": effective_remote_updates,
    }

    if has_central_identity:
        level = SystemHealthLog.LEVEL_OK
        message = "التحديث المركزي مهيأ. إذا كان CENTRAL_URL رابطًا عامًا HTTPS أو عبر VPN فيمكن للمكتب الفحص عبر الإنترنت."
        ok = True
    elif config.allow_remote_updates and not has_external_update_server:
        level = SystemHealthLog.LEVEL_WARNING
        message = "التحديث البعيد مفعّل لكن لا يوجد CENTRAL_URL صالح ولا UPDATE_SERVER_URL. التحديث المحلي ZIP ما يزال متاحًا."
        ok = False
    elif has_external_update_server:
        level = SystemHealthLog.LEVEL_OK
        message = "خادم التحديث الخارجي مهيأ."
        ok = True
    else:
        level = SystemHealthLog.LEVEL_OK
        message = "التحديث المحلي ZIP متاح. التحديث المركزي/الإنترنت غير مهيأ لهذا المكتب بعد."
        ok = True

    log_health("updates", level, message, details)
    return {
        "component": "updates",
        "ok": ok,
        "level": level,
        "label": "التحديثات",
        "message": message,
        "details": details,
    }


def _check_installation(config):
    ok = bool(config.installation_id)
    level = SystemHealthLog.LEVEL_OK if ok else SystemHealthLog.LEVEL_WARNING
    message = "معرّف التثبيت موجود." if ok else "معرّف التثبيت غير مضبوط."
    details = {"installation_id": config.installation_id or ""}
    log_health("installation", level, message, details)
    return {
        "component": "installation",
        "ok": ok,
        "level": level,
        "label": "هوية التثبيت",
        "message": message,
        "details": details,
    }


def collect_health_snapshot():
    config = SystemConfiguration.get_solo()
    checks = [
        _check_database(),
        _check_directory(settings.MEDIA_ROOT, "media", "مجلد الوسائط"),
        _check_directory(settings.LOG_DIR, "logs", "مجلد السجلات"),
        _check_updates(config),
        _check_installation(config),
    ]

    has_error = any(item["level"] == SystemHealthLog.LEVEL_ERROR for item in checks)
    has_warning = any(item["level"] == SystemHealthLog.LEVEL_WARNING for item in checks)

    if has_error:
        overall_level = SystemHealthLog.LEVEL_ERROR
        overall_label = "يوجد خلل يحتاج معالجة"
    elif has_warning:
        overall_level = SystemHealthLog.LEVEL_WARNING
        overall_label = "النظام يعمل مع بعض الملاحظات"
    else:
        overall_level = SystemHealthLog.LEVEL_OK
        overall_label = "النظام سليم"

    return {
        "checked_at": timezone.now(),
        "checks": checks,
        "overall_level": overall_level,
        "overall_label": overall_label,
        "ok_count": sum(1 for item in checks if item["level"] == SystemHealthLog.LEVEL_OK),
        "warning_count": sum(1 for item in checks if item["level"] == SystemHealthLog.LEVEL_WARNING),
        "error_count": sum(1 for item in checks if item["level"] == SystemHealthLog.LEVEL_ERROR),
    }
