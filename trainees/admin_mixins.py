from django.contrib import admin

from .permissions import can_access_admin_panel


class AdminPanelPermissionMixin:
    """يوحد منطق صلاحيات لوحة الإدارة في مكان واحد."""

    delete_requires_superuser = False

    def _can_admin(self, request):
        return can_access_admin_panel(request.user)

    def has_module_permission(self, request):
        return self._can_admin(request)

    def has_view_permission(self, request, obj=None):
        return self._can_admin(request)

    def has_add_permission(self, request):
        return self._can_admin(request)

    def has_change_permission(self, request, obj=None):
        return self._can_admin(request)

    def has_delete_permission(self, request, obj=None):
        if self.delete_requires_superuser:
            return self._can_admin(request) and request.user.is_superuser
        return self._can_admin(request)


class SuperuserOnlyAdminMixin:
    """يوحد صلاحيات إدارة المستخدمين لتبقى محصورة بالمدير العام."""

    def _is_admin_manager(self, request):
        user = request.user
        return bool(user.is_active and user.is_superuser)

    def has_module_permission(self, request):
        return self._is_admin_manager(request)

    def has_view_permission(self, request, obj=None):
        return self._is_admin_manager(request)

    def has_add_permission(self, request):
        return self._is_admin_manager(request)

    def has_change_permission(self, request, obj=None):
        return self._is_admin_manager(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_admin_manager(request)


def _admin_status_label_fallback(obj):
    raw = getattr(obj, "الحالة", "")
    return "حالي" if raw not in {"مشطوب", "منقطع", "removed"} else "مشطوب"


class BaseProgramAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    """إعدادات الإدارة المشتركة بين أنماط المتكوّنين الثلاثة."""

    list_display = ()
    search_fields = ()
    list_filter = ()
    ordering = ("الدفعة__السنة", "الدفعة__رقم_الدورة", "اللقب", "الاسم")

    def تصنيف_الحالة(self, obj):
        return _admin_status_label_fallback(obj)

    تصنيف_الحالة.short_description = "تصنيف الحالة"

    def الدفعة_الحالية(self, obj):
        return str(obj.الدفعة) if getattr(obj, "الدفعة", None) else ""

    الدفعة_الحالية.short_description = "الدفعة"

    def تاريخ_الميلاد_رقمي(self, obj):
        from .admin import _fmt_date
        return _fmt_date(obj, "تاريخ_الميلاد")

    تاريخ_الميلاد_رقمي.short_description = "تاريخ الميلاد"

    def تاريخ_بداية_التكوين_رقمي(self, obj):
        from .admin import _fmt_date
        return _fmt_date(obj, "تاريخ_بداية_التكوين")

    تاريخ_بداية_التكوين_رقمي.short_description = "تاريخ بداية التكوين"

    def تاريخ_نهاية_التكوين_رقمي(self, obj):
        from .admin import _fmt_date
        return _fmt_date(obj, "تاريخ_نهاية_التكوين")

    تاريخ_نهاية_التكوين_رقمي.short_description = "تاريخ نهاية التكوين"

    class Media:
        css = {"all": ("admin/custom_admin.css",)}
        js = ("admin/custom_admin_tables.js", "admin/admin_row_status.js")
