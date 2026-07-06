from django.urls import path

from core.views import (
    system_backup_download,
    system_backup_download_prepare,
    system_backup_view,
    system_dashboard_view,
    system_health_view,
    system_license_view,
    system_local_update_script_download,
    system_local_update_view,
    system_settings_view,
    system_start_pending_update,
    system_finalize_update_shutdown,
    system_updates_view,
    healthz_view,
    readyz_view,
)

urlpatterns = [
    path("healthz/", healthz_view, name="healthz"),
    path("readyz/", readyz_view, name="readyz"),
    path("", system_dashboard_view, name="system_dashboard"),
    path("settings/", system_settings_view, name="system_settings"),
    path("health/", system_health_view, name="system_health"),
    path("backups/", system_backup_view, name="system_backup"),
    path("backups/<str:filename>/download/", system_backup_download, name="system_backup_download"),
    path("backups/<str:filename>/download/prepare/", system_backup_download_prepare, name="system_backup_download_prepare"),
    path("license/", system_license_view, name="system_license"),
    path("updates/", system_updates_view, name="system_updates"),
    path("local-update/", system_local_update_view, name="system_local_update"),
    path("local-update/script/", system_local_update_script_download, name="system_local_update_script"),
    path("updates/start/", system_start_pending_update, name="system_start_pending_update"),
    path("updates/finalize-shutdown/", system_finalize_update_shutdown, name="system_finalize_update_shutdown"),
]
