import hashlib
import json
import os
import secrets
import uuid
from pathlib import Path
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.forms.models import model_to_dict

from .models import OfficeIdentity, SyncOutbox


def _clean(value: str | None) -> str:
    return (value or "").strip()


def normalize_url(value: str | None) -> str:
    return _clean(value).rstrip("/")


@dataclass(frozen=True)
class SyncDesignSettings:
    mode: str
    office_id: str
    office_name: str
    server_id: str
    sync_token: str
    central_url: str
    sync_enabled: bool


def _read_env_file_values() -> dict[str, str]:
    """Read the active ENV_FILE_PATH directly.

    This is intentionally used in addition to Django settings because long-running
    Windows processes can inherit stale environment variables (especially SERVER_ID).
    The .env file must be the source of truth for office identity.
    """
    env_path = (
        os.environ.get("ENV_FILE_PATH")
        or getattr(settings, "ENV_FILE_PATH", "")
        or ""
    )
    env_path = str(env_path).strip().strip('"').strip("'")
    if not env_path:
        return {}
    path = Path(env_path)
    if not path.exists() or not path.is_file():
        return {}

    values: dict[str, str] = {}
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    except Exception:
        return {}
    return values


def _env_bool_text(value: str | None, default: bool = False) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def read_sync_design_settings() -> SyncDesignSettings:
    file_values = _read_env_file_values()

    # The .env file wins over inherited OS environment values. This prevents a
    # developer office (server-tissemsilt-01) from being overwritten by a device
    # identity (device-...).
    mode = file_values.get("SYNC_MODE", getattr(settings, "SYNC_MODE", "local_office"))
    office_id = file_values.get("OFFICE_ID", getattr(settings, "OFFICE_ID", ""))
    office_name = file_values.get("OFFICE_DISPLAY_NAME") or file_values.get("OFFICE_NAME", getattr(settings, "OFFICE_NAME", ""))
    server_id = file_values.get("SERVER_ID", getattr(settings, "SERVER_ID", ""))
    sync_token = file_values.get("SYNC_TOKEN", getattr(settings, "SYNC_TOKEN", ""))
    central_url = file_values.get("CENTRAL_URL", getattr(settings, "CENTRAL_URL", ""))
    sync_enabled = _env_bool_text(
        file_values.get("CENTRAL_SYNC_ENABLED"),
        bool(getattr(settings, "CENTRAL_SYNC_ENABLED", False)),
    )

    return SyncDesignSettings(
        mode=mode,
        office_id=office_id,
        office_name=office_name,
        server_id=server_id,
        sync_token=sync_token,
        central_url=normalize_url(central_url),
        sync_enabled=sync_enabled,
    )


def generate_sync_token() -> str:
    return secrets.token_urlsafe(48)


def mask_token(token: str) -> str:
    token = _clean(token)
    if not token:
        return "غير مضبوط"
    if len(token) <= 10:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]}"


