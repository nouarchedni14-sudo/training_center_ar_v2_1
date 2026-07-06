import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.services.advanced_update_service import normalize_channel, validate_remote_payload

from django.conf import settings
from django.utils import timezone

from core.models import SystemConfiguration, UpdateCheckLog


def parse_version(value: str) -> tuple[int, ...]:
    cleaned = (value or "").strip().lower().removeprefix("v")
    if not cleaned:
        return (0,)
    parts: list[int] = []
    for token in cleaned.split('.'):
        digits = ''.join(ch for ch in token if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])





def discover_runtime_version() -> str:
    from pathlib import Path

    roots: list[Path] = []

    def add_root(value) -> None:
        if not value:
            return
        try:
            root = Path(value).resolve()
        except Exception:
            return
        if root not in roots:
            roots.append(root)

    try:
        from launcher.runtime_state import read_runtime_state
        state = read_runtime_state() or {}
        add_root(state.get('runtime_root'))
        add_root(state.get('root_dir'))
    except Exception:
        pass

    add_root(Path(sys.executable).resolve().parent if getattr(sys, 'executable', '') else None)
    add_root(Path.cwd())
    add_root(getattr(settings, 'BASE_DIR', '.'))

    discovered: list[tuple[tuple[int, ...], str, str]] = []

    def register(value: str, source: str) -> None:
        value = str(value or '').strip()
        if not value:
            return
        discovered.append((parse_version(value), value, source))

    for root in roots:
        candidates = [
            root / 'app_version.txt',
            root / 'release_manifest.json',
            root / '.env',
        ]
        for candidate in candidates:
            try:
                if not candidate.exists():
                    continue
                suffix = candidate.suffix.lower()
                if candidate.name.lower() == '.env':
                    for raw_line in candidate.read_text(encoding='utf-8', errors='ignore').splitlines():
                        line = raw_line.strip()
                        if not line or line.startswith('#') or '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        if key.strip() == 'APP_VERSION':
                            register(value.strip().strip("'").strip('"'), str(candidate))
                            break
                    continue
                if suffix == '.txt':
                    try:
                        register(candidate.read_text(encoding='utf-8-sig').strip(), str(candidate))
                    except Exception:
                        register(candidate.read_text(encoding='utf-8', errors='ignore').strip(), str(candidate))
                elif suffix == '.json':
                    register(str((json.loads(candidate.read_text(encoding='utf-8', errors='ignore')) or {}).get('version') or '').strip(), str(candidate))
            except Exception:
                continue

    env_version = str(getattr(settings, 'APP_VERSION', '') or '').strip() or str(__import__('os').environ.get('APP_VERSION', '') or '').strip()
    register(env_version, 'environment')

    if discovered:
        discovered.sort(key=lambda item: (item[0], item[1]))
        return discovered[-1][1]
    return '1.0.0'


def is_update_available(current: str, latest: str) -> bool:
    return parse_version(latest) > parse_version(current)



def update_status_summary(config: SystemConfiguration, pending_update: dict | None = None) -> dict:
    current_version = config.current_version or discover_runtime_version()
    latest_version = config.latest_version or current_version
    remote_update_available = is_update_available(current_version, latest_version)
    local_update_available = bool(pending_update and pending_update.get("version") and is_update_available(current_version, pending_update.get("version", "")))
    return {
        "current_version": current_version,
        "latest_version": latest_version,
        "remote_update_available": remote_update_available,
        "local_update_available": local_update_available,
        "effective_update_available": bool(remote_update_available or local_update_available or config.update_available),
    }





