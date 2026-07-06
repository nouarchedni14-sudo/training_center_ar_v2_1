from django.urls import path

from . import api
from . import central_views

urlpatterns = [
    path("devices/register/", api.device_register, name="device_register_api"),
    path("devices/config/", api.device_config, name="device_config_api"),
    path("sync/status/", api.sync_status, name="sync_status_api"),
    path("sync/push/", api.sync_push, name="sync_push_api"),
    path("sync/pull/", api.sync_pull, name="sync_pull_api"),
    path("audit/export/", api.audit_export, name="audit_export_api"),
    path("license/check/", api.license_check, name="license_check_api"),
    path("updates/check/", api.updates_check, name="updates_check_api"),
    path("updates/download/<int:pk>/", api.updates_download, name="updates_download_api"),

    # لوحة المطور المركزية - المرحلة 7
    path("central/dashboard/", central_views.central_dashboard, name="central_dashboard"),
    path("central/offices/", central_views.central_offices, name="central_offices"),
    path("central/devices/", central_views.central_devices, name="central_devices"),
    path("central/devices/<int:pk>/approve/", central_views.central_device_approve, name="central_device_approve"),
    path("central/devices/<int:pk>/reject/", central_views.central_device_reject, name="central_device_reject"),
    path("central/devices/<int:pk>/delete/", central_views.central_device_delete, name="central_device_delete"),
    path("central/offices/new/", central_views.central_office_new, name="central_office_new"),
    path("central/offices/cleanup-orphan-users/", central_views.central_cleanup_orphan_office_users, name="central_cleanup_orphan_office_users"),
    path("central/offices/users/new/", central_views.central_office_user_new, name="central_office_user_new"),
    path("central/trainee-manager/", central_views.central_trainee_manager_picker, name="central_trainee_manager_picker"),
    path("central/offices/<int:pk>/open/", central_views.central_office_open, name="central_office_open"),
    path("central/offices/<int:pk>/sync-now/", central_views.central_office_sync_now, name="central_office_sync_now"),
    path("central/offices/<int:pk>/pull-audit/", central_views.central_office_pull_audit, name="central_office_pull_audit"),
    path("central/offices/<int:pk>/delete/", central_views.central_office_delete, name="central_office_delete"),
    path("central/offices/<int:pk>/root-delete/", central_views.central_office_root_delete, name="central_office_root_delete"),
    path("central/offices/<int:pk>/users/", central_views.central_office_users, name="central_office_users"),
    path("central/offices/<int:pk>/users/<str:username>/edit/", central_views.central_office_user_edit, name="central_office_user_edit"),
    path("central/offices/<int:pk>/", central_views.central_office_edit, name="central_office_edit"),
    path("central/updates/", central_views.central_updates, name="central_updates"),
    path("central/updates/new/", central_views.central_update_edit, name="central_update_new"),
    path("central/updates/<int:pk>/", central_views.central_update_edit, name="central_update_edit"),
]
