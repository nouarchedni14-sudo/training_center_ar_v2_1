from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from django.db import models as django_models
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import SyncConflict, SyncInbox, SyncOutbox
from .services import suspend_sync_tracking


class SyncApplyError(Exception):
    pass


@dataclass
class ApplyResult:
    applied: int = 0
    conflicts: int = 0
    failed: int = 0
    ignored: int = 0
    processed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "applied": self.applied,
            "conflicts": self.conflicts,
            "failed": self.failed,
            "ignored": self.ignored,
        }


def _model_for_event(event: SyncInbox):
    try:
        return apps.get_model(event.app_label, event.model_name)
    except LookupError as exc:
        raise SyncApplyError(f"النموذج غير موجود: {event.app_label}.{event.model_name}") from exc


def _local_payload(model, pk: str) -> dict[str, Any]:
    obj = model._base_manager.filter(pk=pk).first()
    if obj is None:
        return {}
    data: dict[str, Any] = {}
    for field in obj._meta.concrete_fields:
        try:
            data[field.name] = getattr(obj, field.attname)
        except Exception:
            continue
    return data


def _candidate_local_unsent_event(event: SyncInbox):
    return (
        SyncOutbox.objects
        .filter(app_label=event.app_label, model_name=event.model_name, object_pk=event.object_pk)
        .filter(status__in=[SyncOutbox.STATUS_PENDING, SyncOutbox.STATUS_FAILED, SyncOutbox.STATUS_SENDING])
        .order_by("-created_at")
        .first()
    )


def _record_conflict(event: SyncInbox, model, *, reason: str, local_event=None, resolution: str = "last_write_wins_remote_applied") -> SyncConflict:
    local_payload = _local_payload(model, event.object_pk)
    conflict = SyncConflict.objects.create(
        app_label=event.app_label,
        model_name=event.model_name,
        object_pk=event.object_pk,
        local_event_id=getattr(local_event, "event_id", None),
        remote_event_id=event.event_id,
        reason=reason,
        local_payload=local_payload,
        remote_payload=event.payload or {},
        resolution=resolution,
        status=SyncConflict.STATUS_RESOLVED if resolution else SyncConflict.STATUS_OPEN,
        resolved_at=timezone.now() if resolution else None,
    )
    return conflict


def _fields_by_payload_key(model) -> dict[str, Any]:
    """Map both field.name and field.attname to the concrete field object."""
    fields: dict[str, Any] = {}
    for field in model._meta.concrete_fields:
        fields[field.name] = field
        fields[field.attname] = field
    return fields


def _normalize_date_value(value: Any):
    if value in (None, ""):
        return None
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    if isinstance(value, str):
        parsed = parse_date(value[:10])
        if parsed is not None:
            return parsed
    return value


def _normalize_datetime_value(value: Any):
    if value in (None, ""):
        return None
    if hasattr(value, "tzinfo") and hasattr(value, "date"):
        return value
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is not None:
            return parsed
        parsed_date = parse_date(value[:10])
        if parsed_date is not None:
            return parsed_date
    return value


def _normalize_fk_value(field, value: Any):
    if value in (None, ""):
        return None
    # When payload used field.name for a FK, assign through attname so Django receives the raw pk.
    # If old events sent a label instead of pk, ignore it rather than failing the whole trainee apply.
    target_field = getattr(field, "target_field", None)
    if target_field is not None and isinstance(target_field, (django_models.AutoField, django_models.BigAutoField, django_models.IntegerField)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return value


def _normalize_value_for_field(field, value: Any):
    if isinstance(field, django_models.ForeignKey):
        return _normalize_fk_value(field, value)
    if isinstance(field, django_models.DateTimeField):
        return _normalize_datetime_value(value)
    if isinstance(field, django_models.DateField):
        return _normalize_date_value(value)
    if isinstance(field, django_models.BooleanField) and isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "نعم"}
    return value


def _find_existing_object_for_payload(model, event: SyncInbox, payload: dict[str, Any]):
    # First try the original primary key.
    obj = model._base_manager.filter(pk=event.object_pk).first()
    if obj is not None:
        return obj

    # If databases generated different ids, use stable natural identifiers when available.
    registration = payload.get("رقم_التسجيل")
    if registration and any(f.name == "رقم_التسجيل" for f in model._meta.concrete_fields):
        obj = model._base_manager.filter(رقم_التسجيل=registration).first()
        if obj is not None:
            return obj

    national_id = payload.get("الرقم_التعريفي")
    if national_id and any(f.name == "الرقم_التعريفي" for f in model._meta.concrete_fields):
        obj = model._base_manager.filter(الرقم_التعريفي=national_id).first()
        if obj is not None:
            return obj

    return None


