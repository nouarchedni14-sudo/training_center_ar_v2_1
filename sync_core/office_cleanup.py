"""تنظيف مستخدمي المكاتب المركزية عند حذف المكاتب.

الهدف من هذا الملف أن تكون قاعدة الحذف واحدة سواء تم حذف المكتب من:
- صفحة إدارة المكاتب المركزية /api/central/offices/
- Django Admin
- أي كود آخر يستدعي office.delete()
"""
from __future__ import annotations

import os
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import CentralOffice, CentralSyncEvent


USER_EVENT_FILTER = {
    "app_label": "auth",
    "model_name": "User",
    "operation": "provision_user",
}


def event_target_office_id(event: CentralSyncEvent) -> str:
    """قراءة المكتب الهدف من extra أو payload لدعم السجلات القديمة والجديدة."""
    extra = event.extra or {}
    payload = event.payload or {}
    return str(extra.get("target_office_id") or payload.get("target_office_id") or "").strip()


def _all_user_provision_events(*, include_deleted: bool = False):
    qs = CentralSyncEvent.objects.filter(**USER_EVENT_FILTER)
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    return qs


def _office_provision_user_events(office_id: str, *, include_deleted: bool = True):
    """كل أحداث إرسال المستخدمين المرتبطة بمكتب معيّن.

    نستعمل extra__target_office_id و payload__target_office_id معًا لأن بعض
    النسخ القديمة كانت تحفظ المكتب الهدف داخل payload فقط.
    """
    office_id = str(office_id or "").strip()
    if not office_id:
        return CentralSyncEvent.objects.none()
    qs = CentralSyncEvent.objects.filter(**USER_EVENT_FILTER).filter(
        Q(extra__target_office_id=office_id) | Q(payload__target_office_id=office_id)
    )
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    return qs


def _usernames_in_provision_events(events: Iterable[CentralSyncEvent]) -> set[str]:
    usernames: set[str] = set()
    for event in events:
        payload = event.payload or {}
        username = str(payload.get("username") or event.object_pk or "").strip()
        if username:
            usernames.add(username)
    return usernames


def _setting_or_env(name: str, default: str = "") -> str:
    """قراءة القيمة من Django settings ثم من .env/البيئة."""
    value = getattr(settings, name, None)
    if value is None or str(value).strip() == "":
        value = os.getenv(name, default)
    return str(value or default).strip()


def _protected_central_usernames() -> set[str]:
    """أسماء حسابات الإدارة المركزية الثابتة التي لا تُحذف.

    ملاحظة مهمة:
    ensure_developer.py يستعمل DEV_USERNAME من ملف .env، وإذا لم توجد يستعمل
    الاسم الافتراضي developer. لذلك لا نكتفي بـ settings.DEV_USERNAME فقط.
    """
    protected = {"admin", "developer"}

    for value in (
        getattr(settings, "DEV_USERNAME", ""),
        os.getenv("DEV_USERNAME", ""),
        _setting_or_env("DEV_USERNAME", "developer"),
    ):
        username = str(value or "").strip()
        if username:
            protected.add(username)
    return protected


def _protected_developer_emails() -> set[str]:
    emails = {"developer@local.test"}
    for value in (
        getattr(settings, "DEV_EMAIL", ""),
        os.getenv("DEV_EMAIL", ""),
        _setting_or_env("DEV_EMAIL", "developer@local.test"),
    ):
        email = str(value or "").strip().lower()
        if email:
            emails.add(email)
    return emails


def _is_developer_superuser(user) -> bool:
    """تمييز حساب المطور الثابت حتى لا يحذفه حذف المكاتب أو زر التنظيف."""
    if not user or not getattr(user, "is_superuser", False):
        return False
    username = str(getattr(user, "username", "") or "").strip()
    email = str(getattr(user, "email", "") or "").strip().lower()
    return username in _protected_central_usernames() or (email and email in _protected_developer_emails())


def _is_permanently_protected_central_user(user) -> bool:
    """حسابات لا تُحذف إطلاقًا من تنظيف مستخدمي المكاتب."""
    if not user:
        return True
    username = str(getattr(user, "username", "") or "").strip()
    return username == "admin" or _is_developer_superuser(user)


def _is_protected_central_user(user, *, provisioned_usernames: set[str] | None = None) -> bool:
    if not user:
        return True

    # حساب المطور superuser لا يُحذف حتى لو ظهر بالخطأ ضمن أحداث مكتب.
    if _is_permanently_protected_central_user(user):
        return True

    is_office_user = provisioned_usernames is not None and user.username in provisioned_usernames
    # المطلوب: أي مستخدم تابع لمكتب يُحذف عند حذف مكتبه حتى لو كان superuser/staff.
    # الاستثناء الوحيد هنا هو حساب المطور الثابت وحساب admin.
    if is_office_user:
        return False

    # نحمي حسابات الإدارة المركزية التي لم تُنشأ أصلًا كمستخدمين لمكتب.
    if user.is_superuser:
        return True
    if user.is_staff:
        return True
    return False


