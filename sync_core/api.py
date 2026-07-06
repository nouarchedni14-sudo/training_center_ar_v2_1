import json
from typing import Any

from django.conf import settings
from pathlib import Path

from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CentralOffice, CentralSyncEvent, CentralUpdateRelease, CentralUpdateCheckLog, CentralDeviceRegistration


def _json_response(data: dict[str, Any], status: int = 200) -> JsonResponse:
    return JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})


def _read_json(request) -> dict[str, Any]:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


def _header(request, name: str) -> str:
    return (request.headers.get(name) or request.META.get("HTTP_" + name.upper().replace("-", "_")) or "").strip()


def _client_payload(request) -> dict[str, Any]:
    body = _read_json(request)
    return {
        "office_id": _header(request, "X-Sync-Office") or str(body.get("office_id") or "").strip(),
        "server_id": _header(request, "X-Sync-Server") or str(body.get("server_id") or "").strip(),
        "token": _header(request, "X-Sync-Token") or str(body.get("sync_token") or body.get("token") or "").strip(),
        "body": body,
    }


def _auth_office(request, *, require_push: bool = False, require_pull: bool = False):
    client = _client_payload(request)
    office_id = client["office_id"]
    server_id = client["server_id"]
    token = client["token"]

    if not office_id or not token:
        return None, client, _json_response({"ok": False, "error": "missing_office_or_token"}, 401)

    office = CentralOffice.objects.filter(office_id=office_id).first()
    auto_register = bool(getattr(settings, "CENTRAL_AUTO_REGISTER_OFFICES", False))
    if office is None and auto_register:
        office = CentralOffice.objects.create(
            office_id=office_id,
            office_name=str(client["body"].get("office_name") or office_id),
            server_id=server_id,
            sync_token=token,
            is_active=True,
        )

    if office is None:
        return None, client, _json_response({"ok": False, "error": "office_not_registered"}, 403)

    if not office.is_active:
        return None, client, _json_response({"ok": False, "error": "office_disabled"}, 403)

    if not constant_time_compare(office.sync_token or "", token):
        return None, client, _json_response({"ok": False, "error": "invalid_token"}, 403)

    if require_push and not office.allow_push:
        return None, client, _json_response({"ok": False, "error": "push_disabled"}, 403)

    if require_pull and not office.allow_pull:
        return None, client, _json_response({"ok": False, "error": "pull_disabled"}, 403)

    office.mark_seen(server_id=server_id)
    return office, client, None


def _event_to_dict(event: CentralSyncEvent) -> dict[str, Any]:
    return {
        "central_cursor": event.id,
        "central_event_id": str(event.central_event_id),
        "source_event_id": str(event.source_event_id),
        "source_office_id": event.source_office_id,
        "source_server_id": event.source_server_id,
        "app_label": event.app_label,
        "model_name": event.model_name,
        "object_pk": event.object_pk,
        "operation": event.operation,
        "payload": event.payload,
        "changed_fields": event.changed_fields,
        "payload_hash": event.payload_hash,
        "received_at": event.received_at.isoformat() if event.received_at else None,
        "source_created_at": event.source_created_at.isoformat() if event.source_created_at else None,
    }


