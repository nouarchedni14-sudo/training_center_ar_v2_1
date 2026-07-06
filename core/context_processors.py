from django.conf import settings
from core.models import SystemConfiguration


def _perm(user, code):
    return bool(getattr(user, "is_authenticated", False) and (getattr(user, "is_superuser", False) or user.has_perm(code)))


def system_status(request):
    config = None
    try:
        config = SystemConfiguration.get_solo()
    except Exception:  # noqa: BLE001
        return {
            "system_configuration": None,
            "system_update_available": False,
            "can_view_system_settings": False,
            "can_check_system_updates": False,
            "can_view_system_health": False,
            "can_manage_license_info": False,
        }

    can_manage_settings = _perm(request.user, "core.manage_system_settings")
    can_check_updates = _perm(request.user, "core.check_system_updates")
    can_view_health = _perm(request.user, "core.view_system_health")
    can_manage_license = _perm(request.user, "core.manage_license_info")
    can_view_page = any([can_manage_settings, can_check_updates, can_view_health, can_manage_license])
    return {
        "system_configuration": config,
        "system_update_available": bool(config.update_available),
        "can_view_system_settings": can_view_page,
        "can_check_system_updates": can_check_updates,
        "can_view_system_health": can_view_health,
        "can_manage_license_info": can_manage_license,
    }



def central_navigation(request):
    """روابط مساعدة للتنقل بين برنامج المكتب المحلي ولوحة المطور المركزية.

    CENTRAL_URL مخصص للمزامنة وقد يكون عنوان الشبكة.
    زر لوحة المطور المركزية يستعمل CENTRAL_DASHBOARD_URL حتى يبقى محليًا للمطور فقط.
    """
    central_url = (getattr(settings, "CENTRAL_URL", "") or "").strip().rstrip("/")
    if not central_url:
        central_url = "http://127.0.0.1:9000"

    dashboard_url = (getattr(settings, "CENTRAL_DASHBOARD_URL", "") or "").strip()
    if not dashboard_url:
        dashboard_url = f"{central_url}/central/"

    return {
        "central_dashboard_url": dashboard_url,
        "central_offices_url": f"{central_url}/central/offices/",
        "central_api_status_url": f"{central_url}/api/sync/status/",
    }
