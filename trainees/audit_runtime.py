from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from django.db import transaction

from .models import ComprehensiveAuditLog

_current_request: ContextVar[Any | None] = ContextVar('current_request', default=None)
_current_user: ContextVar[Any | None] = ContextVar('current_user', default=None)


def set_current_request(request):
    _current_request.set(request)
    user = getattr(request, 'user', None) if request is not None else None
    _current_user.set(user)


def clear_current_request():
    _current_request.set(None)
    _current_user.set(None)


def get_current_request():
    return _current_request.get()


def get_current_user():
    return _current_user.get()


def _truncate(value: Any, limit: int = 255) -> str:
    text = str(value or '')
    return text[:limit]


def _json_safe(value: Any):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool, list, dict)):
        return value
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _sanitize_payload(data: dict | None) -> dict:
    clean = {}
    for key, value in (data or {}).items():
        clean[str(key)] = _json_safe(value)
    return clean


def write_comprehensive_audit(*, user=None, username_snapshot='', action='request', method='GET', status_code=None, success=True, screen_name='', view_name='', model_label='', object_pk='', object_repr='', path='', query_string='', details='', before_data=None, after_data=None, ip_address=None, user_agent='', session_key=''):
    payload = dict(
        user=user if getattr(user, 'is_authenticated', False) else None,
        username_snapshot=_truncate(username_snapshot or getattr(user, 'username', ''), 150),
        action=action,
        method=_truncate(method, 10),
        status_code=status_code,
        success=bool(success),
        screen_name=_truncate(screen_name, 255),
        view_name=_truncate(view_name, 255),
        model_label=_truncate(model_label, 255),
        object_pk=_truncate(object_pk, 64),
        object_repr=_truncate(object_repr, 255),
        path=_truncate(path, 500),
        query_string=str(query_string or '')[:4000],
        details=str(details or '')[:4000],
        before_data=_sanitize_payload(before_data),
        after_data=_sanitize_payload(after_data),
        ip_address=ip_address,
        user_agent=str(user_agent or '')[:2000],
        session_key=_truncate(session_key, 64),
    )

    def _create():
        log = ComprehensiveAuditLog.objects.create(**payload)
        # نخزن نسخة من سجل التدقيق في SyncOutbox حتى تُرسل تلقائيًا إلى الخادم المركزي
        # عندما يعمل Sync Worker. إذا كان جهاز المطوّر مطفأ، يبقى الحدث محفوظًا محليًا.
        try:
            from django.conf import settings
            if bool(getattr(settings, "SYNC_AUDIT_OUTBOX_ENABLED", True)):
                from sync_core.models import SyncOutbox
                from sync_core.services import create_outbox_event
                audit_payload = {
                    "audit_id": log.id,
                    "username": payload.get("username_snapshot", ""),
                    "action": payload.get("action", ""),
                    "method": payload.get("method", ""),
                    "status_code": payload.get("status_code"),
                    "success": payload.get("success", True),
                    "screen_name": payload.get("screen_name", ""),
                    "view_name": payload.get("view_name", ""),
                    "model_label": payload.get("model_label", ""),
                    "object_pk": payload.get("object_pk", ""),
                    "object_repr": payload.get("object_repr", ""),
                    "path": payload.get("path", ""),
                    "query_string": payload.get("query_string", ""),
                    "details": payload.get("details", ""),
                    "before_data": payload.get("before_data", {}),
                    "after_data": payload.get("after_data", {}),
                    "ip_address": str(payload.get("ip_address") or ""),
                    "user_agent": payload.get("user_agent", ""),
                    "session_key": payload.get("session_key", ""),
                    "created_at": log.created_at.isoformat() if log.created_at else "",
                }
                create_outbox_event(log, SyncOutbox.OP_SNAPSHOT, payload=audit_payload)
        except Exception:
            pass

    try:
        transaction.on_commit(_create)
    except Exception:
        _create()