def ensure_office_identity_from_settings(create_missing_values: bool = True) -> tuple[OfficeIdentity, bool]:
    cfg = read_sync_design_settings()

    office_id = cfg.office_id or (OfficeIdentity.new_office_id() if create_missing_values else "")
    server_id = cfg.server_id or (OfficeIdentity.new_server_id() if create_missing_values else "")
    token = cfg.sync_token or (generate_sync_token() if create_missing_values else "")

    identity, created = OfficeIdentity.objects.get_or_create(
        singleton_key=1,
        defaults={
            "mode": cfg.mode,
            "office_id": office_id,
            "office_name": cfg.office_name,
            "server_id": server_id,
            "central_url": cfg.central_url,
            "sync_token": token,
            "sync_enabled": cfg.sync_enabled,
        },
    )

    changed = False
    for field, value in {
        "mode": cfg.mode,
        "office_name": cfg.office_name or identity.office_name,
        "central_url": cfg.central_url or identity.central_url,
        "sync_enabled": cfg.sync_enabled,
    }.items():
        if getattr(identity, field) != value:
            setattr(identity, field, value)
            changed = True

    if cfg.office_id and identity.office_id != cfg.office_id:
        identity.office_id = cfg.office_id
        changed = True
    if cfg.server_id and identity.server_id != cfg.server_id:
        identity.server_id = cfg.server_id
        changed = True
    if cfg.sync_token and identity.sync_token != cfg.sync_token:
        identity.sync_token = cfg.sync_token
        changed = True

    if changed:
        identity.save()

    return identity, created


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def serialize_instance_for_sync(instance) -> dict[str, Any]:
    """تحويل سجل Django إلى قاموس آمن للتخزين في JSONField.

    نعتمد على الحقول concrete فقط، ونسجل مفاتيح ForeignKey كـ ID.
    الملفات تسجل كاسم/مسار نسبي فقط، ومزامنة الملف نفسه ستكون مرحلة لاحقة.
    """
    data: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        name = field.name
        try:
            value = getattr(instance, field.attname)
        except Exception:
            continue
        if hasattr(value, "name"):
            value = value.name
        data[name] = _json_safe(value)
    return data


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, cls=DjangoJSONEncoder).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _idempotency_key(identity: OfficeIdentity, app_label: str, model_name: str, object_pk: str, operation: str, payload_hash: str) -> str:
    # نضيف UUID في النهاية لأن التعديلات المتكررة لنفس السجل يجب أن تُسجل كأحداث مستقلة.
    return f"{identity.office_id}:{identity.server_id}:{app_label}:{model_name}:{object_pk}:{operation}:{payload_hash[:16]}:{uuid.uuid4().hex[:12]}"


def create_outbox_event(instance, operation: str, *, changed_fields: list[str] | None = None, payload: dict[str, Any] | None = None) -> SyncOutbox | None:
    """إنشاء حدث محلي داخل SyncOutbox.

    الدالة لا ترسل البيانات للخادم المركزي بعد. الإرسال سيكون في مرحلة العامل Sync Worker.
    """
    if not bool(getattr(settings, "SYNC_TRACKING_ENABLED", False)):
        return None

    try:
        identity, _ = ensure_office_identity_from_settings(create_missing_values=True)
        app_label = instance._meta.app_label
        model_name = instance._meta.model_name
        object_pk = str(instance.pk)
        if payload is None:
            payload = serialize_instance_for_sync(instance)
        payload = _json_safe(payload)
        payload_hash = _payload_hash(payload)
        event = SyncOutbox.objects.create(
            office_id=identity.office_id,
            server_id=identity.server_id,
            app_label=app_label,
            model_name=model_name,
            object_pk=object_pk,
            operation=operation,
            payload=payload,
            changed_fields=changed_fields or [],
            payload_hash=payload_hash,
            idempotency_key=_idempotency_key(identity, app_label, model_name, object_pk, operation, payload_hash),
        )
        return event
    except (OperationalError, ProgrammingError, DatabaseError):
        # أثناء أول تشغيل أو قبل migrate قد لا تكون الجداول موجودة. نتجاهل ذلك حتى لا يتوقف البرنامج.
        return None
    except Exception:
        # لا نوقف حفظ بيانات المستخدم إذا فشل تسجيل حدث المزامنة.
        return None


def tracked_model_labels() -> list[str]:
    raw = getattr(settings, "SYNC_TRACKED_MODELS", [])
    if isinstance(raw, str):
        parts = [item.strip() for item in raw.split(",")]
    else:
        parts = [str(item).strip() for item in raw]
    return [item for item in parts if item]

# ===== Phase 6: safe application of remote events =====
# عند تطبيق أحداث SyncInbox القادمة من الخادم المركزي، لا نريد أن يؤدي save/delete المحلي
# إلى إنشاء أحداث جديدة في SyncOutbox، وإلا سنقع في حلقة مزامنة لا تنتهي.
import threading
from contextlib import contextmanager

_sync_tracking_state = threading.local()


def is_sync_tracking_suspended() -> bool:
    return bool(getattr(_sync_tracking_state, "suspended", False))


@contextmanager
def suspend_sync_tracking():
    previous = bool(getattr(_sync_tracking_state, "suspended", False))
    _sync_tracking_state.suspended = True
    try:
        yield
    finally:
        _sync_tracking_state.suspended = previous
