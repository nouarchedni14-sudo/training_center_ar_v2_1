from trainees.roles import DEFAULT_ROLE_CODE, get_role_label, get_role_permissions

PERMISSION_FIELDS = [
    "can_access_admin_panel",
    "can_manage_all_programs",
    "initial_view",
    "initial_add",
    "initial_change",
    "initial_delete",
    "apprentice_view",
    "apprentice_add",
    "apprentice_change",
    "apprentice_delete",
    "evening_view",
    "evening_add",
    "evening_change",
    "evening_delete",
    "can_view_reports",
    "can_export_data",
    "force_password_change",
]


def normalize_role_code(role_code):
    return role_code or DEFAULT_ROLE_CODE


def get_default_permissions_for_role(role_code):
    return get_role_permissions(normalize_role_code(role_code))


def apply_role_defaults(profile):
    profile.role_code = normalize_role_code(profile.role_code)
    defaults = get_default_permissions_for_role(profile.role_code)
    for field_name in PERMISSION_FIELDS:
        setattr(profile, field_name, defaults.get(field_name, False))
    profile.is_customized = False


def profile_permissions_snapshot(profile):
    return {field_name: getattr(profile, field_name, False) for field_name in PERMISSION_FIELDS}


def role_defaults_snapshot(role_code):
    defaults = get_default_permissions_for_role(role_code)
    return {field_name: defaults.get(field_name, False) for field_name in PERMISSION_FIELDS}


def is_profile_customized_against_role(profile):
    return profile_permissions_snapshot(profile) != role_defaults_snapshot(profile.role_code)


def changed_permission_fields(before, after):
    changed = []
    for field_name in PERMISSION_FIELDS:
        if before.get(field_name) != after.get(field_name):
            changed.append(field_name)
    return changed


def build_role_change_note(old_role, new_role):
    old_label = get_role_label(old_role)
    new_label = get_role_label(new_role)
    return f"تم تغيير الدور من '{old_label}' إلى '{new_label}'."
