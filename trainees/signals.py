from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from django.db.models.signals import pre_save, post_save

from .models import ActivityLog, UserAccessProfile, UserAccountAuditLog
from .audit_runtime import write_comprehensive_audit
from .services.role_service import build_role_change_note


def _client_ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip() or None


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ActivityLog.objects.create(
        user=user,
        action="login",
        object_repr="تسجيل الدخول",
        details="تم تسجيل الدخول إلى النظام.",
        path=getattr(request, "path", "") or "",
        ip_address=_client_ip(request),
    )
    write_comprehensive_audit(
        user=user,
        action="auth",
        method=getattr(request, "method", "POST") if request else "POST",
        status_code=200,
        success=True,
        screen_name="تسجيل الدخول",
        view_name="login",
        path=getattr(request, "path", "") or "",
        details="تم تسجيل الدخول إلى النظام.",
        ip_address=_client_ip(request),
        user_agent=(getattr(request, "META", {}) or {}).get("HTTP_USER_AGENT", ""),
        session_key=getattr(getattr(request, "session", None), "session_key", "") if request else "",
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    ActivityLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action="logout",
        object_repr="تسجيل الخروج",
        details="تم تسجيل الخروج من النظام.",
        path=getattr(request, "path", "") if request else "",
        ip_address=_client_ip(request),
    )
    write_comprehensive_audit(
        user=user if getattr(user, "is_authenticated", False) else None,
        username_snapshot=getattr(user, "username", "") if getattr(user, "is_authenticated", False) else "",
        action="auth",
        method=getattr(request, "method", "POST") if request else "POST",
        status_code=200,
        success=True,
        screen_name="تسجيل الخروج",
        view_name="logout",
        path=getattr(request, "path", "") if request else "",
        details="تم تسجيل الخروج من النظام.",
        ip_address=_client_ip(request),
        user_agent=(getattr(request, "META", {}) or {}).get("HTTP_USER_AGENT", ""),
        session_key=getattr(getattr(request, "session", None), "session_key", "") if request else "",
    )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    username = (credentials or {}).get("username", "") or "غير معروف"
    details = f"فشل تسجيل الدخول للحساب: {username}"
    ActivityLog.objects.create(
        user=None,
        action="login_failed",
        object_repr="محاولة دخول فاشلة",
        details=details,
        path=getattr(request, "path", "") if request else "",
        ip_address=_client_ip(request),
    )
    UserAccountAuditLog.objects.create(
        actor=None,
        target_user=None,
        action="login_failed",
        changed_fields=[],
        before_data={"username": username},
        after_data={},
        notes=details,
        ip_address=_client_ip(request),
    )
    write_comprehensive_audit(
        user=None,
        username_snapshot=username,
        action="auth",
        method=getattr(request, "method", "POST") if request else "POST",
        status_code=401,
        success=False,
        screen_name="محاولة دخول فاشلة",
        view_name="login_failed",
        path=getattr(request, "path", "") if request else "",
        details=details,
        ip_address=_client_ip(request),
        user_agent=(getattr(request, "META", {}) or {}).get("HTTP_USER_AGENT", ""),
        session_key=getattr(getattr(request, "session", None), "session_key", "") if request else "",
    )


@receiver(pre_save, sender=UserAccessProfile)
def cache_previous_role_before_profile_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_role_code = None
        return

    old = UserAccessProfile.objects.filter(pk=instance.pk).only("role_code").first()
    instance._previous_role_code = old.role_code if old else None


@receiver(post_save, sender=UserAccessProfile)
def audit_role_change_after_profile_save(sender, instance, created, **kwargs):
    old_role = getattr(instance, "_previous_role_code", None)
    new_role = instance.role_code

    if created:
        return

    if old_role != new_role:
        UserAccountAuditLog.objects.create(
            actor=None,
            target_user=instance.user,
            action="role_changed",
            changed_fields=["role_code"],
            before_data={"role_code": old_role},
            after_data={"role_code": new_role},
            notes=build_role_change_note(old_role, new_role),
            ip_address=None,
        )
