from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

PROGRAMS = ("initial", "apprentice", "evening", "crossing")
PROGRAM_LABELS = {
    "initial": "الحضوري الأولي",
    "apprentice": "التمهين",
    "evening": "الدروس المسائية",
    "crossing": "المعابر",
}

# المعابر تستعمل نفس حقول صلاحيات المسائي في UserAccessProfile،
# لكن تظهر في الواجهة كقسم مستقل.
PERMISSION_PROGRAM_ALIASES = {"crossing": "evening"}
ACTION_TO_FIELD = {
    "view": "view",
    "add": "add",
    "change": "change",
    "delete": "delete",
    "export": "view",
    "reports": "view",
}


def get_profile(user):
    if not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.access_profile
    except Exception:
        from .models import UserAccessProfile
        profile, _ = UserAccessProfile.objects.get_or_create(user=user)
        return profile


def can_manage_users(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    profile = get_profile(user)
    return bool(profile and (profile.can_access_admin_panel or profile.can_manage_all_programs))


def is_access_within_schedule(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", False):
        return False
    if user.is_superuser:
        return True
    profile = get_profile(user)
    return bool(profile and profile.has_active_access())


def get_access_denied_message(user):
    if not getattr(user, "is_authenticated", False):
        return "يجب تسجيل الدخول أولاً."
    if not getattr(user, "is_active", False):
        return "هذا الحساب غير مفعّل."
    if user.is_superuser:
        return "الصلاحيات مفعلة."
    profile = get_profile(user)
    if not profile:
        return "لا توجد صلاحيات معرفة لهذا المستخدم."
    return profile.access_status_message()


def can_access_admin_panel(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if not is_access_within_schedule(user):
        return False
    profile = get_profile(user)
    return bool(profile and (profile.can_access_admin_panel or profile.can_manage_all_programs))


def has_program_permission(user, program, action="view"):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if not is_access_within_schedule(user):
        return False
    profile = get_profile(user)
    if not profile:
        return False
    if profile.can_manage_all_programs:
        return True
    suffix = ACTION_TO_FIELD.get(action, action)
    permission_program = PERMISSION_PROGRAM_ALIASES.get(program, program)
    field_name = f"{permission_program}_{suffix}"
    return bool(getattr(profile, field_name, False))


def visible_programs(user):
    return [code for code in PROGRAMS if has_program_permission(user, code, "view")]


def require_program_permission(request, program, action="view"):
    if has_program_permission(request.user, program, action):
        return
    if not is_access_within_schedule(request.user):
        raise PermissionDenied(get_access_denied_message(request.user))
    raise PermissionDenied("غير مصرح لك بالوصول إلى هذا القسم")


def in_group(*group_names):
    def check(user):
        return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=group_names).exists())
    return user_passes_test(check)



def build_access_summary(user):
    """تلخيص حالة الوصول الحالية في قاموس واحد ليستعمل في القوالب والواجهات."""
    summary = {
        "state": "anonymous",
        "state_label": "غير مسجل الدخول",
        "message": "يجب تسجيل الدخول أولاً.",
        "allowed_programs": [],
        "can_access_admin": False,
        "can_view_reports": False,
        "can_export_data": False,
        "window_label": "—",
        "daily_window": "—",
        "allowed_weekdays": "—",
        "access_type": "—",
        "days_until_expiry": None,
        "permission_labels": [],
    }
    if not getattr(user, "is_authenticated", False):
        return summary
    if user.is_superuser:
        summary.update({
            "state": "superuser",
            "state_label": "صلاحية كاملة",
            "message": "هذا الحساب يملك كل الصلاحيات بصفته مديرًا عامًا.",
            "allowed_programs": ["الحضوري الأولي", "التمهين", "الدروس المسائية", "المعابر"],
            "can_access_admin": True,
            "can_view_reports": True,
            "can_export_data": True,
            "window_label": "بدون قيود زمنية",
            "daily_window": "بدون قيود زمنية",
            "allowed_weekdays": "كل الأيام",
            "access_type": "مدير النظام",
            "permission_labels": ["إدارة كاملة", "لوحة الإدارة", "التقارير", "التصدير"],
        })
        return summary

    profile = get_profile(user)
    if not profile:
        summary.update({
            "state": "missing",
            "state_label": "بدون ملف صلاحيات",
            "message": "لا يوجد ملف صلاحيات مرتبط بهذا المستخدم بعد.",
        })
        return summary

    allowed_programs = profile.granted_programs()
    permission_labels = []
    if profile.can_access_admin_panel:
        permission_labels.append("لوحة الإدارة")
    if profile.can_manage_all_programs:
        permission_labels.append("إدارة كل الأنماط")
    if profile.can_view_reports:
        permission_labels.append("التقارير")
    if profile.can_export_data:
        permission_labels.append("التصدير")

    summary.update({
        "state": profile.get_access_state(),
        "state_label": profile.get_access_state_label(),
        "message": profile.access_status_message(),
        "allowed_programs": allowed_programs,
        "can_access_admin": bool(profile.can_access_admin_panel or profile.can_manage_all_programs),
        "can_view_reports": bool(profile.can_view_reports),
        "can_export_data": bool(profile.can_export_data),
        "window_label": profile.access_window_label(),
        "daily_window": profile.current_daily_window_label(),
        "allowed_weekdays": profile.allowed_weekdays_display(),
        "access_type": profile.get_access_type_display(),
        "days_until_expiry": profile.days_until_expiry(),
        "permission_labels": permission_labels,
    })
    return summary
