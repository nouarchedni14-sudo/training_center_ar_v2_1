from datetime import timedelta
import csv

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserChangeForm
from django.contrib.auth.models import Group, User
from django.db.models import Case, IntegerField, Value, When
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .forms import UserAccessProfileAdminForm
from .models import (
    ACCESS_PROFILE_AUDIT_LABELS,
    AccessAuditLog,
    UserAccessProfile,
    diff_access_snapshots,
    get_access_audit_field_labels,
    serialize_access_profile_for_audit,
)
from .audit import audit_view_event


def format_admin_datetime_ar(value):
    if not value:
        return "—"
    try:
        value = timezone.localtime(value)
    except Exception:
        pass
    return value.strftime("%d-%m-%Y %H:%M")


def get_user_display_name(user):
    if not user:
        return "غير معروف"
    full_name = ""
    if hasattr(user, "get_full_name"):
        full_name = (user.get_full_name() or "").strip()
    if full_name:
        return full_name
    first_name = (getattr(user, "first_name", "") or "").strip()
    last_name = (getattr(user, "last_name", "") or "").strip()
    combined = " ".join(part for part in [first_name, last_name] if part).strip()
    return combined or getattr(user, "username", "غير معروف")


def build_access_audit_notes(base_text, changed_fields):
    labels = get_access_audit_field_labels(changed_fields or [])
    if labels:
        return f"{base_text} الحقول المعدلة: {'، '.join(labels)}"
    return base_text


def localize_access_audit_text(text):
    text = str(text or "").strip()
    if not text:
        return "—"
    for field_name in sorted(ACCESS_PROFILE_AUDIT_LABELS.keys(), key=len, reverse=True):
        import re
        text = re.sub(rf"\b{re.escape(field_name)}\b", ACCESS_PROFILE_AUDIT_LABELS[field_name], text)
    return text


