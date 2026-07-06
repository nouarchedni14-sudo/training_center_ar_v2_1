from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.db.models import Model

from .activity import client_ip
from .audit_runtime import get_current_request, get_current_user, write_comprehensive_audit


def _safe(value: Any):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Model):
        return {'pk': value.pk, 'label': str(value)}
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    return str(value)


def model_snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        name = field.name
        try:
            data[name] = _safe(getattr(instance, name))
        except Exception:
            data[name] = None
    return data


def diff_snapshots(before, after):
    before = before or {}
    after = after or {}
    changed = []
    for key in sorted(set(before.keys()) | set(after.keys())):
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def _request_meta(request=None):
    request = request or get_current_request()
    if not request:
        return {
            'path': '', 'method': '', 'view_name': '', 'ip_address': None,
            'query_string': '', 'user_agent': '', 'session_key': '',
        }
    resolver = getattr(request, 'resolver_match', None)
    session = getattr(request, 'session', None)
    return {
        'path': getattr(request, 'path', '') or '',
        'method': getattr(request, 'method', '') or '',
        'view_name': getattr(resolver, 'view_name', '') if resolver else '',
        'ip_address': client_ip(request),
        'query_string': request.META.get('QUERY_STRING', ''),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'session_key': getattr(session, 'session_key', '') or '',
    }


def create_audit_log(*, event_type='request', action='request', target_model='', target_id='', object_repr='', before_data=None, after_data=None, changed_fields=None, details='', status_code=None, request=None, user=None, program='', success=True):
    request_meta = _request_meta(request)
    actor = user if getattr(user, 'is_authenticated', False) else get_current_user()
    detail_parts = []
    if event_type:
        detail_parts.append(f'event_type={event_type}')
    if program:
        detail_parts.append(f'program={program}')
    if changed_fields:
        detail_parts.append('changed_fields=' + ', '.join(str(x) for x in changed_fields))
    if details:
        detail_parts.append(str(details))
    combined_details = ' | '.join(detail_parts)

    write_comprehensive_audit(
        user=actor,
        username_snapshot=getattr(actor, 'username', '') if actor else '',
        action=(action or 'request')[:20],
        method=(request_meta['method'] or ('POST' if action in {'create', 'update', 'delete'} else 'GET')),
        status_code=status_code,
        success=bool(success),
        screen_name=request_meta['view_name'] or request_meta['path'] or '',
        view_name=request_meta['view_name'] or '',
        model_label=target_model or '',
        object_pk=str(target_id or ''),
        object_repr=str(object_repr or '')[:255],
        path=request_meta['path'] or '',
        query_string=request_meta['query_string'] or '',
        details=combined_details,
        before_data=_safe(before_data or {}),
        after_data=_safe(after_data or {}),
        ip_address=request_meta['ip_address'],
        user_agent=request_meta['user_agent'] or '',
        session_key=request_meta['session_key'] or '',
    )


def audit_view_event(request=None, **kwargs):
    kwargs.setdefault('event_type', 'view')
    kwargs.setdefault('success', True)
    return create_audit_log(request=request, **kwargs)


def audit_error_event(request=None, *, details='', status_code=None, success=False, **kwargs):
    kwargs.setdefault('event_type', 'error')
    kwargs.setdefault('action', 'error')
    return create_audit_log(request=request, details=details, status_code=status_code, success=success, **kwargs)
