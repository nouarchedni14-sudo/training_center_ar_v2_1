from django.apps import apps
from django.conf import settings
from django.db.models.signals import post_save, pre_delete

from .models import CentralOffice, SyncOutbox
from .services import create_outbox_event, is_sync_tracking_suspended, serialize_instance_for_sync, tracked_model_labels

_CONNECTED = False

_OFFICE_CLEANUP_CONNECTED = False


def _central_office_pre_delete_cleanup(sender, instance, **kwargs):
    """Fallback: تنظيف مستخدمي المكتب حتى إذا حُذف من أي مكان خارج الواجهة."""
    try:
        from .office_cleanup import cleanup_users_for_office_delete

        cleanup_users_for_office_delete(instance.office_id)
    except Exception:
        # لا نوقف حذف المكتب بسبب مشكلة عابرة في التنظيف؛ زر التنظيف اليدوي يعالج الباقي.
        pass


def connect_central_office_cleanup_signal():
    global _OFFICE_CLEANUP_CONNECTED
    if _OFFICE_CLEANUP_CONNECTED:
        return
    pre_delete.connect(
        _central_office_pre_delete_cleanup,
        sender=CentralOffice,
        weak=False,
        dispatch_uid="sync_core_central_office_cleanup_before_delete",
    )
    _OFFICE_CLEANUP_CONNECTED = True


EXCLUDED_APP_LABELS = {
    "admin",
    "auth",
    "contenttypes",
    "sessions",
    "messages",
    "staticfiles",
    "sync_core",
}


def _should_track_model(model) -> bool:
    label = f"{model._meta.app_label}.{model.__name__}"
    label_lower = label.lower()
    configured = [item.lower() for item in tracked_model_labels()]
    if configured:
        return label_lower in configured
    return model._meta.app_label not in EXCLUDED_APP_LABELS


def _post_save_handler(sender, instance, created, raw=False, **kwargs):
    if raw or is_sync_tracking_suspended():
        return
    operation = SyncOutbox.OP_CREATE if created else SyncOutbox.OP_UPDATE
    create_outbox_event(instance, operation)


def _pre_delete_handler(sender, instance, **kwargs):
    if is_sync_tracking_suspended():
        return
    payload = serialize_instance_for_sync(instance)
    create_outbox_event(instance, SyncOutbox.OP_DELETE, payload=payload)


def connect_sync_tracking_signals():
    global _CONNECTED
    if _CONNECTED:
        return
    if not bool(getattr(settings, "SYNC_TRACKING_ENABLED", False)):
        return

    for model in apps.get_models():
        if not _should_track_model(model):
            continue
        dispatch_uid_save = f"sync_core_track_save_{model._meta.label_lower}"
        dispatch_uid_delete = f"sync_core_track_delete_{model._meta.label_lower}"
        post_save.connect(_post_save_handler, sender=model, weak=False, dispatch_uid=dispatch_uid_save)
        pre_delete.connect(_pre_delete_handler, sender=model, weak=False, dispatch_uid=dispatch_uid_delete)

    _CONNECTED = True