def sync_runtime_version_state(config: SystemConfiguration, pending_update: dict | None = None) -> str:
    runtime_version = discover_runtime_version() or config.current_version or '1.0.0'
    changed_fields: list[str] = []

    if config.current_version != runtime_version:
        config.current_version = runtime_version
        changed_fields.append('current_version')

    latest_version = str(config.latest_version or '').strip()
    if latest_version and parse_version(runtime_version) >= parse_version(latest_version):
        if config.latest_version != runtime_version:
            config.latest_version = runtime_version
            changed_fields.append('latest_version')
        if config.update_available:
            config.update_available = False
            changed_fields.append('update_available')
        message = str(config.update_message or '').strip()
        if message.startswith('تم تجهيز تحديث') or 'يوجد تحديث جديد' in message:
            config.update_message = 'أنت تستخدم آخر إصدار متاح.'
            changed_fields.append('update_message')

    if pending_update:
        pending_version = str(pending_update.get('version') or '').strip()
        if pending_version and parse_version(runtime_version) >= parse_version(pending_version):
            try:
                from core.services.local_update_service import clear_pending_state
                clear_pending_state()
                pending_update = None
            except Exception:
                pass
            if config.update_available:
                config.update_available = False
                changed_fields.append('update_available')
            if config.latest_version != runtime_version:
                config.latest_version = runtime_version
                changed_fields.append('latest_version')
            config.update_message = 'تم تطبيق التحديث بنجاح وأنت تستخدم آخر إصدار متاح.'
            changed_fields.append('update_message')

    if changed_fields:
        config.save(update_fields=list(dict.fromkeys(changed_fields + ['updated_at'])))

    return runtime_version

def _office_identity_for_central_updates() -> dict:
    """قراءة هوية المكتب اللازمة لفحص/تنزيل التحديثات من الخادم المركزي."""
    try:
        from sync_core.services import ensure_office_identity_from_settings
        identity, _ = ensure_office_identity_from_settings(create_missing_values=True)
        central_url = str(identity.central_url or getattr(settings, "CENTRAL_URL", "") or "").strip().rstrip("/")
        office_id = str(identity.office_id or getattr(settings, "OFFICE_ID", "") or "").strip()
        server_id = str(identity.server_id or getattr(settings, "SERVER_ID", "") or "").strip()
        sync_token = str(identity.sync_token or getattr(settings, "SYNC_TOKEN", "") or "").strip()
    except Exception:
        central_url = str(getattr(settings, "CENTRAL_URL", "") or "").strip().rstrip("/")
        office_id = str(getattr(settings, "OFFICE_ID", "") or "").strip()
        server_id = str(getattr(settings, "SERVER_ID", "") or "").strip()
        sync_token = str(getattr(settings, "SYNC_TOKEN", "") or "").strip()

    if not central_url or not office_id or not sync_token:
        return {}
    return {
        "central_url": central_url,
        "office_id": office_id,
        "server_id": server_id,
        "sync_token": sync_token,
    }


def central_update_download_headers() -> dict[str, str]:
    """رؤوس المصادقة المطلوبة لتنزيل حزمة التحديث من الخادم المركزي."""
    identity = _office_identity_for_central_updates()
    if not identity:
        return {}
    return {
        "X-Sync-Office": identity["office_id"],
        "X-Sync-Server": identity.get("server_id", ""),
        "X-Sync-Token": identity["sync_token"],
    }


def update_connectivity_status(config: SystemConfiguration | None = None) -> dict:
    """ملخص واضح لمصادر التحديث التي يمكن أن تعمل محليًا أو عبر الشبكة أو الإنترنت."""
    config = config or SystemConfiguration.get_solo()
    identity = _office_identity_for_central_updates()
    central_url = identity.get("central_url") or str(getattr(settings, "CENTRAL_URL", "") or "").strip().rstrip("/")
    update_server_url = str(config.update_server_url or getattr(settings, "UPDATE_SERVER_URL", "") or "").strip()
    is_https_central = central_url.lower().startswith("https://")
    is_local_central = central_url.lower().startswith("http://127.") or "localhost" in central_url.lower()
    central_ready = bool(central_url and identity.get("office_id") and identity.get("sync_token"))
    external_ready = bool(update_server_url)
    remote_enabled = bool(config.allow_remote_updates or central_ready or external_ready)
    if central_ready:
        if is_https_central:
            central_label = "مفعّل عبر الإنترنت HTTPS"
        elif is_local_central:
            central_label = "مفعّل محليًا على نفس الجهاز"
        else:
            central_label = "مفعّل عبر الشبكة/VPN"
    else:
        central_label = "غير مهيأ"
    return {
        "remote_enabled": remote_enabled,
        "allow_remote_updates": bool(config.allow_remote_updates),
        "central_ready": central_ready,
        "central_url": central_url,
        "central_label": central_label,
        "central_is_https": is_https_central,
        "central_is_local": is_local_central,
        "external_ready": external_ready,
        "external_update_url": update_server_url,
        "sync_enabled": bool(getattr(settings, "CENTRAL_SYNC_ENABLED", False)),
        "worker_enabled": bool(getattr(settings, "SYNC_WORKER_ENABLED", False)),
        "support_enabled": bool(config.developer_support_enabled),
    }


