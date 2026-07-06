from django.core.exceptions import PermissionDenied

from .models import ActivityLog


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip() or None


def log_activity(request, action, program="", obj=None, details=""):
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    object_repr = ""
    if obj is not None:
        object_repr = getattr(obj, "اللقب_والاسم", None) or str(obj)
    ActivityLog.objects.create(
        user=user,
        action=action,
        program=program or "",
        object_repr=object_repr[:255],
        details=(details or "")[:2000],
        path=(request.path or "")[:255],
        ip_address=client_ip(request),
    )


def deny_with_log(request, program, action):
    log_activity(request, "access_denied", program=program, details=f"محاولة {action}")
    raise PermissionDenied("غير مصرح لك بهذا الإجراء")
