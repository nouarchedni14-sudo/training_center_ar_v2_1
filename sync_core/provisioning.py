"""Helpers for provisioning users from the central server to local offices.

This module intentionally has no migrations. It stores provisioning requests as
CentralSyncEvent records directed to a target office. Local offices apply those
requests through sync_core.applier.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model

from .models import CentralOffice, CentralSyncEvent


DEFAULT_ROLE = "registration_officer"


def permissions_from_user_and_cleaned(user, cleaned: dict[str, Any]) -> dict[str, Any]:
    """Build the permission payload from the single source of truth: UserAccessProfile.

    The central edit page no longer repeats local-office permission checkboxes.
    Permissions are read from the inline "صلاحيات المستخدم" section when it exists.
    """
    profile = getattr(user, "access_profile", None)
    if profile:
        return {
            "role_code": getattr(profile, "role_code", None) or DEFAULT_ROLE,
            "can_admin_panel": bool(getattr(profile, "can_access_admin_panel", False) or getattr(user, "is_staff", False)),
            "can_manage_all_programs": bool(getattr(profile, "can_manage_all_programs", False)),
            "can_view_reports": bool(getattr(profile, "can_view_reports", False)),
            "can_export_data": bool(getattr(profile, "can_export_data", False)),
            "force_password_change": bool(getattr(profile, "force_password_change", False)),
            "access_enabled": bool(getattr(profile, "access_enabled", True)),
            "access_start_date": str(getattr(profile, "access_start_date", "") or ""),
            "access_end_date": str(getattr(profile, "access_end_date", "") or ""),
            "can_initial": bool(getattr(profile, "initial_view", False)),
            "can_apprentice": bool(getattr(profile, "apprentice_view", False)),
            "can_evening": bool(getattr(profile, "evening_view", False)),
            "initial_view": bool(getattr(profile, "initial_view", False)),
            "initial_add": bool(getattr(profile, "initial_add", False)),
            "initial_change": bool(getattr(profile, "initial_change", False)),
            "initial_delete": bool(getattr(profile, "initial_delete", False)),
            "apprentice_view": bool(getattr(profile, "apprentice_view", False)),
            "apprentice_add": bool(getattr(profile, "apprentice_add", False)),
            "apprentice_change": bool(getattr(profile, "apprentice_change", False)),
            "apprentice_delete": bool(getattr(profile, "apprentice_delete", False)),
            "evening_view": bool(getattr(profile, "evening_view", False)),
            "evening_add": bool(getattr(profile, "evening_add", False)),
            "evening_change": bool(getattr(profile, "evening_change", False)),
            "evening_delete": bool(getattr(profile, "evening_delete", False)),
            # legacy compact keys kept for older local appliers
            "can_add": bool(getattr(profile, "initial_add", False) or getattr(profile, "apprentice_add", False) or getattr(profile, "evening_add", False)),
            "can_edit": bool(getattr(profile, "initial_change", False) or getattr(profile, "apprentice_change", False) or getattr(profile, "evening_change", False)),
            "can_delete": bool(getattr(profile, "initial_delete", False) or getattr(profile, "apprentice_delete", False) or getattr(profile, "evening_delete", False)),
            "can_export": bool(getattr(profile, "can_export_data", False)),
        }

    return {
        "role_code": cleaned.get("role_code") or DEFAULT_ROLE,
        "can_initial": bool(cleaned.get("can_initial", True)),
        "can_apprentice": bool(cleaned.get("can_apprentice", True)),
        "can_evening": bool(cleaned.get("can_evening", True)),
        "can_add": bool(cleaned.get("can_add", True)),
        "can_edit": bool(cleaned.get("can_edit", True)),
        "can_delete": bool(cleaned.get("can_delete", False)),
        "can_export": bool(cleaned.get("can_export", True)),
        "can_admin_panel": bool(cleaned.get("can_admin_panel") or cleaned.get("is_staff")),
    }


def payload_from_user_and_cleaned(user, cleaned: dict[str, Any], target_office: CentralOffice) -> dict[str, Any]:
    password = cleaned.get("password") or cleaned.get("password1") or ""
    permissions = permissions_from_user_and_cleaned(user, cleaned)
    return {
        "target_office_id": target_office.office_id,
        "username": user.username,
        "password": password,
        "email": getattr(user, "email", "") or cleaned.get("email") or "",
        "first_name": getattr(user, "first_name", "") or cleaned.get("first_name") or "",
        "last_name": getattr(user, "last_name", "") or cleaned.get("last_name") or "",
        "is_active": bool(getattr(user, "is_active", cleaned.get("is_active", True))),
        # دخول /admin/ في المكتب المحلي يأتي من صلاحيات المستخدم فقط، وليس من حقل مكرر في نموذج الإرسال.
        "is_staff": bool(permissions.get("can_admin_panel")),
        "is_superuser": False,
        "permissions": permissions,
        "notes": cleaned.get("notes") or "",
    }


def create_or_update_central_user(*, username: str, password: str = "", email: str = "", first_name: str = "", last_name: str = "", is_active: bool = True, is_staff: bool = False, is_superuser: bool = False):
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=username)
    user.email = email or ""
    user.first_name = first_name or ""
    user.last_name = last_name or ""
    user.is_active = bool(is_active)
    user.is_staff = bool(is_staff)
    user.is_superuser = bool(is_superuser)
    if password:
        user.set_password(password)
    user.save()
    return user


def create_user_provision_event(*, target_office: CentralOffice, user, payload: dict[str, Any], kind: str = "user_provision", changed_fields: list[str] | None = None) -> CentralSyncEvent:
    """Create a central event targeted to one local office."""
    changed_fields = changed_fields or list(payload.keys())
    return CentralSyncEvent.objects.create(
        source_event_id=uuid.uuid4(),
        source_office_id="__central__",
        source_server_id="central-server",
        app_label="auth",
        model_name="User",
        object_pk=getattr(user, "username", payload.get("username", "")),
        operation="provision_user",
        payload=payload,
        changed_fields=changed_fields,
        extra={"target_office_id": target_office.office_id, "kind": kind},
    )


def latest_user_payloads_for_office(office: CentralOffice) -> dict[str, dict[str, Any]]:
    """Return latest provisioning payload per username for a given office."""
    events = (
        CentralSyncEvent.objects
        .filter(app_label="auth", model_name="User", operation="provision_user", is_deleted=False, extra__target_office_id=office.office_id)
        .order_by("id")
    )
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event.payload or {}
        username = str(payload.get("username") or event.object_pk or "").strip()
        if not username:
            continue
        result[username] = {"event": event, "payload": payload}
    return result