class UserAccessStateFilter(admin.SimpleListFilter):
    title = "حالة الصلاحية"
    parameter_name = "access_state"

    def lookups(self, request, model_admin):
        return (
            ("active", "نشطة"),
            ("pending", "لم تبدأ بعد"),
            ("expired", "منتهية"),
            ("disabled", "معطلة"),
            ("no_profile", "بدون ملف صلاحيات"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        today = timezone.localdate()
        if value == "no_profile":
            return queryset.filter(access_profile__isnull=True)
        if value == "disabled":
            return queryset.filter(access_profile__access_enabled=False)
        if value == "pending":
            return queryset.filter(access_profile__access_enabled=True, access_profile__access_start_date__gt=today)
        if value == "expired":
            return queryset.filter(access_profile__access_enabled=True, access_profile__access_end_date__lt=today)
        if value == "active":
            qs = queryset.filter(access_profile__access_enabled=True)
            qs = qs.exclude(access_profile__access_start_date__gt=today)
            return qs.exclude(access_profile__access_end_date__lt=today)
        return queryset


class UserProgramsCountFilter(admin.SimpleListFilter):
    title = "عدد الأنماط المفعلة"
    parameter_name = "programs_count"

    def lookups(self, request, model_admin):
        return (
            ("0", "بدون أنماط"),
            ("1", "نمط واحد"),
            ("2", "نمطان"),
            ("3", "ثلاثة أنماط"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value not in {"0", "1", "2", "3"}:
            return queryset
        return queryset.filter(_programs_count=int(value))


class UserAccessProfileInline(admin.StackedInline):
    model = UserAccessProfile
    form = UserAccessProfileAdminForm
    can_delete = False
    extra = 0
    verbose_name = "صلاحيات المستخدم"
    verbose_name_plural = "صلاحيات المستخدم"
    classes = ("tc-permissions-inline",)
    readonly_fields = ("current_access_state", "current_access_window", "current_permissions_preview")
    fieldsets = (
        ("ملخص سريع", {
            "classes": ("wide", "tc-permission-card", "tc-permission-summary-card"),
            "description": "هذا الملخص يساعدك على فهم حالة الحساب الحالية قبل النزول إلى تفاصيل كل صلاحية.",
            "fields": ("current_access_state", "current_access_window", "current_permissions_preview"),
        }),
        ("الصلاحيات العامة", {
            "classes": ("wide", "tc-permission-card", "tc-general-permissions"),
            "description": "صلاحيات عامة تخص الدخول إلى لوحة الإدارة، إدارة جميع الأنماط، التقارير، وتصدير البيانات.",
            "fields": (("access_enabled",), ("access_start_date", "access_end_date"), ("can_access_admin_panel", "can_manage_all_programs"), ("can_view_reports", "can_export_data"), ("force_password_change",)),
        }),
        ("صلاحيات الحضوري الأولي", {
            "classes": ("wide", "tc-permission-card", "tc-program-permissions"),
            "description": "صلاحيات خاصة بمتابعة متكوني الحضوري الأولي.",
            "fields": ((("initial_view", "initial_add", "initial_change", "initial_delete")),),
        }),
        ("صلاحيات التمهين", {
            "classes": ("wide", "tc-permission-card", "tc-program-permissions"),
            "description": "صلاحيات خاصة بمتابعة متكوني التمهين.",
            "fields": ((("apprentice_view", "apprentice_add", "apprentice_change", "apprentice_delete")),),
        }),
        ("صلاحيات المسائي والمعابر", {
            "classes": ("wide", "tc-permission-card", "tc-program-permissions"),
            "description": "صلاحيات خاصة بمتابعة متكوني المسائي والمعابر.",
            "fields": ((("evening_view", "evening_add", "evening_change", "evening_delete")),),
        }),
    )

    def current_access_state(self, obj):
        return obj.access_state_label() if obj and obj.pk else "سيظهر بعد حفظ المستخدم"

    current_access_state.short_description = "الحالة الحالية"

    def current_access_window(self, obj):
        return obj.access_window_label() if obj and obj.pk else "سيظهر بعد حفظ المستخدم"

    current_access_window.short_description = "نافذة الصلاحية"

    def current_permissions_preview(self, obj):
        summary = obj.admin_permissions_summary() if obj and obj.pk else "سيظهر بعد حفظ المستخدم"
        return format_html('<div style="white-space:pre-line;line-height:1.8;">{}</div>', summary)

    current_permissions_preview.short_description = "ملخص الامتيازات"


class AccessAuditLogInline(admin.TabularInline):
    model = AccessAuditLog
    fk_name = "target_user"
    extra = 0
    can_delete = False
    verbose_name = "آخر عملية تدقيق"
    verbose_name_plural = "سجل تدقيق الصلاحيات"
    readonly_fields = ("created_at_display", "actor_display", "action", "changed_fields_display", "notes_display", "before_after_preview")
    fields = ("created_at_display", "actor_display", "action", "changed_fields_display", "notes_display", "before_after_preview")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def created_at_display(self, obj):
        if not obj.created_at:
            return "—"
        value = timezone.localtime(obj.created_at)
        return format_html('<div class="tc-audit-datetime"><div class="tc-audit-datetime__date">{}</div><div class="tc-audit-datetime__time">{}</div></div>', value.strftime("%Y-%m-%d"), value.strftime("%H:%M"))

    created_at_display.short_description = "تاريخ العملية"

    def actor_display(self, obj):
        return get_user_display_name(obj.actor)

    actor_display.short_description = "تم بواسطة"

    def changed_fields_display(self, obj):
        return format_html('<div style="min-width:170px;white-space:normal;line-height:1.8;">{}</div>', obj.changed_fields_labels())

    changed_fields_display.short_description = "الحقول المتغيرة"

    def notes_display(self, obj):
        return format_html('<div class="tc-audit-notes">{}</div>', localize_access_audit_text(obj.notes))

    notes_display.short_description = "ملاحظات"

    def before_after_preview(self, obj):
        return format_html('<div style="min-width:360px;max-width:460px;background:#f8faf8;border:1px solid #d8e6dd;border-radius:12px;padding:12px 14px;white-space:pre-line;line-height:1.9;box-shadow:inset 0 1px 0 rgba(255,255,255,0.65);">{}</div>', obj.before_after_summary())

    before_after_preview.short_description = "قبل / بعد"


class ArabicUserChangeForm(UserChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        password_field = self.fields.get("password")
        if password_field:
            password_field.help_text = mark_safe('لا يتم حفظ كلمات المرور بصيغتها الأصلية، لذلك لا يمكن عرض كلمة مرور هذا المستخدم.')


class ArabicAdminPasswordChangeForm(AdminPasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        usable_password = self.fields.get("usable_password")
        if usable_password:
            usable_password.label = "المصادقة باستخدام كلمة المرور"
            usable_password.help_text = "تحديد ما إذا كان المستخدم سيتمكن من تسجيل الدخول باستعمال كلمة مرور أم لا. إذا تم تعطيل ذلك، فقد يظل قادرًا على المصادقة عبر وسائل أخرى مثل تسجيل الدخول الأحادي أو LDAP."
            translated = []
            for value, label in usable_password.choices:
                label_text = str(label)
                if label_text == "Enabled":
                    label_text = "مفعّل"
                elif label_text == "Disabled":
                    label_text = "معطّل"
                translated.append((value, label_text))
            usable_password.choices = translated


class RestrictedUserAdmin(DjangoUserAdmin):
    form = ArabicUserChangeForm
    change_password_form = ArabicAdminPasswordChangeForm
    inlines = (UserAccessProfileInline, AccessAuditLogInline)
    expiry_warning_days = 7
    list_display = ("username", "full_name_display", "email", "is_active", "admin_role_badge", "access_state_badge", "granted_programs_display", "access_end_display", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser", UserAccessStateFilter, UserProgramsCountFilter)
    search_fields = ("username", "first_name", "last_name", "email")
    actions = ("activate_selected_access", "disable_selected_access", "extend_access_7_days", "extend_access_15_days", "extend_access_30_days", "enable_force_password_change", "disable_force_password_change")
    change_list_template = "admin/auth/user/change_list.html"
    fieldsets = (("بيانات الدخول", {"classes": ("wide", "tc-user-card", "tc-login-card"), "fields": ("username", "password")}), ("المعلومات الشخصية", {"classes": ("wide", "tc-user-card", "tc-personal-card"), "fields": (("first_name", "last_name"), "email")}), ("حالة الحساب", {"classes": ("wide", "tc-user-card", "tc-account-status-group"), "fields": (("is_active", "is_staff"), "is_superuser"), "description": "إعدادات الحساب الأساسية الخاصة بالنشاط، إمكانية دخول لوحة الإدارة، والصلاحيات العليا للمستخدم."}), ("تواريخ مهمة", {"classes": ("wide", "tc-user-card", "tc-dates-card"), "fields": ("last_login", "date_joined")}))
    add_fieldsets = ((None, {"classes": ("wide", "tc-user-card", "tc-login-card"), "fields": ("username", "password1", "password2", "is_active", "is_superuser")}),)

    class Media:
        css = {"all": ("admin/custom_admin.css",)}
        js = ("admin/permission_select_all.js",)

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("access-reports/", self.admin_site.admin_view(self.access_reports_view), name="auth_user_access_reports"),
            path("export-access-report/", self.admin_site.admin_view(self.export_access_report_csv), name="auth_user_export_access_report"),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["access_reports_url"] = reverse("admin:auth_user_access_reports")
        extra_context["export_access_report_url"] = reverse("admin:auth_user_export_access_report")
        extra_context["expiry_warning_days"] = self.expiry_warning_days
        return super().changelist_view(request, extra_context=extra_context)

    def access_reports_view(self, request):
        audit_view_event(request, event_type="admin", action="view", target_model="auth.User", object_repr="access_reports_view", details="فتح تقارير الصلاحيات والمتابعة الإدارية", program="users")
        qs = self.get_queryset(request).order_by("username")
        users = list(qs)
        active_users = []
        pending_users = []
        expired_users = []
        disabled_users = []
        expiring_soon_users = []
        no_programs_users = []
        force_password_change_users = []
        for user in users:
            profile = getattr(user, "access_profile", None)
            if not profile:
                no_programs_users.append(user)
                continue
            state = profile.access_state_code()
            if state == "active":
                active_users.append(user)
            elif state == "pending":
                pending_users.append(user)
            elif state == "expired":
                expired_users.append(user)
            elif state == "disabled":
                disabled_users.append(user)
            if profile.granted_programs_count() == 0:
                no_programs_users.append(user)
            if profile.force_password_change:
                force_password_change_users.append(user)
            if profile.is_expiring_within_days(self.expiry_warning_days):
                expiring_soon_users.append(user)
        expiring_soon_users.sort(key=lambda u: (u.access_profile.remaining_access_days() or 9999, u.username))
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "تقارير الصلاحيات والمتابعة الإدارية",
            "subtitle": "ملخص جاهز لمتابعة المستخدمين وحالات الوصول",
            "access_reports_url": reverse("admin:auth_user_access_reports"),
            "warning_days": self.expiry_warning_days,
            "summary_cards": [
                {"label": "إجمالي المستخدمين", "value": len(users), "color": "#175cd3"},
                {"label": "الصلاحيات النشطة", "value": len(active_users), "color": "#067647"},
                {"label": "الصلاحيات المعطلة", "value": len(disabled_users), "color": "#475467"},
                {"label": "الصلاحيات المنتهية", "value": len(expired_users), "color": "#b42318"},
                {"label": f"تنتهي خلال {self.expiry_warning_days} أيام", "value": len(expiring_soon_users), "color": "#b54708"},
            ],
            "export_access_report_url": reverse("admin:auth_user_export_access_report"),
            "expiring_soon_users": expiring_soon_users,
            "expired_users": expired_users[:15],
            "pending_users": pending_users[:15],
            "disabled_users": disabled_users[:15],
            "no_programs_users": no_programs_users[:15],
            "force_password_change_users": force_password_change_users[:15],
        }
        return TemplateResponse(request, "admin/auth/user/access_reports.html", context)

    def _log_access_audit(self, request, target_user, profile, action, before_data, after_data, notes=""):
        changed_fields = diff_access_snapshots(before_data, after_data)
        AccessAuditLog.objects.create(actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None, target_user=target_user, profile=profile, action=action, changed_fields=changed_fields, before_data=before_data or {}, after_data=after_data or {}, notes=notes or "")

    def save_formset(self, request, form, formset, change):
        if getattr(formset, "model", None) is not UserAccessProfile:
            return super().save_formset(request, form, formset, change)
        before_map = {obj.pk: serialize_access_profile_for_audit(obj) for obj in formset.get_queryset()}
        response = super().save_formset(request, form, formset, change)
        for obj, changed_fields in getattr(formset, "changed_objects", []):
            before_data = before_map.get(obj.pk, {})
            after_data = serialize_access_profile_for_audit(obj)
            self._log_access_audit(request, obj.user, obj, "update", before_data, after_data, notes=build_access_audit_notes("تم تعديل الصلاحيات من داخل صفحة المستخدم.", changed_fields))
            audit_view_event(request, event_type="admin", action="update", target_model="trainees.UserAccessProfile", target_id=obj.pk, object_repr=get_user_display_name(obj.user), before_data=before_data, after_data=after_data, changed_fields=changed_fields, details="تعديل صلاحيات المستخدم من صفحة المستخدم", program="users")
        for obj in getattr(formset, "new_objects", []):
            after_data = serialize_access_profile_for_audit(obj)
            self._log_access_audit(request, obj.user, obj, "create", {}, after_data, notes="تم إنشاء ملف صلاحيات جديد من داخل لوحة الإدارة.")
            audit_view_event(request, event_type="admin", action="create", target_model="trainees.UserAccessProfile", target_id=obj.pk, object_repr=get_user_display_name(obj.user), before_data={}, after_data=after_data, changed_fields=sorted(after_data.keys()), details="إنشاء ملف صلاحيات جديد من داخل لوحة الإدارة", program="users")
        for obj in getattr(formset, "deleted_objects", []):
            before_data = before_map.get(obj.pk, serialize_access_profile_for_audit(obj))
            self._log_access_audit(request, getattr(obj, "user", None), None, "delete", before_data, {}, notes="تم حذف ملف الصلاحيات من داخل لوحة الإدارة.")
            audit_view_event(request, event_type="admin", action="delete", target_model="trainees.UserAccessProfile", target_id=getattr(obj, "pk", ""), object_repr=get_user_display_name(getattr(obj, "user", None)), before_data=before_data, after_data={}, changed_fields=sorted(before_data.keys()), details="حذف ملف صلاحيات من داخل لوحة الإدارة", program="users")
        return response

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("access_profile").annotate(_programs_count=(Case(When(access_profile__initial_view=True, then=Value(1)), default=Value(0), output_field=IntegerField()) + Case(When(access_profile__apprentice_view=True, then=Value(1)), default=Value(0), output_field=IntegerField()) + Case(When(access_profile__evening_view=True, then=Value(1)), default=Value(0), output_field=IntegerField())))

    def _is_admin_manager(self, request):
        u = request.user
        return u.is_active and u.is_superuser

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

    def full_name_display(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name or "—"

    full_name_display.short_description = "الاسم الكامل"

    def _profile(self, obj):
        return getattr(obj, "access_profile", None)

    def admin_role_badge(self, obj):
        profile = self._profile(obj)
        if obj.is_superuser:
            label = "مدير كامل"
            color = "#b42318"
        elif profile and profile.can_manage_all_programs:
            label = "مدير الأنماط"
            color = "#175cd3"
        elif profile and profile.can_access_admin_panel:
            label = "مشرف لوحة"
            color = "#0f766e"
        else:
            label = "مستخدم عادي"
            color = "#475467"
        return format_html('<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{};color:#fff;">{}</span>', color, label)

    admin_role_badge.short_description = "الدور الإداري"

    def access_state_badge(self, obj):
        profile = self._profile(obj)
        if not profile:
            return format_html('<span style="color:#475467;">بدون ملف صلاحيات</span>')
        mapping = {"active": ("نشطة", "#067647"), "pending": ("لم تبدأ", "#b54708"), "expired": ("منتهية", "#b42318"), "disabled": ("معطلة", "#475467")}
        label, color = mapping.get(profile.access_state_code(), ("غير معروفة", "#475467"))
        return format_html('<strong style="color:{};">{}</strong>', color, label)

    access_state_badge.short_description = "حالة الصلاحية"

    def granted_programs_display(self, obj):
        profile = self._profile(obj)
        if not profile:
            return "—"
        labels = profile.granted_program_labels()
        return "، ".join(labels) if labels else "بدون أنماط"

    granted_programs_display.short_description = "الأنماط المفعلة"

    def access_end_display(self, obj):
        profile = self._profile(obj)
        if not profile:
            return "—"
        if not profile.access_end_date:
            return "غير محددة"
        remaining = profile.remaining_access_days()
        suffix = ""
        if remaining is not None:
            suffix = f" (منذ {abs(remaining)} يوم)" if remaining < 0 else f" (بعد {remaining} يوم)"
        return f"{profile.access_end_date:%Y-%m-%d}{suffix}"

    access_end_display.short_description = "نهاية الصلاحية"

    @admin.action(description="تفعيل الصلاحيات للمستخدمين المحددين")
    def activate_selected_access(self, request, queryset):
        selected_users = list(queryset)
        updated = 0
        for user in queryset:
            profile, _ = UserAccessProfile.objects.get_or_create(user=user)
            if not profile.access_enabled:
                before_data = serialize_access_profile_for_audit(profile)
                profile.access_enabled = True
                profile.save(update_fields=["access_enabled", "updated_at"])
                self._log_access_audit(request, user, profile, "activate", before_data, serialize_access_profile_for_audit(profile), notes="تم تفعيل الصلاحيات عبر إجراء جماعي.")
                updated += 1
        audit_view_event(request, event_type="admin", action="update", target_model="auth.User", object_repr="bulk_activate_access", after_data={"updated": updated, "users": [u.username for u in selected_users]}, changed_fields=["access_enabled"], details="تفعيل الصلاحيات عبر إجراء جماعي", program="users")
        self.message_user(request, f"تم تفعيل الصلاحيات لـ {updated} مستخدم/مستخدمين.", level=messages.SUCCESS)

    @admin.action(description="تعطيل الصلاحيات للمستخدمين المحددين")
    def disable_selected_access(self, request, queryset):
        selected_users = list(queryset)
        updated = 0
        for user in queryset:
            if user.is_superuser:
                continue
            profile, _ = UserAccessProfile.objects.get_or_create(user=user)
            if profile.access_enabled:
                before_data = serialize_access_profile_for_audit(profile)
                profile.access_enabled = False
                profile.save(update_fields=["access_enabled", "updated_at"])
                self._log_access_audit(request, user, profile, "disable", before_data, serialize_access_profile_for_audit(profile), notes="تم تعطيل الصلاحيات عبر إجراء جماعي.")
                updated += 1
        audit_view_event(request, event_type="admin", action="update", target_model="auth.User", object_repr="bulk_disable_access", after_data={"updated": updated, "users": [u.username for u in selected_users]}, changed_fields=["access_enabled"], details="تعطيل الصلاحيات عبر إجراء جماعي", program="users")
        self.message_user(request, f"تم تعطيل الصلاحيات لـ {updated} مستخدم/مستخدمين.", level=messages.WARNING)

    def _extend_access(self, request, queryset, days):
        today = timezone.localdate()
        updated = 0
        for user in queryset:
            profile, _ = UserAccessProfile.objects.get_or_create(user=user)
            before_data = serialize_access_profile_for_audit(profile)
            base_date = profile.access_end_date or today
            if base_date < today:
                base_date = today
            if not profile.access_start_date:
                profile.access_start_date = today
            profile.access_enabled = True
            profile.access_end_date = base_date + timedelta(days=days)
            profile.save(update_fields=["access_enabled", "access_start_date", "access_end_date", "updated_at"])
            self._log_access_audit(request, user, profile, "extend", before_data, serialize_access_profile_for_audit(profile), notes=f"تم تمديد الصلاحية لمدة {days} يومًا عبر إجراء جماعي.")
            updated += 1
        self.message_user(request, f"تم تمديد الصلاحية لمدة {days} يومًا لـ {updated} مستخدم/مستخدمين.", level=messages.SUCCESS)

    @admin.action(description="تمديد الصلاحية 7 أيام")
    def extend_access_7_days(self, request, queryset):
        self._extend_access(request, queryset, 7)

    @admin.action(description="تمديد الصلاحية 15 يومًا")
    def extend_access_15_days(self, request, queryset):
        self._extend_access(request, queryset, 15)

    @admin.action(description="تمديد الصلاحية 30 يومًا")
    def extend_access_30_days(self, request, queryset):
        self._extend_access(request, queryset, 30)

    @admin.action(description="إجبار المستخدمين المحددين على تغيير كلمة المرور")
    def enable_force_password_change(self, request, queryset):
        selected_users = list(queryset)
        updated = 0
        for user in queryset:
            profile, _ = UserAccessProfile.objects.get_or_create(user=user)
            if not profile.force_password_change:
                before_data = serialize_access_profile_for_audit(profile)
                profile.force_password_change = True
                profile.save(update_fields=["force_password_change", "updated_at"])
                self._log_access_audit(request, user, profile, "force_password_on", before_data, serialize_access_profile_for_audit(profile), notes="تم تفعيل إجبار تغيير كلمة المرور عبر إجراء جماعي.")
                updated += 1
        self.message_user(request, f"تم تفعيل طلب تغيير كلمة المرور لـ {updated} مستخدم/مستخدمين.", level=messages.SUCCESS)

    @admin.action(description="إلغاء إجبار تغيير كلمة المرور")
    def disable_force_password_change(self, request, queryset):
        selected_users = list(queryset)
        updated = 0
        for user in queryset:
            profile, _ = UserAccessProfile.objects.get_or_create(user=user)
            if profile.force_password_change:
                before_data = serialize_access_profile_for_audit(profile)
                profile.force_password_change = False
                profile.save(update_fields=["force_password_change", "updated_at"])
                self._log_access_audit(request, user, profile, "force_password_off", before_data, serialize_access_profile_for_audit(profile), notes="تم إلغاء إجبار تغيير كلمة المرور عبر إجراء جماعي.")
                updated += 1
        self.message_user(request, f"تم إلغاء إجبار تغيير كلمة المرور لـ {updated} مستخدم/مستخدمين.", level=messages.SUCCESS)

    def export_access_report_csv(self, request):
        audit_view_event(request, event_type="admin", action="request", target_model="auth.User", object_repr="export_access_report_csv", details="تصدير تقرير الصلاحيات بصيغة CSV", program="users")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="user_access_report.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["اسم المستخدم", "الاسم الكامل", "مفعلة", "بداية الصلاحية", "نهاية الصلاحية", "الأيام المتبقية", "درجة الاستعجال", "الأنماط", "لوحة الإدارة", "إجبار تغيير كلمة المرور"])
        for user in self.get_queryset(request):
            profile = self._profile(user)
            if not profile:
                continue
            writer.writerow([user.username, user.get_full_name().strip(), "نعم" if profile.access_enabled else "لا", profile.access_start_date or "", profile.access_end_date or "", profile.days_until_expiry() if profile.days_until_expiry() is not None else "", profile.expiry_urgency_label(), "، ".join(profile.granted_program_labels()) if profile.granted_program_labels() else "", "نعم" if profile.can_access_admin_panel else "لا", "نعم" if profile.force_password_change else "لا"])
        return response


class AccessAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at_display", "target_user_display", "actor_display", "action", "changed_fields_short")
    list_filter = ("action", "created_at")
    search_fields = ("target_user__username", "target_user__first_name", "target_user__last_name", "actor__username", "actor__first_name", "actor__last_name", "notes")
    readonly_fields = ("created_at_display", "actor_display", "target_user_display", "profile", "action", "changed_fields_display", "notes_display", "before_after_preview")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def created_at_display(self, obj):
        return format_admin_datetime_ar(obj.created_at)

    created_at_display.short_description = "تاريخ العملية"

    def target_user_display(self, obj):
        return get_user_display_name(obj.target_user)

    target_user_display.short_description = "المستخدم المستهدف"

    def actor_display(self, obj):
        return get_user_display_name(obj.actor)

    actor_display.short_description = "تم بواسطة"

    def changed_fields_short(self, obj):
        return obj.changed_fields_labels()

    changed_fields_short.short_description = "الحقول المتغيرة"

    def changed_fields_display(self, obj):
        return format_html('<div style="min-width:220px;white-space:normal;line-height:1.8;">{}</div>', obj.changed_fields_labels())

    changed_fields_display.short_description = "الحقول المتغيرة"

    def notes_display(self, obj):
        return format_html('<div style="min-width:420px;white-space:normal;line-height:1.9;">{}</div>', localize_access_audit_text(obj.notes))

    notes_display.short_description = "ملاحظات"

    def before_after_preview(self, obj):
        return format_html('<div class="tc-audit-before-after">{}</div>', obj.before_after_summary())

    before_after_preview.short_description = "قبل / بعد"
    fieldsets = ((None, {"fields": (("created_at_display", "action"), ("target_user_display", "actor_display"), "profile")}), ("التغييرات", {"fields": ("changed_fields_display", "notes_display", "before_after_preview")}))


def register_auth_admin(site):
    try:
        site.unregister(Group)
    except admin.sites.NotRegistered:
        pass
    try:
        site.unregister(User)
    except admin.sites.NotRegistered:
        pass
    try:
        site.unregister(AccessAuditLog)
    except admin.sites.NotRegistered:
        pass
    site.register(User, RestrictedUserAdmin)
    site.register(AccessAuditLog, AccessAuditLogAdmin)
