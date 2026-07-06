import json
import time
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from .applier import apply_received_events
from .models import OfficeIdentity, SyncInbox, SyncOutbox, SyncState
from .services import ensure_office_identity_from_settings, normalize_url


class SyncWorkerError(Exception):
    pass


def _now():
    return timezone.now()


def _state(direction: str, scope: str = "global") -> SyncState:
    obj, _ = SyncState.objects.get_or_create(direction=direction, scope=scope)
    return obj


def _mark_state_success(direction: str, *, cursor: str | None = None, extra: dict[str, Any] | None = None) -> None:
    state = _state(direction)
    state.last_success_at = _now()
    state.last_error = ""
    state.last_error_at = None
    if cursor is not None:
        state.last_cursor = str(cursor)
    if extra is not None:
        state.extra = extra
    state.save()


def _mark_state_error(direction: str, error: str) -> None:
    state = _state(direction)
    state.last_error_at = _now()
    state.last_error = error[:4000]
    state.save(update_fields=["last_error_at", "last_error", "updated_at"])


def _endpoint(base_url: str, path: str) -> str:
    return normalize_url(base_url) + path


def _headers(identity: OfficeIdentity) -> dict[str, str]:
    return {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "X-Sync-Office": identity.office_id,
        "X-Sync-Server": identity.server_id,
        "X-Sync-Token": identity.sync_token,
    }


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False, cls=DjangoJSONEncoder).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise SyncWorkerError(f"HTTP {exc.code} from {url}: {raw[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise SyncWorkerError(f"Connection error to {url}: {exc}") from exc
    except TimeoutError as exc:
        raise SyncWorkerError(f"Timeout connecting to {url}") from exc
    except json.JSONDecodeError as exc:
        raise SyncWorkerError(f"Invalid JSON response from {url}") from exc


def _outbox_to_payload(event: SyncOutbox) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "office_id": event.office_id,
        "server_id": event.server_id,
        "app_label": event.app_label,
        "model_name": event.model_name,
        "object_pk": event.object_pk,
        "operation": event.operation,
        "payload": event.payload,
        "changed_fields": event.changed_fields,
        "payload_hash": event.payload_hash,
        "status": event.status,
        "attempts": event.attempts,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }


def validate_worker_ready(*, force: bool = False) -> OfficeIdentity:
    identity, _ = ensure_office_identity_from_settings(create_missing_values=True)
    if not force:
        if not bool(getattr(settings, "CENTRAL_SYNC_ENABLED", False)):
            raise SyncWorkerError("CENTRAL_SYNC_ENABLED=0. فعّلها إلى 1 بعد تسجيل المكتب في الخادم المركزي.")
        if not bool(getattr(settings, "SYNC_WORKER_ENABLED", False)):
            raise SyncWorkerError("SYNC_WORKER_ENABLED=0. فعّلها إلى 1 بعد اختبار الاتصال.")
    if not identity.central_url:
        raise SyncWorkerError("CENTRAL_URL غير مضبوط في .env.")
    if not identity.office_id or not identity.server_id or not identity.sync_token:
        raise SyncWorkerError("OFFICE_ID أو SERVER_ID أو SYNC_TOKEN غير مضبوط.")
    return identity


def push_pending_events(*, batch_size: int | None = None, force: bool = False) -> dict[str, Any]:
    identity = validate_worker_ready(force=force)
    batch_size = int(batch_size or getattr(settings, "SYNC_BATCH_SIZE", 100))
    max_attempts = int(getattr(settings, "SYNC_WORKER_MAX_ATTEMPTS", 10))
    include_failed = bool(getattr(settings, "SYNC_WORKER_PUSH_FAILED", True))
    timeout = int(getattr(settings, "SYNC_WORKER_HTTP_TIMEOUT", 20))

    statuses = [SyncOutbox.STATUS_PENDING]
    if include_failed:
        statuses.append(SyncOutbox.STATUS_FAILED)

    events = list(
        SyncOutbox.objects
        .filter(status__in=statuses, attempts__lt=max_attempts)
        .order_by("created_at")[:batch_size]
    )
    if not events:
        _mark_state_success("push", extra={"pushed": 0, "message": "no_pending_events"})
        return {"ok": True, "pushed": 0, "accepted": 0, "duplicates": 0, "errors": []}

    ids = [event.id for event in events]
    now = _now()
    SyncOutbox.objects.filter(id__in=ids).update(status=SyncOutbox.STATUS_SENDING, attempts=models_attempts_increment(), last_attempt_at=now, error_message="")
    events = list(SyncOutbox.objects.filter(id__in=ids).order_by("created_at"))

    payload = {
        "office_id": identity.office_id,
        "office_name": identity.office_name,
        "server_id": identity.server_id,
        "events": [_outbox_to_payload(event) for event in events],
    }
    try:
        response = _post_json(_endpoint(identity.central_url, "/api/sync/push/"), payload, _headers(identity), timeout)
    except Exception as exc:
        message = str(exc)
        SyncOutbox.objects.filter(id__in=ids).update(status=SyncOutbox.STATUS_FAILED, error_message=message[:4000])
        _mark_state_error("push", message)
        raise

    errors = response.get("errors") or []
    error_indexes = {int(item.get("index")) for item in errors if str(item.get("index", "")).isdigit()}
    sent_ids = [event.id for index, event in enumerate(events) if index not in error_indexes]
    failed_map = {int(item.get("index")): str(item.get("error") or "unknown_error") for item in errors if str(item.get("index", "")).isdigit()}

    if sent_ids:
        SyncOutbox.objects.filter(id__in=sent_ids).update(status=SyncOutbox.STATUS_SENT, sent_at=_now(), error_message="")
    for index, message in failed_map.items():
        if 0 <= index < len(events):
            SyncOutbox.objects.filter(id=events[index].id).update(status=SyncOutbox.STATUS_FAILED, error_message=message[:4000])

    result = {
        "ok": bool(response.get("ok", not errors)),
        "pushed": len(events),
        "accepted": int(response.get("accepted") or 0),
        "duplicates": int(response.get("duplicates") or 0),
        "failed": len(error_indexes),
        "errors": errors,
        "next_cursor": response.get("next_cursor"),
    }
    _mark_state_success("push", cursor=str(response.get("next_cursor") or ""), extra=result)
    return result