def _valid_office_user_events(valid_office_ids: set[str] | None = None):
    if valid_office_ids is None:
        valid_office_ids = set(CentralOffice.objects.values_list("office_id", flat=True))
    return [
        event for event in _all_user_provision_events(include_deleted=False)
        if event_target_office_id(event) in valid_office_ids
    ]


def _delete_central_users_if_only_linked_to_office(usernames: set[str], office_id: str) -> int:
    """حذف مستخدمي المكتب إذا لم يعودوا مرتبطين بمكتب آخر موجود."""
    office_id = str(office_id or "").strip()
    if not usernames or not office_id:
        return 0

    existing_other_office_ids = set(
        CentralOffice.objects.exclude(office_id=office_id).values_list("office_id", flat=True)
    )
    usernames_used_elsewhere = _usernames_in_provision_events(
        event for event in _all_user_provision_events(include_deleted=False)
        if event_target_office_id(event) in existing_other_office_ids
    )
    provisioned_usernames = _usernames_in_provision_events(_all_user_provision_events(include_deleted=True))

    User = get_user_model()
    deleted = 0
    for username in sorted(usernames):
        if username in usernames_used_elsewhere:
            continue
        user = User.objects.filter(username=username).first()
        if _is_protected_central_user(user, provisioned_usernames=provisioned_usernames):
            continue
        user.delete()
        deleted += 1
    return deleted


def cleanup_users_for_office_delete(office_id: str) -> tuple[int, int]:
    """تنظيف مستخدمي مكتب واحد قبل/بعد حذف المكتب.

    Returns: (deleted_users, deleted_user_events)
    """
    office_id = str(office_id or "").strip()
    if not office_id:
        return 0, 0

    events = list(_office_provision_user_events(office_id, include_deleted=True))
    usernames = _usernames_in_provision_events(events)
    deleted_users = _delete_central_users_if_only_linked_to_office(usernames, office_id)

    deleted_events = 0
    if events:
        ids = [event.id for event in events]
        deleted_events, _ = CentralSyncEvent.objects.filter(id__in=ids).delete()
    return deleted_users, deleted_events


def _cleanup_orphan_office_users() -> tuple[int, int, int]:
    """تنظيف المستخدمين/الأحداث التي تشير إلى مكاتب محذوفة.

    ينظف حالتين:
    1) أحداث إرسال مستخدمين مرتبطة بمكاتب لم تعد موجودة.
    2) مستخدمون ظاهرون في جدول إدارة المستخدمين ولا يملكون أي ارتباط بمكتب موجود.

    Returns: (deleted_users, deleted_events, orphan_offices_count)
    """
    valid_office_ids = set(CentralOffice.objects.values_list("office_id", flat=True))
    all_events = list(_all_user_provision_events(include_deleted=False))
    orphan_events: list[CentralSyncEvent] = []
    orphan_office_ids: set[str] = set()
    valid_events: list[CentralSyncEvent] = []

    for event in all_events:
        office_id = event_target_office_id(event)
        if office_id and office_id in valid_office_ids:
            valid_events.append(event)
        elif office_id:
            orphan_events.append(event)
            orphan_office_ids.add(office_id)

    usernames_used_by_existing_offices = _usernames_in_provision_events(valid_events)
    candidate_usernames = _usernames_in_provision_events(orphan_events)

    User = get_user_model()
    for user in User.objects.all():
        # زر التنظيف اليدوي مخصص لإزالة أي حساب لا يعود مرتبطًا بمكتب صالح،
        # ويشمل ذلك الحسابات التي بقيت من إصدارات سابقة حتى لو كانت superuser.
        # لكن حساب المطور superuser وحساب admin لا يُحذفان إطلاقًا.
        if _is_permanently_protected_central_user(user):
            continue
        if user.username not in usernames_used_by_existing_offices:
            candidate_usernames.add(user.username)

    deleted_users = 0
    for username in sorted(candidate_usernames - usernames_used_by_existing_offices):
        user = User.objects.filter(username=username).first()
        if not user or _is_permanently_protected_central_user(user):
            continue
        user.delete()
        deleted_users += 1

    deleted_events = 0
    if orphan_events:
        ids = [event.id for event in orphan_events]
        deleted_events, _ = CentralSyncEvent.objects.filter(id__in=ids).delete()

    return deleted_users, deleted_events, len(orphan_office_ids)
