from __future__ import annotations

ACCESS_PROFILE_AUDIT_FIELDS = [
    ("access_enabled", "تفعيل الصلاحيات"),
    ("access_start_date", "تاريخ بداية الصلاحية"),
    ("access_end_date", "تاريخ نهاية الصلاحية"),
    ("can_access_admin_panel", "دخول لوحة الإدارة"),
    ("can_manage_all_programs", "إدارة كل الأنماط"),
    ("initial_view", "الحضوري: عرض"),
    ("initial_add", "الحضوري: إضافة"),
    ("initial_change", "الحضوري: تعديل"),
    ("initial_delete", "الحضوري: حذف"),
    ("apprentice_view", "التمهين: عرض"),
    ("apprentice_add", "التمهين: إضافة"),
    ("apprentice_change", "التمهين: تعديل"),
    ("apprentice_delete", "التمهين: حذف"),
    ("evening_view", "المسائي: عرض"),
    ("evening_add", "المسائي: إضافة"),
    ("evening_change", "المسائي: تعديل"),
    ("evening_delete", "المسائي: حذف"),
    ("can_view_reports", "عرض التقارير"),
    ("can_export_data", "تصدير البيانات"),
    ("force_password_change", "إجبار تغيير كلمة المرور"),
]

ACCESS_PROFILE_AUDIT_LABELS = {field: label for field, label in ACCESS_PROFILE_AUDIT_FIELDS}


def get_access_audit_field_label(field_name):
    return ACCESS_PROFILE_AUDIT_LABELS.get(field_name, field_name)


def get_access_audit_field_labels(field_names):
    return [get_access_audit_field_label(field_name) for field_name in (field_names or [])]


def serialize_access_profile_for_audit(profile):
    if not profile:
        return {}
    data = {}
    for field_name, _label in ACCESS_PROFILE_AUDIT_FIELDS:
        value = getattr(profile, field_name, None)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        data[field_name] = value
    data["access_state"] = profile.access_state_label()
    data["access_window"] = profile.access_window_label()
    data["programs"] = profile.granted_program_labels()
    return data


def diff_access_snapshots(before, after):
    before = before or {}
    after = after or {}
    changed = []
    for field_name, _label in ACCESS_PROFILE_AUDIT_FIELDS:
        if before.get(field_name) != after.get(field_name):
            changed.append(field_name)
    return changed