def models_attempts_increment():
    from django.db.models import F
    return F("attempts") + 1


def pull_remote_events(*, limit: int | None = None, force: bool = False) -> dict[str, Any]:
    identity = validate_worker_ready(force=force)
    timeout = int(getattr(settings, "SYNC_WORKER_HTTP_TIMEOUT", 20))
    limit = int(limit or getattr(settings, "SYNC_PULL_LIMIT", 100))
    state = _state("pull")
    last_cursor = state.last_cursor or "0"

    payload = {
        "office_id": identity.office_id,
        "office_name": identity.office_name,
        "server_id": identity.server_id,
        "last_cursor": last_cursor,
        "limit": limit,
    }
    try:
        response = _post_json(_endpoint(identity.central_url, "/api/sync/pull/"), payload, _headers(identity), timeout)
    except Exception as exc:
        _mark_state_error("pull", str(exc))
        raise

    events = response.get("events") or []
    received = 0
    duplicates = 0
    with transaction.atomic():
        for item in events:
            event_id = str(item.get("source_event_id") or item.get("event_id") or "").strip()
            if not event_id:
                continue
            obj, created = SyncInbox.objects.get_or_create(
                event_id=event_id,
                defaults={
                    "source_office_id": str(item.get("source_office_id") or ""),
                    "source_server_id": str(item.get("source_server_id") or ""),
                    "app_label": str(item.get("app_label") or ""),
                    "model_name": str(item.get("model_name") or ""),
                    "object_pk": str(item.get("object_pk") or ""),
                    "operation": str(item.get("operation") or ""),
                    "payload": item.get("payload") or {},
                    "central_cursor": str(item.get("central_cursor") or ""),
                    "status": SyncInbox.STATUS_RECEIVED,
                },
            )
            if created:
                received += 1
            else:
                duplicates += 1

    next_cursor = str(response.get("next_cursor") or last_cursor)
    result = {
        "ok": bool(response.get("ok", True)),
        "received": received,
        "duplicates": duplicates,
        "remote_count": len(events),
        "next_cursor": next_cursor,
        "has_more": bool(response.get("has_more", False)),
    }
    _mark_state_success("pull", cursor=next_cursor, extra=result)
    return result


def apply_inbox_events(*, limit: int | None = None) -> dict[str, Any]:
    if not bool(getattr(settings, "SYNC_APPLY_INBOX_ENABLED", True)):
        return {"ok": True, "skipped": True, "reason": "SYNC_APPLY_INBOX_ENABLED=0"}
    try:
        result = apply_received_events(limit=limit)
        _mark_state_success("apply", extra=result)
        return {"ok": True, **result}
    except Exception as exc:
        _mark_state_error("apply", str(exc))
        raise


def run_sync_once(*, push: bool = True, pull: bool = True, apply: bool = True, force: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True, "push": None, "pull": None, "apply": None}
    if push:
        result["push"] = push_pending_events(force=force)
    if pull:
        result["pull"] = pull_remote_events(force=force)
    if apply:
        result["apply"] = apply_inbox_events()
    return result


def run_sync_loop(*, interval: int | None = None, push: bool = True, pull: bool = True, apply: bool = True, force: bool = False, stdout=None) -> None:
    interval = int(interval or getattr(settings, "SYNC_WORKER_INTERVAL_SECONDS", 300))
    while True:
        try:
            result = run_sync_once(push=push, pull=pull, apply=apply, force=force)
            if stdout:
                stdout.write(f"[{_now().isoformat()}] OK {result}")
        except Exception as exc:
            if stdout:
                stdout.write(f"[{_now().isoformat()}] ERROR {exc}")
        time.sleep(max(10, interval))