def _save_update_result(config: SystemConfiguration, *, payload: dict, latest_version: str, update_available: bool, update_required: bool, update_message: str, update_download_url: str, success: bool = True) -> dict:
    config.latest_version = latest_version
    config.update_available = update_available
    config.update_required = update_required
    config.update_message = update_message
    config.update_download_url = update_download_url
    config.last_update_check_at = timezone.now()
    config.save(update_fields=[
        "current_version", "latest_version", "update_available", "update_required", "update_message",
        "update_download_url", "last_update_check_at", "updated_at",
    ])

    safe_payload = dict(payload or {})
    # لا نخزن أي رؤوس مصادقة داخل سجل قاعدة البيانات.
    safe_payload.pop("download_headers", None)
    UpdateCheckLog.objects.create(
        success=success,
        requested_version=config.current_version,
        received_version=latest_version,
        message=update_message,
        details=safe_payload,
    )
    return {"ok": success, "message": update_message, "config": config, "payload": payload}


def _check_central_updates(config: SystemConfiguration, current_channel: str) -> dict | None:
    """فحص التحديث من الخادم المركزي الخاص بالمكاتب، إن كانت بياناته مهيأة."""
    identity = _office_identity_for_central_updates()
    if not identity:
        return None

    url = identity["central_url"].rstrip("/") + "/api/updates/check/"
    request_payload = {
        "office_id": identity["office_id"],
        "server_id": identity.get("server_id", ""),
        "current_version": config.current_version,
        "channel": current_channel,
    }
    data = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Sync-Office": identity["office_id"],
            "X-Sync-Server": identity.get("server_id", ""),
            "X-Sync-Token": identity["sync_token"],
        },
    )

    try:
        with urlopen(request, timeout=int(getattr(settings, "SYNC_WORKER_HTTP_TIMEOUT", 20))) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = f"فشل الاتصال بالخادم المركزي للتحديثات: HTTP {exc.code}."
        UpdateCheckLog.objects.create(success=False, requested_version=config.current_version, message=message, details={"reason": "central_http_error", "code": exc.code})
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config}
    except URLError:
        message = "تعذر الوصول إلى الخادم المركزي للتحديثات. البرنامج سيواصل العمل محليًا بشكل عادي."
        UpdateCheckLog.objects.create(success=False, requested_version=config.current_version, message=message, details={"reason": "central_url_error"})
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config}
    except Exception as exc:  # noqa: BLE001
        message = f"حدث خطأ أثناء فحص التحديث المركزي: {exc}"
        UpdateCheckLog.objects.create(success=False, requested_version=config.current_version, message=message, details={"reason": "central_unexpected_error"})
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config}

    if not result.get("ok", False):
        message = str(result.get("error") or result.get("message") or "الخادم المركزي رفض طلب فحص التحديث.")
        UpdateCheckLog.objects.create(success=False, requested_version=config.current_version, message=message, details={"reason": "central_rejected", "payload": result})
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config, "payload": result}

    update = result.get("update") or {}
    latest_version = str(result.get("latest_version") or update.get("version") or config.current_version or "").strip()
    has_update = bool(result.get("has_update") and latest_version and is_update_available(config.current_version, latest_version))
    update_required = bool(update.get("is_required", False))
    update_download_url = str(update.get("download_url") or "").strip()
    update_message = str(update.get("release_notes") or update.get("title") or ("يوجد تحديث مركزي جديد متاح." if has_update else "أنت تستخدم آخر إصدار متاح لهذا المكتب."))
    payload = {
        "source": "central",
        "latest_version": latest_version,
        "version": latest_version,
        "update_available": has_update,
        "update_required": update_required,
        "message": update_message,
        "release_notes": str(update.get("release_notes") or ""),
        "download_url": update_download_url,
        "sha256": str(update.get("sha256") or update.get("checksum_sha256") or "").strip(),
        "checksum": str(update.get("sha256") or update.get("checksum_sha256") or "").strip(),
        "package_name": str(update.get("package_name") or "").strip(),
        "package_type": "installer" if update.get("update_type") == "installer" else "zip",
        "channel": str(result.get("channel") or current_channel),
        "download_requires_sync_auth": bool(update.get("download_requires_sync_auth", False)),
        "central_office_id": result.get("office_id"),
    }

    return _save_update_result(
        config,
        payload=payload,
        latest_version=latest_version or config.current_version,
        update_available=has_update,
        update_required=update_required,
        update_message=update_message,
        update_download_url=update_download_url,
        success=True,
    )