def _apply_create_or_update(event: SyncInbox, model) -> str:
    payload = event.payload or {}
    if not isinstance(payload, dict):
        raise SyncApplyError("payload ليس قاموس JSON صالحًا")

    fields_by_key = _fields_by_payload_key(model)
    defaults: dict[str, Any] = {}
    pk_name = model._meta.pk.name
    pk_attname = model._meta.pk.attname

    for key, value in payload.items():
        field = fields_by_key.get(key)
        if field is None:
            continue
        if key in {pk_name, pk_attname, "id"}:
            continue
        assign_key = field.attname if isinstance(field, django_models.ForeignKey) else field.name
        defaults[assign_key] = _normalize_value_for_field(field, value)

    obj = _find_existing_object_for_payload(model, event, payload)
    if obj is None:
        obj = model(pk=event.object_pk)
        for key, value in defaults.items():
            setattr(obj, key, value)
        obj.save()
        return "created"

    for key, value in defaults.items():
        setattr(obj, key, value)
    obj.save()
    return "updated"


def _apply_delete(event: SyncInbox, model) -> str:
    obj = model._base_manager.filter(pk=event.object_pk).first()
    if obj is None:
        return "delete_ignored_missing"
    obj.delete()
    return "deleted"



def _target_office_matches(event: SyncInbox) -> bool:
    payload = event.payload or {}
    target_office_id = str(payload.get("target_office_id") or "").strip()
    if not target_office_id:
        return True
    current_office_id = str(getattr(settings, "OFFICE_ID", "") or "").strip()
    return target_office_id == current_office_id


def _apply_user_access_profile(user, permissions: dict[str, Any]) -> None:
    """تطبيق صلاحيات المستخدم القادمة من الخادم المركزي داخل المكتب المحلي."""
    try:
        from trainees.models import UserAccessProfile
    except Exception:
        return

    profile, _ = UserAccessProfile.objects.get_or_create(user=user)
    profile.access_enabled = bool(permissions.get("access_enabled", True))
    profile.is_customized = True
    profile.role_code = str(permissions.get("role_code") or "read_only")
    profile.can_access_admin_panel = bool(permissions.get("can_admin_panel"))
    profile.can_manage_all_programs = bool(permissions.get("can_manage_all_programs", False))
    profile.force_password_change = bool(permissions.get("force_password_change", False))

    # New detailed payload. Falls back to legacy compact keys for older events.
    if any(key in permissions for key in ("initial_add", "apprentice_add", "evening_add")):
        profile.initial_view = bool(permissions.get("initial_view", permissions.get("can_initial")))
        profile.initial_add = bool(permissions.get("initial_add", False))
        profile.initial_change = bool(permissions.get("initial_change", False))
        profile.initial_delete = bool(permissions.get("initial_delete", False))

        profile.apprentice_view = bool(permissions.get("apprentice_view", permissions.get("can_apprentice")))
        profile.apprentice_add = bool(permissions.get("apprentice_add", False))
        profile.apprentice_change = bool(permissions.get("apprentice_change", False))
        profile.apprentice_delete = bool(permissions.get("apprentice_delete", False))

        profile.evening_view = bool(permissions.get("evening_view", permissions.get("can_evening")))
        profile.evening_add = bool(permissions.get("evening_add", False))
        profile.evening_change = bool(permissions.get("evening_change", False))
        profile.evening_delete = bool(permissions.get("evening_delete", False))

        profile.can_view_reports = bool(permissions.get("can_view_reports", permissions.get("can_export_data", False)))
        profile.can_export_data = bool(permissions.get("can_export_data", permissions.get("can_export", False)))
    else:
        can_initial = bool(permissions.get("can_initial"))
        can_apprentice = bool(permissions.get("can_apprentice"))
        can_evening = bool(permissions.get("can_evening"))
        can_add = bool(permissions.get("can_add"))
        can_edit = bool(permissions.get("can_edit"))
        can_delete = bool(permissions.get("can_delete"))
        can_export = bool(permissions.get("can_export"))

        profile.initial_view = can_initial
        profile.initial_add = can_initial and can_add
        profile.initial_change = can_initial and can_edit
        profile.initial_delete = can_initial and can_delete

        profile.apprentice_view = can_apprentice
        profile.apprentice_add = can_apprentice and can_add
        profile.apprentice_change = can_apprentice and can_edit
        profile.apprentice_delete = can_apprentice and can_delete

        profile.evening_view = can_evening
        profile.evening_add = can_evening and can_add
        profile.evening_change = can_evening and can_edit
        profile.evening_delete = can_evening and can_delete

        profile.can_view_reports = can_export
        profile.can_export_data = can_export
    profile.save()


def _apply_provision_user(event: SyncInbox) -> str:
    payload = event.payload or {}
    username = str(payload.get("username") or event.object_pk or "").strip()
    if not username:
        raise SyncApplyError("اسم المستخدم مفقود في حدث إنشاء المستخدم")

    User = get_user_model()
    user = User.objects.filter(username=username).first()
    created = user is None
    if user is None:
        user = User(username=username)

    for field in ["email", "first_name", "last_name"]:
        if field in payload:
            setattr(user, field, payload.get(field) or "")
    if "is_active" in payload:
        user.is_active = bool(payload.get("is_active"))
    if "is_staff" in payload:
        user.is_staff = bool(payload.get("is_staff"))
    if "is_superuser" in payload:
        user.is_superuser = bool(payload.get("is_superuser"))
    if payload.get("password"):
        user.set_password(str(payload.get("password")))
    user.save()

    permissions = payload.get("permissions") or {}
    if isinstance(permissions, dict):
        _apply_user_access_profile(user, permissions)

    return "created_user" if created else "updated_user"