@csrf_exempt
@require_http_methods(["POST"])
def device_register(request):
    """يسجل جهازًا جديدًا كطلب ربط بانتظار موافقة المطوّر.

    لا يحتاج SYNC_TOKEN. الجهاز يرسل SERVER_ID و request_secret. هذا لا يمنحه أي صلاحية
    مزامنة، بل يضعه فقط في قائمة انتظار الاعتماد داخل لوحة المطوّر.
    """
    body = _read_json(request)
    server_id = str(body.get("server_id") or "").strip()
    request_secret = str(body.get("request_secret") or "").strip()
    if not server_id or not request_secret:
        return _json_response({"ok": False, "error": "missing_server_id_or_request_secret"}, 400)

    obj, created = CentralDeviceRegistration.objects.get_or_create(
        server_id=server_id,
        defaults={
            "request_secret": request_secret,
            "hostname": str(body.get("hostname") or "")[:180],
            "device_label": str(body.get("device_label") or "")[:180],
            "lan_ip": (body.get("lan_ip") or request.META.get("REMOTE_ADDR") or None),
            "app_version": str(body.get("app_version") or "")[:50],
            "central_url": str(body.get("central_url") or "")[:200],
            "last_seen_at": timezone.now(),
        },
    )
    if not constant_time_compare(obj.request_secret or "", request_secret):
        return _json_response({"ok": False, "error": "invalid_request_secret"}, 403)

    changed = False
    for field, value in {
        "hostname": str(body.get("hostname") or obj.hostname or "")[:180],
        "device_label": str(body.get("device_label") or obj.device_label or "")[:180],
        "app_version": str(body.get("app_version") or obj.app_version or "")[:50],
        "central_url": str(body.get("central_url") or obj.central_url or "")[:200],
    }.items():
        if value and getattr(obj, field) != value:
            setattr(obj, field, value)
            changed = True
    ip_value = body.get("lan_ip") or request.META.get("REMOTE_ADDR") or None
    if ip_value and str(obj.lan_ip or "") != str(ip_value):
        obj.lan_ip = ip_value
        changed = True
    obj.last_seen_at = timezone.now()
    changed = True
    if changed:
        obj.save()

    return _json_response({
        "ok": True,
        "created": created,
        "status": obj.status,
        "server_id": obj.server_id,
        "message": "pending_approval" if obj.status == CentralDeviceRegistration.STATUS_PENDING else obj.status,
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def device_config(request):
    """يعيد إعدادات المزامنة للجهاز فقط بعد اعتماد المطوّر له."""
    body = _read_json(request)
    server_id = str(body.get("server_id") or "").strip()
    request_secret = str(body.get("request_secret") or "").strip()
    if not server_id or not request_secret:
        return _json_response({"ok": False, "error": "missing_server_id_or_request_secret"}, 400)
    obj = CentralDeviceRegistration.objects.filter(server_id=server_id).first()
    if obj is None:
        return _json_response({"ok": False, "status": "not_registered"}, 404)
    if not constant_time_compare(obj.request_secret or "", request_secret):
        return _json_response({"ok": False, "error": "invalid_request_secret"}, 403)
    obj.last_seen_at = timezone.now()
    obj.save(update_fields=["last_seen_at"])

    if obj.status == CentralDeviceRegistration.STATUS_REJECTED:
        return _json_response({"ok": False, "status": "rejected", "message": "device_rejected"}, 403)
    if obj.status != CentralDeviceRegistration.STATUS_APPROVED or not obj.assigned_office:
        return _json_response({"ok": True, "status": "pending", "message": "waiting_for_developer_approval"})

    office = obj.assigned_office
    if not office.is_active:
        return _json_response({"ok": False, "status": "office_disabled", "message": "office_disabled"}, 403)
    if not obj.device_token:
        from .services import generate_sync_token
        obj.device_token = generate_sync_token()
    obj.config_delivered_at = timezone.now()
    obj.save(update_fields=["device_token", "config_delivered_at", "last_seen_at"])

    central_url = str(obj.central_url or "").strip().rstrip("/")
    if not central_url:
        # عند النشر عبر الإنترنت ومع تفعيل إعدادات Reverse Proxy سيعيد build_absolute_uri
        # الرابط العام الصحيح مثل https://updates.example.com/.
        central_url = request.build_absolute_uri("/").rstrip("/")

    return _json_response({
        "ok": True,
        "status": "approved",
        "config": {
            "OFFICE_ID": office.office_id,
            "OFFICE_NAME": office.office_name or office.office_id,
            "SERVER_ID": obj.server_id,
            "SYNC_TOKEN": office.sync_token,
            "DEVICE_TOKEN": obj.device_token,
            "CENTRAL_URL": central_url,
            "CENTRAL_SYNC_ENABLED": "1",
            "SYNC_WORKER_ENABLED": "1",
            "SYNC_TRACKING_ENABLED": "1",
            "SYNC_APPLY_INBOX_ENABLED": "1",
            "IN_PROCESS_SYNC_WORKER_ENABLED": "1",
            "ALLOW_REMOTE_UPDATES": "1",
        },
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def sync_status(request):
    client = _client_payload(request)
    total_events = CentralSyncEvent.objects.count()
    total_offices = CentralOffice.objects.count()
    return _json_response({
        "ok": True,
        "mode": "central_server",
        "server_time": timezone.now().isoformat(),
        "client_office_id": client.get("office_id"),
        "total_offices": total_offices,
        "total_events": total_events,
        "api": {
            "device_register": "/api/devices/register/",
            "device_config": "/api/devices/config/",
            "push": "/api/sync/push/",
            "pull": "/api/sync/pull/",
            "license": "/api/license/check/",
            "updates": "/api/updates/check/",
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
def sync_push(request):
    office, client, error = _auth_office(request, require_push=True)
    if error:
        return error

    body = client["body"]
    events = body.get("events") or []
    if not isinstance(events, list):
        return _json_response({"ok": False, "error": "events_must_be_list"}, 400)

    accepted = 0
    duplicates = 0
    errors: list[dict[str, Any]] = []
    max_cursor = 0

    for index, item in enumerate(events):
        try:
            source_event_id = str(item.get("event_id") or item.get("source_event_id") or "").strip()
            if not source_event_id:
                raise ValueError("missing_event_id")

            obj, created = CentralSyncEvent.objects.get_or_create(
                source_event_id=source_event_id,
                defaults={
                    "source_office_id": office.office_id,
                    "source_server_id": client.get("server_id") or str(item.get("server_id") or ""),
                    "app_label": str(item.get("app_label") or ""),
                    "model_name": str(item.get("model_name") or ""),
                    "object_pk": str(item.get("object_pk") or ""),
                    "operation": str(item.get("operation") or ""),
                    "payload": item.get("payload") or {},
                    "changed_fields": item.get("changed_fields") or [],
                    "payload_hash": str(item.get("payload_hash") or ""),
                    "source_created_at": item.get("created_at") or None,
                    "extra": {"raw_status": item.get("status", "")},
                },
            )
            if created:
                accepted += 1
            else:
                duplicates += 1
            max_cursor = max(max_cursor, obj.id)
        except Exception as exc:
            errors.append({"index": index, "error": str(exc)})

    return _json_response({
        "ok": len(errors) == 0,
        "accepted": accepted,
        "duplicates": duplicates,
        "errors": errors,
        "next_cursor": max_cursor,
        "server_time": timezone.now().isoformat(),
    }, status=200 if len(errors) == 0 else 207)


@csrf_exempt
@require_http_methods(["POST"])
def sync_pull(request):
    office, client, error = _auth_office(request, require_pull=True)
    if error:
        return error

    body = client["body"]
    try:
        last_cursor = int(body.get("last_cursor") or body.get("cursor") or 0)
    except Exception:
        last_cursor = 0
    try:
        limit = int(body.get("limit") or getattr(settings, "SYNC_PULL_LIMIT", 100))
    except Exception:
        limit = 100
    limit = max(1, min(limit, 500))

    # لا نرسل للمكتب إلا الأحداث العامة أو الأحداث الموجهة له فقط.
    # بعض أحداث الخادم المركزي مثل إنشاء مستخدم داخل مكتب تحمل extra.target_office_id.
    # بدون هذا الفلتر قد يستقبل كل مكتب مستخدمي المكاتب الأخرى.
    def _event_is_visible_to_office(event):
        extra = event.extra or {}
        target_office_id = str(extra.get("target_office_id") or "").strip()
        if target_office_id and target_office_id != office.office_id:
            return False
        return True

    # وضع الأجهزة المستقلة:
    # لا نحجب أحداث نفس office_id، لأن عدة أجهزة داخل نفس المكتب يجب أن تتبادل نفس البيانات.
    # نحجب فقط الأحداث التي خرجت من نفس الجهاز الحالي حتى لا يستقبل الجهاز تعديلاته هو مرة أخرى.
    # server_id هو device_id فعليًا داخل كل جهاز مستقل.
    base_qs = (
        CentralSyncEvent.objects
        .filter(id__gt=last_cursor, is_deleted=False)
        .exclude(source_server_id=client.get("server_id") or "")
        .order_by("id")
    )

    selected_events = []
    # نقرأ دفعة أكبر قليلًا لأن بعض الأحداث قد تكون موجهة لمكاتب أخرى.
    scan_limit = min(limit * 5, 1000)
    for event in base_qs[:scan_limit]:
        if _event_is_visible_to_office(event):
            selected_events.append(event)
        if len(selected_events) >= limit:
            break

    events = [_event_to_dict(event) for event in selected_events]
    next_cursor = selected_events[-1].id if selected_events else last_cursor

    has_more = False
    for event in CentralSyncEvent.objects.filter(id__gt=next_cursor, is_deleted=False).exclude(source_server_id=client.get("server_id") or "").order_by("id")[:scan_limit]:
        if _event_is_visible_to_office(event):
            has_more = True
            break

    return _json_response({
        "ok": True,
        "events": events,
        "count": len(events),
        "next_cursor": next_cursor,
        "has_more": has_more,
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST", "GET"])
def audit_export(request):
    """تصدير سجلات التدقيق من خادم مكتب محلي حتى يستطيع جهاز المطوّر سحبها عند الحاجة.

    هذا المسار يُستخدم في وضع المكتب المحلي. الحماية تعتمد على نفس SYNC_TOKEN الخاص بالمكتب
    أو على OFFICE_PULL_TOKEN إن تم ضبطه في ملف .env.
    """
    from django.conf import settings as django_settings
    from trainees.models import ComprehensiveAuditLog

    if str(getattr(django_settings, "SYNC_MODE", "local_office")) == "central_server":
        return _json_response({"ok": False, "error": "audit_export_is_for_local_office_only"}, 400)

    client = _client_payload(request)
    expected_token = (
        str(getattr(django_settings, "OFFICE_PULL_TOKEN", "") or "").strip()
        or str(getattr(django_settings, "SYNC_TOKEN", "") or "").strip()
    )
    if expected_token and not constant_time_compare(expected_token, client.get("token") or ""):
        return _json_response({"ok": False, "error": "invalid_token"}, 403)

    body = client.get("body") or {}
    try:
        last_cursor = int(body.get("last_cursor") or request.GET.get("last_cursor") or 0)
    except Exception:
        last_cursor = 0
    try:
        limit = int(body.get("limit") or request.GET.get("limit") or 200)
    except Exception:
        limit = 200
    limit = max(1, min(limit, 1000))

    office_id = str(getattr(django_settings, "OFFICE_ID", "") or "").strip()
    office_name = str(getattr(django_settings, "OFFICE_NAME", "") or "").strip()
    server_id = str(getattr(django_settings, "SERVER_ID", "") or "").strip()

    qs = ComprehensiveAuditLog.objects.filter(id__gt=last_cursor).order_by("id")[:limit]
    events = []
    next_cursor = last_cursor
    for log in qs:
        next_cursor = log.id
        payload = {
            "audit_id": log.id,
            "office_id": office_id,
            "office_name": office_name,
            "server_id": server_id,
            "username": log.username_snapshot or (log.user.username if log.user else ""),
            "action": log.action,
            "method": log.method,
            "success": log.success,
            "status_code": log.status_code,
            "screen_name": log.screen_name,
            "view_name": log.view_name,
            "model_label": log.model_label,
            "object_pk": log.object_pk,
            "object_repr": log.object_repr,
            "path": log.path,
            "details": log.details,
            "before_data": log.before_data or {},
            "after_data": log.after_data or {},
            "ip_address": str(log.ip_address or ""),
            "user_agent": log.user_agent,
            "session_key": log.session_key,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        events.append({
            "event_id": f"audit-{office_id}-{server_id}-{log.id}",
            "source_event_id": f"audit-{office_id}-{server_id}-{log.id}",
            "source_office_id": office_id,
            "source_server_id": server_id,
            "app_label": "trainees",
            "model_name": "ComprehensiveAuditLog",
            "object_pk": str(log.id),
            "operation": "snapshot",
            "payload": payload,
            "changed_fields": [],
            "payload_hash": "",
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "central_cursor": next_cursor,
        })

    has_more = ComprehensiveAuditLog.objects.filter(id__gt=next_cursor).exists()
    return _json_response({
        "ok": True,
        "mode": "local_office",
        "office_id": office_id,
        "office_name": office_name,
        "server_id": server_id,
        "events": events,
        "count": len(events),
        "next_cursor": next_cursor,
        "has_more": has_more,
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST", "GET"])
def license_check(request):
    office, client, error = _auth_office(request)
    if error:
        return error

    # المرحلة 7: يرجع الخادم المركزي الآن إعدادات الترخيص والتحكم للمكتب.
    return _json_response({
        "ok": True,
        "office_id": office.office_id,
        "office_name": office.office_name,
        "license_status": office.effective_license_status,
        "license_valid": office.license_valid,
        "license_expires_at": office.license_expires_at.isoformat() if office.license_expires_at else None,
        "license_plan": office.license_plan,
        "max_users": office.max_users,
        "feature_flags": office.feature_flags or {},
        "is_active": office.is_active,
        "disabled_reason": office.disabled_reason,
        "allow_push": office.allow_push,
        "allow_pull": office.allow_pull,
        "server_time": timezone.now().isoformat(),
    })


def _parse_version_for_update(value: str) -> tuple[int, ...]:
    cleaned = (value or "").strip().lower().removeprefix("v")
    if not cleaned:
        return (0,)
    parts = []
    for token in cleaned.split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])


def _central_update_package_path(release: CentralUpdateRelease) -> Path | None:
    name = str(getattr(release, "local_package_name", "") or "").strip().replace("\\", "/")
    if not name or ".." in name.split("/"):
        return None
    root = Path(getattr(settings, "APP_DATA_DIR", settings.BASE_DIR)) / "central_updates" / "packages"
    path = (root / name).resolve()
    try:
        path.relative_to(root.resolve())
    except Exception:
        return None
    return path if path.exists() and path.is_file() else None


@csrf_exempt
@require_http_methods(["POST", "GET"])
def updates_check(request):
    """فحص التحديثات من الخادم المركزي وإرجاع رابط تنزيل آمن للمكتب."""
    office, client, error = _auth_office(request)
    if error:
        return error

    body = client["body"]
    current_version = str(body.get("current_version") or request.GET.get("current_version") or getattr(settings, "APP_VERSION", "")).strip()
    channel = str(body.get("channel") or request.GET.get("channel") or getattr(settings, "CENTRAL_DEFAULT_UPDATE_CHANNEL", "stable")).strip().lower() or "stable"
    if channel in {"beta", "testing"}:
        channel = "test"
    if channel not in {"stable", "test"}:
        channel = "stable"

    qs = CentralUpdateRelease.objects.filter(is_active=True, channel=channel).order_by("-published_at", "-created_at")
    release = None
    for item in qs:
        if not item.is_allowed_for_office(office.office_id):
            continue
        min_current = str(item.min_current_version or "").strip()
        if min_current and current_version and _parse_version_for_update(current_version) < _parse_version_for_update(min_current):
            continue
        release = item
        break

    has_update = False
    offered_version = release.version if release else ""
    if release:
        if not current_version:
            has_update = True
        else:
            has_update = _parse_version_for_update(release.version) > _parse_version_for_update(current_version)

    CentralUpdateCheckLog.objects.create(
        office_ref=office,
        office_id=office.office_id,
        server_id=client.get("server_id") or "",
        current_version=current_version,
        channel=channel,
        offered_version=offered_version,
        has_update=has_update,
        ip_address=request.META.get("REMOTE_ADDR") or None,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    update_payload = None
    if release and has_update:
        package_path = _central_update_package_path(release)
        if package_path:
            download_url = request.build_absolute_uri(reverse("updates_download_api", args=[release.pk]))
            download_requires_sync_auth = True
            package_name = package_path.name
        else:
            download_url = release.download_url
            download_requires_sync_auth = False
            package_name = Path(str(release.download_url or "")).name
        update_payload = {
            "version": release.version,
            "title": release.title,
            "channel": release.channel,
            "update_type": release.update_type,
            "download_url": download_url,
            "download_requires_sync_auth": download_requires_sync_auth,
            "package_name": package_name,
            "sha256": release.checksum_sha256,
            "checksum_sha256": release.checksum_sha256,
            "file_size_bytes": release.file_size_bytes,
            "is_required": release.is_required,
            "release_notes": release.release_notes,
            "published_at": release.published_at.isoformat() if release.published_at else None,
        }

    return _json_response({
        "ok": True,
        "office_id": office.office_id,
        "current_version": current_version,
        "channel": channel,
        "has_update": has_update,
        "latest_version": offered_version or current_version,
        "update": update_payload,
        "server_time": timezone.now().isoformat(),
    })


@csrf_exempt
@require_http_methods(["GET"])
def updates_download(request, pk: int):
    """تنزيل ملف تحديث مرفوع على الخادم المركزي بعد التحقق من هوية المكتب."""
    office, client, error = _auth_office(request)
    if error:
        return error

    release = CentralUpdateRelease.objects.filter(pk=pk, is_active=True).first()
    if release is None:
        return _json_response({"ok": False, "error": "update_not_found"}, 404)
    if not release.is_allowed_for_office(office.office_id):
        return _json_response({"ok": False, "error": "update_not_allowed_for_office"}, 403)
    package_path = _central_update_package_path(release)
    if package_path is None:
        return _json_response({"ok": False, "error": "update_file_not_found"}, 404)

    response = FileResponse(package_path.open("rb"), as_attachment=True, filename=package_path.name, content_type="application/octet-stream")
    if release.checksum_sha256:
        response["X-Update-SHA256"] = release.checksum_sha256
    return response