def check_for_updates(force=False):
    config = SystemConfiguration.get_solo()
    config.current_version = discover_runtime_version() or config.current_version or "1.0.0"
    current_channel = normalize_channel(getattr(config, "update_channel", "") or getattr(settings, "UPDATE_CHANNEL", "") or getattr(settings, "CENTRAL_DEFAULT_UPDATE_CHANNEL", "stable"))

    connectivity = update_connectivity_status(config)
    if not connectivity["remote_enabled"] and not force:
        message = "فحص التحديثات البعيدة غير مهيأ. فعّل CENTRAL_URL للمزامنة المركزية أو UPDATE_SERVER_URL، أو استخدم التحديث المحلي ZIP."
        UpdateCheckLog.objects.create(
            success=False,
            requested_version=config.current_version,
            message=message,
            details={"reason": "disabled", "connectivity": connectivity},
        )
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config}

    # الأولوية للخادم المركزي إذا كان المكتب مربوطًا به، لأنه نظام التحديث الرسمي للمكاتب
    # سواء كان CENTRAL_URL داخل الشبكة المحلية أو عبر الإنترنت HTTPS/VPN.
    central_result = _check_central_updates(config, current_channel)
    if central_result is not None:
        return central_result

    if not config.update_server_url:
        message = "التحديث عبر الإنترنت غير مهيأ بعد لأن رابط خادم التحديث غير مضبوط. يمكنك متابعة استخدام التحديث المحلي بشكل عادي."
        UpdateCheckLog.objects.create(
            success=False,
            requested_version=config.current_version,
            message=message,
            details={"reason": "missing_url"},
        )
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config}

    query = urlencode({
        "installation_id": config.installation_id,
        "version": config.current_version,
        "app_mode": config.app_mode,
        "channel": current_channel,
    })
    url = config.update_server_url
    separator = "&" if "?" in url else "?"
    request_url = f"{url}{separator}{query}"

    try:
        with urlopen(request_url, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = f"فشل الاتصال بخادم التحديث: HTTP {exc.code}."
        UpdateCheckLog.objects.create(success=False, requested_version=config.current_version, message=message, details={"reason": "http_error", "code": exc.code})
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config}
    except URLError:
        message = "تعذر الوصول إلى خادم التحديث. البرنامج سيواصل العمل محليًا بشكل عادي."
        UpdateCheckLog.objects.create(success=False, requested_version=config.current_version, message=message, details={"reason": "url_error"})
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config}
    except Exception as exc:  # noqa: BLE001
        message = f"حدث خطأ أثناء فحص التحديثات: {exc}"
        UpdateCheckLog.objects.create(success=False, requested_version=config.current_version, message=message, details={"reason": "unexpected_error"})
        config.last_update_check_at = timezone.now()
        config.save(update_fields=["current_version", "last_update_check_at", "updated_at"])
        return {"ok": False, "message": message, "config": config}

    payload.setdefault("channel", current_channel)
    is_valid_payload, validation_message = validate_remote_payload(payload, config.current_version, current_channel)
    latest_version = str(payload.get("latest_version") or payload.get("version") or config.current_version)
    if is_valid_payload:
        update_available = bool(payload.get("update_available", is_update_available(config.current_version, latest_version)))
    else:
        update_available = False
    update_required = bool(payload.get("update_required", False))
    update_message = str((validation_message if not is_valid_payload else "") or payload.get("message") or payload.get("release_notes") or ("يوجد تحديث جديد متاح." if update_available else "أنت تستخدم آخر إصدار متاح."))
    package_type = str(payload.get("package_type") or ("exe" if payload.get("exe_url") else "zip" if payload.get("zip_url") else ""))
    update_download_url = str(payload.get("download_url") or payload.get("exe_url") or payload.get("zip_url") or "")
    payload["latest_version"] = latest_version
    payload["download_url"] = update_download_url
    if package_type:
        payload["package_type"] = package_type

    return _save_update_result(
        config,
        payload=payload,
        latest_version=latest_version,
        update_available=update_available,
        update_required=update_required,
        update_message=update_message,
        update_download_url=update_download_url,
        success=True,
    )