def apply_inbox_event(event: SyncInbox, *, conflict_policy: str | None = None) -> dict[str, Any]:
    """تطبيق حدث واحد من SyncInbox على قاعدة بيانات المكتب المحلي.

    السياسة المبدئية: last_write_wins.
    عند وجود تعديل محلي غير مرسل لنفس السجل، نسجل SyncConflict لحفظ السجل الكامل،
    ثم نطبّق الحدث البعيد لأن آخر حدث وصل من الخادم المركزي هو المعتمد في هذه المرحلة.
    """
    conflict_policy = (conflict_policy or getattr(settings, "SYNC_CONFLICT_POLICY", "last_write_wins") or "last_write_wins").strip()
    model = _model_for_event(event)
    local_event = _candidate_local_unsent_event(event)
    conflict_created = False

    with transaction.atomic():
        locked = SyncInbox.objects.select_for_update().get(pk=event.pk)
        if locked.status != SyncInbox.STATUS_RECEIVED:
            return {"ok": True, "status": locked.status, "ignored": True}

        if not _target_office_matches(locked):
            locked.status = SyncInbox.STATUS_IGNORED
            locked.error_message = "حدث موجّه لمكتب آخر"
            locked.save(update_fields=["status", "error_message"])
            return {"ok": True, "status": locked.status, "ignored": True}

        if locked.app_label == "auth" and locked.model_name in {"User", "user"} and locked.operation == "provision_user":
            try:
                with suspend_sync_tracking():
                    action = _apply_provision_user(locked)
            except Exception as exc:
                locked.status = SyncInbox.STATUS_FAILED
                locked.error_message = str(exc)[:4000]
                locked.save(update_fields=["status", "error_message"])
                raise
            locked.status = SyncInbox.STATUS_APPLIED
            locked.applied_at = timezone.now()
            locked.error_message = ""
            locked.save(update_fields=["status", "applied_at", "error_message"])
            return {"ok": True, "status": locked.status, "action": action, "conflict_logged": False}

        if local_event is not None:
            _record_conflict(
                locked,
                model,
                reason="local_unsent_change_for_same_record",
                local_event=local_event,
                resolution="last_write_wins_remote_applied" if conflict_policy == "last_write_wins" else "manual_review_required",
            )
            conflict_created = True
            if conflict_policy != "last_write_wins":
                locked.status = SyncInbox.STATUS_CONFLICT
                locked.error_message = "يوجد تعديل محلي غير مرسل لنفس السجل. يحتاج مراجعة."
                locked.save(update_fields=["status", "error_message"])
                return {"ok": False, "status": locked.status, "conflict": True}

        try:
            with suspend_sync_tracking():
                if locked.operation in {SyncOutbox.OP_CREATE, SyncOutbox.OP_UPDATE, SyncOutbox.OP_SNAPSHOT, "create", "update", "snapshot"}:
                    action = _apply_create_or_update(locked, model)
                elif locked.operation in {SyncOutbox.OP_DELETE, "delete"}:
                    action = _apply_delete(locked, model)
                else:
                    raise SyncApplyError(f"نوع العملية غير مدعوم: {locked.operation}")
        except Exception as exc:
            locked.status = SyncInbox.STATUS_FAILED
            locked.error_message = str(exc)[:4000]
            locked.save(update_fields=["status", "error_message"])
            raise

        locked.status = SyncInbox.STATUS_APPLIED
        locked.applied_at = timezone.now()
        locked.error_message = ""
        locked.save(update_fields=["status", "applied_at", "error_message"])
        return {"ok": True, "status": locked.status, "action": action, "conflict_logged": conflict_created}


def apply_received_events(*, limit: int | None = None) -> dict[str, int]:
    limit = int(limit or getattr(settings, "SYNC_APPLY_LIMIT", getattr(settings, "SYNC_PULL_LIMIT", 100)))
    result = ApplyResult()
    qs = SyncInbox.objects.filter(status=SyncInbox.STATUS_RECEIVED).order_by("central_cursor", "received_at", "id")[:limit]
    for event in qs:
        result.processed += 1
        try:
            applied = apply_inbox_event(event)
            if applied.get("ignored"):
                result.ignored += 1
            elif applied.get("conflict"):
                result.conflicts += 1
            else:
                result.applied += 1
                if applied.get("conflict_logged"):
                    result.conflicts += 1
        except Exception:
            result.failed += 1
    return result.as_dict()


def conflict_summary() -> dict[str, int]:
    return {
        "open": SyncConflict.objects.filter(status=SyncConflict.STATUS_OPEN).count(),
        "resolved": SyncConflict.objects.filter(status=SyncConflict.STATUS_RESOLVED).count(),
        "ignored": SyncConflict.objects.filter(status=SyncConflict.STATUS_IGNORED).count(),
        "total": SyncConflict.objects.count(),
    }
