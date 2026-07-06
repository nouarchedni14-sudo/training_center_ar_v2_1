from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Max, Q
from django.utils import timezone

from trainees.models import ActivityLog, UserAccessProfile, UserAccountAuditLog


@dataclass
class AccountActivityEntry:
    timestamp: object
    source: str
    action: str
    action_label: str
    username: str
    actor_name: str
    ip_address: str
    details: str
    changed_fields: list


def roles_summary(role_code: str = ""):
    queryset = UserAccessProfile.objects.select_related("user")
    if role_code:
        queryset = queryset.filter(role_code=role_code)

    rows = []
    for item in (
        queryset.values("role_code")
        .annotate(
            total=Count("id"),
            active=Count("id", filter=Q(access_enabled=True)),
            inactive=Count("id", filter=Q(access_enabled=False)),
            customized=Count("id", filter=Q(is_customized=True)),
            expiring=Count(
                "id",
                filter=Q(
                    access_enabled=True,
                    access_end_date__isnull=False,
                    access_end_date__gte=timezone.localdate(),
                ),
            ),
            latest_update=Max("updated_at"),
        )
        .order_by("role_code")
    ):
        rows.append(
            {
                "role_code": item["role_code"],
                "role_label": dict(UserAccessProfile.ROLE_CODE_CHOICES).get(item["role_code"], item["role_code"] or "—"),
                "total": item["total"],
                "active": item["active"],
                "inactive": item["inactive"],
                "customized": item["customized"],
                "expiring": item["expiring"],
                "latest_update": item["latest_update"],
            }
        )
    return rows


def expiring_profiles(days: int = 7, role_code: str = "", state: str = "", search: str = ""):
    today = timezone.localdate()
    limit = today + timedelta(days=max(1, int(days or 7)))
    queryset = UserAccessProfile.objects.select_related("user").filter(
        access_end_date__isnull=False,
        access_end_date__gte=today,
        access_end_date__lte=limit,
    )
    if role_code:
        queryset = queryset.filter(role_code=role_code)
    if state == "enabled":
        queryset = queryset.filter(access_enabled=True)
    elif state == "disabled":
        queryset = queryset.filter(access_enabled=False)
    if search:
        queryset = queryset.filter(
            Q(user__username__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__email__icontains=search)
        )
    return queryset.order_by("access_end_date", "user__username")


def customized_profiles(role_code: str = "", search: str = "", access_state: str = ""):
    queryset = UserAccessProfile.objects.select_related("user").filter(is_customized=True)
    if role_code:
        queryset = queryset.filter(role_code=role_code)
    if access_state == "enabled":
        queryset = queryset.filter(access_enabled=True)
    elif access_state == "disabled":
        queryset = queryset.filter(access_enabled=False)
    if search:
        queryset = queryset.filter(
            Q(user__username__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__email__icontains=search)
        )
    return queryset.order_by("user__username")


def account_activity(days: int = 30, action: str = "", username: str = ""):
    since = timezone.now() - timedelta(days=max(1, int(days or 30)))
    username = (username or "").strip()

    activity_qs = ActivityLog.objects.select_related("user").filter(created_at__gte=since)
    if action:
        activity_qs = activity_qs.filter(action=action)
    if username:
        activity_qs = activity_qs.filter(user__username__icontains=username)

    audit_qs = UserAccountAuditLog.objects.select_related("actor", "target_user").filter(created_at__gte=since)
    if action:
        audit_qs = audit_qs.filter(action=action)
    if username:
        audit_qs = audit_qs.filter(
            Q(target_user__username__icontains=username) | Q(actor__username__icontains=username)
        )

    entries = []
    for item in activity_qs[:200]:
        entries.append(
            AccountActivityEntry(
                timestamp=item.created_at,
                source="activity",
                action=item.action,
                action_label=item.get_action_display(),
                username=item.user.username if item.user else "غير معروف",
                actor_name=(item.user.get_full_name() or item.user.username) if item.user else "غير معروف",
                ip_address=item.ip_address or "—",
                details=item.details or item.object_repr or item.path or "—",
                changed_fields=[],
            )
        )

    for item in audit_qs[:200]:
        target = item.target_user.username if item.target_user else "غير معروف"
        actor = (item.actor.get_full_name() or item.actor.username) if item.actor else "غير معروف"
        entries.append(
            AccountActivityEntry(
                timestamp=item.created_at,
                source="audit",
                action=item.action,
                action_label=item.get_action_display(),
                username=target,
                actor_name=actor,
                ip_address=item.ip_address or "—",
                details=item.notes or "—",
                changed_fields=item.changed_fields or [],
            )
        )

    entries.sort(key=lambda item: item.timestamp, reverse=True)
    return entries[:250]


def role_choices_for_filters():
    return list(UserAccessProfile.ROLE_CODE_CHOICES)
