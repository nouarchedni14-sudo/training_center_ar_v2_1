from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.conf import settings

from core.models import LicenseInfo


LICENSE_ALLOWED_PREFIXES = (
    "/accounts/login/",
    "/admin/login/",
    "/logout/",
    "/system/license/",
    "/system/health/",
    "/media/",
    "/static/",
)


@dataclass(frozen=True)
class LicenseStatus:
    is_valid: bool
    is_expired: bool
    is_trial: bool
    is_suspended: bool
    status_code: str
    status_label: str
    days_left: int | None
    message: str
    level: str
    customer_name: str
    support_expires_at: date | None
    enforcement_required: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "is_expired": self.is_expired,
            "is_trial": self.is_trial,
            "is_suspended": self.is_suspended,
            "status_code": self.status_code,
            "status_label": self.status_label,
            "days_left": self.days_left,
            "message": self.message,
            "level": self.level,
            "customer_name": self.customer_name,
            "support_expires_at": self.support_expires_at,
            "enforcement_required": self.enforcement_required,
        }


def license_enforcement_enabled() -> bool:
    return bool(getattr(settings, "LICENSE_ENFORCEMENT_ENABLED", True))



def get_license_status(license_info: LicenseInfo | None = None, *, today: date | None = None) -> dict[str, Any]:
    license_info = license_info or LicenseInfo.get_solo()
    today = today or date.today()

    status_code = (license_info.license_status or LicenseInfo.STATUS_TRIAL).strip() or LicenseInfo.STATUS_TRIAL
    status_label = license_info.get_license_status_display() or status_code
    expires_at = license_info.support_expires_at
    days_left: int | None = None
    is_expired_by_date = False
    if expires_at:
        days_left = (expires_at - today).days
        is_expired_by_date = days_left < 0

    is_trial = status_code == LicenseInfo.STATUS_TRIAL
    is_suspended = status_code == LicenseInfo.STATUS_SUSPENDED
    is_expired = status_code == LicenseInfo.STATUS_EXPIRED or is_expired_by_date
    is_active = status_code == LicenseInfo.STATUS_ACTIVE and not is_expired_by_date
    is_valid = is_active or is_trial

    if is_suspended:
        level = "error"
        message = "الترخيص معلّق حالياً. راجع صفحة الترخيص لإعادة التفعيل."
    elif is_expired:
        level = "error"
        if expires_at:
            message = f"انتهت صلاحية الترخيص أو الدعم في {expires_at:%Y-%m-%d}."
        else:
            message = "الترخيص منتهي الصلاحية."
    elif days_left is not None and days_left <= 14:
        level = "warning"
        message = f"الترخيص أو الدعم سينتهي بعد {days_left} يومًا."
    elif is_trial:
        level = "warning"
        if days_left is not None:
            message = f"النسخة الة فعّالة، والمدة المتبقية {max(days_left, 0)} يومًا."
        else:
            message = "النسخة تعمل بوضع ."
    else:
        level = "success"
        message = "الترخيص فعّال ويمكن استخدام النظام بشكل طبيعي."

    status = LicenseStatus(
        is_valid=is_valid,
        is_expired=is_expired,
        is_trial=is_trial,
        is_suspended=is_suspended,
        status_code=status_code,
        status_label=status_label,
        days_left=days_left,
        message=message,
        level=level,
        customer_name=license_info.customer_name or "",
        support_expires_at=expires_at,
        enforcement_required=license_enforcement_enabled(),
    )
    return status.as_dict()



def request_path_is_license_exempt(path: str) -> bool:
    normalized = (path or "").strip() or "/"
    return any(normalized.startswith(prefix) for prefix in LICENSE_ALLOWED_PREFIXES)
