from django.contrib import admin

from core.models import LicenseInfo, SystemConfiguration, SystemErrorLog, SystemHealthLog, UpdateCheckLog


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "organization_name",
        "installation_id",
        "app_mode",
        "current_version",
        "latest_version",
        "update_available",
        "last_update_check_at",
    )
    readonly_fields = ("installation_id", "last_update_check_at", "created_at", "updated_at")


@admin.register(LicenseInfo)
class LicenseInfoAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "license_code", "license_status", "support_expires_at", "max_devices")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UpdateCheckLog)
class UpdateCheckLogAdmin(admin.ModelAdmin):
    list_display = ("checked_at", "success", "requested_version", "received_version")
    readonly_fields = ("checked_at",)


@admin.register(SystemHealthLog)
class SystemHealthLogAdmin(admin.ModelAdmin):
    list_display = ("checked_at", "component", "level", "message")
    readonly_fields = ("checked_at",)
    list_filter = ("level", "component")


@admin.register(SystemErrorLog)
class SystemErrorLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source", "error_type", "user_display", "resolved")
    readonly_fields = ("created_at",)
    list_filter = ("resolved", "source", "error_type")
