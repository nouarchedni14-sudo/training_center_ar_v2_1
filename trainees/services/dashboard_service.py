from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from trainees.models import ActivityLog, UserAccessProfile, UserAccountAuditLog
from trainees.roles import get_role_label


def access_status_counts():
    counts = {"active": 0, "pending": 0, "expired": 0, "disabled": 0}
    for profile in UserAccessProfile.objects.select_related("user").all():
        counts[profile.access_state_code()] = counts.get(profile.access_state_code(), 0) + 1
    return counts


def expiring_profiles(days=7, limit=8):
    today = timezone.localdate()
    qs = (
        UserAccessProfile.objects.select_related("user")
        .filter(access_enabled=True, access_end_date__isnull=False, access_end_date__gte=today)
        .order_by("access_end_date", "user__username")
    )
    items = []
    for profile in qs:
        remaining = profile.days_until_expiry(today)
        if remaining is None or remaining > days:
            continue
        items.append(profile)
        if len(items) >= limit:
            break
    return items


def recently_disabled_profiles(limit=8):
    return list(
        UserAccessProfile.objects.select_related("user")
        .filter(access_enabled=False)
        .order_by("-updated_at", "user__username")[:limit]
    )


def recent_sensitive_audits(limit=10):
    return list(
        UserAccountAuditLog.objects.select_related("actor", "target_user")
        .order_by("-created_at", "-id")[:limit]
    )


def recent_failed_logins(limit=10):
    return list(
        ActivityLog.objects.select_related("user")
        .filter(action="login_failed")
        .order_by("-created_at", "-id")[:limit]
    )


def user_role_summary():
    User = get_user_model()
    total_users = User.objects.count()
    with_profiles = UserAccessProfile.objects.count()
    role_rows = list(
        UserAccessProfile.objects.values("role_code")
        .annotate(total=Count("id"))
        .order_by("role_code")
    )
    for row in role_rows:
        row["role_label"] = get_role_label(row.get("role_code"))
    return {
        "total_users": total_users,
        "with_profiles": with_profiles,
        "without_profiles": max(total_users - with_profiles, 0),
        "role_rows": role_rows,
    }
