from django.contrib import admin

from .models import (
    CentralOffice,
    CentralSyncEvent,
    CentralDeviceRegistration,
    Commune,
    OfficeIdentity,
    OrganizationUnit,
    SyncConflict,
    SyncInbox,
    SyncOutbox,
    SyncState,
    Wilaya,
)
from .office_cleanup import cleanup_users_for_office_delete, _cleanup_orphan_office_users




@admin.register(Wilaya)
class WilayaAdmin(admin.ModelAdmin):
    list_display = ("code", "name_ar", "name_latin", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name_ar", "name_latin")
    ordering = ("code",)


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ("code", "name_ar", "name_latin", "wilaya", "is_active")
    list_filter = ("wilaya", "is_active")
    search_fields = ("code", "name_ar", "name_latin", "wilaya__code", "wilaya__name_ar")
    autocomplete_fields = ("wilaya",)
    ordering = ("wilaya__code", "code")


@admin.register(OfficeIdentity)
class OfficeIdentityAdmin(admin.ModelAdmin):
    list_display = ("office_name", "office_id", "server_id", "mode", "sync_enabled", "central_url", "updated_at")
    readonly_fields = ("created_at", "updated_at", "last_checked_at")
    fieldsets = (
        ("هوية المكتب", {"fields": ("mode", "office_id", "office_name", "server_id")}),
        ("الخادم المركزي", {"fields": ("central_url", "sync_token", "sync_enabled")}),
        ("معلومات", {"fields": ("notes", "last_checked_at", "created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        if OfficeIdentity.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(SyncOutbox)
class SyncOutboxAdmin(admin.ModelAdmin):
    list_display = ("created_at", "operation", "app_label", "model_name", "object_pk", "status", "attempts", "office_id")
    list_filter = ("status", "operation", "app_label", "model_name", "office_id")
    search_fields = ("event_id", "object_pk", "idempotency_key", "app_label", "model_name")
    readonly_fields = ("event_id", "payload_hash", "idempotency_key", "created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(SyncInbox)
class SyncInboxAdmin(admin.ModelAdmin):
    list_display = ("received_at", "operation", "app_label", "model_name", "object_pk", "status", "source_office_id")
    list_filter = ("status", "operation", "app_label", "model_name", "source_office_id")
    search_fields = ("event_id", "object_pk", "app_label", "model_name")
    readonly_fields = ("received_at", "applied_at")


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    list_display = ("direction", "scope", "last_cursor", "last_success_at", "last_error_at", "updated_at")
    list_filter = ("direction", "scope")
    search_fields = ("scope", "last_cursor", "last_error")


@admin.register(SyncConflict)
class SyncConflictAdmin(admin.ModelAdmin):
    list_display = ("created_at", "app_label", "model_name", "object_pk", "reason", "status")
    list_filter = ("status", "app_label", "model_name")
    search_fields = ("conflict_id", "object_pk", "reason", "app_label", "model_name")
    readonly_fields = ("conflict_id", "created_at")


@admin.register(CentralOffice)
class CentralOfficeAdmin(admin.ModelAdmin):
    list_display = ("office_code", "office_alias", "office_id", "office_display_name", "office_name", "server_id", "commune", "establishment_type", "is_active", "license_status", "max_users", "last_seen_at")
    list_filter = ("is_active", "allow_push", "allow_pull", "license_status", "license_plan", "establishment_type", "wilaya", "commune")
    search_fields = ("office_code", "office_alias", "office_id", "office_name", "office_display_name", "server_id", "commune__name_ar", "commune__code")
    autocomplete_fields = ("wilaya", "commune")
    readonly_fields = ("created_at", "updated_at", "last_seen_at", "last_pull_at", "last_pull_cursor", "last_pull_error")
    fieldsets = (
        ("هوية المؤسسة الرسمية", {"fields": ("office_code", "office_alias", "office_id", "office_name", "office_display_name", "wilaya", "commune", "establishment_type", "establishment_number", "server_id", "sync_token")}),
        ("السماح بالمزامنة", {"fields": ("is_active", "allow_push", "allow_pull", "pull_enabled", "office_api_url", "disabled_reason")}),
        ("الترخيص والتحكم", {"fields": ("license_status", "license_expires_at", "license_plan", "max_users", "feature_flags")}),
        ("ملاحظات", {"fields": ("control_notes", "notes")}),
        ("تواريخ", {"fields": ("last_seen_at", "last_pull_at", "last_pull_cursor", "last_pull_error", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        # عند إضافة مكتب من Django Admin نولّد الرمز تلقائيًا ونفعّل الدفع والسحب.
        if not obj.sync_token:
            from .services import generate_sync_token
            obj.sync_token = generate_sync_token()
        obj.is_active = True if obj.is_active is None else obj.is_active
        obj.allow_push = True
        obj.allow_pull = True
        super().save_model(request, obj, form, change)

    def _cleanup_users_before_office_delete(self, office):
        deleted_users, deleted_events = cleanup_users_for_office_delete(office.office_id)
        return deleted_users, deleted_events

    def delete_model(self, request, obj):
        from django.db import transaction

        office_label = obj.office_name or obj.office_id
        with transaction.atomic():
            deleted_users, deleted_events = self._cleanup_users_before_office_delete(obj)
            super().delete_model(request, obj)
            extra_users, extra_events, _ = _cleanup_orphan_office_users()
        self.message_user(
            request,
            f"تم حذف المكتب {office_label} وتنظيف مستخدميه تلقائيًا: حذف {deleted_users + extra_users} مستخدم و {deleted_events + extra_events} سجل إرسال مستخدمين.",
        )

    def delete_queryset(self, request, queryset):
        from django.db import transaction

        offices = list(queryset)
        with transaction.atomic():
            deleted_users = 0
            deleted_events = 0
            for office in offices:
                users_count, events_count = self._cleanup_users_before_office_delete(office)
                deleted_users += users_count
                deleted_events += events_count
            super().delete_queryset(request, queryset)
            extra_users, extra_events, _ = _cleanup_orphan_office_users()
            deleted_users += extra_users
            deleted_events += extra_events
        self.message_user(
            request,
            f"تم حذف {len(offices)} مكتب/مكاتب وتنظيف المستخدمين تلقائيًا: حذف {deleted_users} مستخدم و {deleted_events} سجل إرسال مستخدمين.",
        )


@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(admin.ModelAdmin):
    list_display = ("office", "unit_code", "name_ar", "unit_type", "parent", "order", "is_active")
    list_filter = ("unit_type", "is_active", "office")
    search_fields = ("unit_code", "name_ar", "office__office_code", "office__office_id", "office__office_display_name")
    autocomplete_fields = ("office", "parent")
    ordering = ("office__office_code", "order", "id")


@admin.register(CentralSyncEvent)
class CentralSyncEventAdmin(admin.ModelAdmin):
    list_display = ("id", "received_at", "source_office_id", "operation", "app_label", "model_name", "object_pk")
    list_filter = ("source_office_id", "operation", "app_label", "model_name")
    search_fields = ("source_event_id", "central_event_id", "object_pk", "app_label", "model_name")
    readonly_fields = ("central_event_id", "source_event_id", "received_at")
    date_hierarchy = "received_at"

from .models import CentralUpdateRelease, CentralUpdateCheckLog


@admin.register(CentralUpdateRelease)
class CentralUpdateReleaseAdmin(admin.ModelAdmin):
    list_display = ("version", "title", "channel", "update_type", "is_active", "is_required", "rollout_all_offices", "published_at")
    list_filter = ("is_active", "is_required", "channel", "update_type", "rollout_all_offices")
    search_fields = ("version", "title", "download_url", "release_notes")
    readonly_fields = ("published_at", "created_at", "updated_at")
    fieldsets = (
        ("معلومات الإصدار", {"fields": ("version", "title", "channel", "update_type", "release_notes")}),
        ("ملف التحديث", {"fields": ("download_url", "checksum_sha256", "file_size_bytes")}),
        ("النشر والتوجيه", {"fields": ("is_active", "is_required", "rollout_all_offices", "allowed_office_ids", "blocked_office_ids", "min_current_version")}),
        ("تواريخ", {"fields": ("published_at", "created_at", "updated_at")}),
    )


@admin.register(CentralUpdateCheckLog)
class CentralUpdateCheckLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "office_id", "server_id", "current_version", "channel", "has_update", "offered_version")
    list_filter = ("has_update", "channel", "offered_version")
    search_fields = ("office_id", "server_id", "current_version", "offered_version")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

# ============================================================
# Central Admin user provisioning to offices WITHOUT changing
# the original beautiful Users admin interface.
# نحتفظ بواجهة المستخدمين الأصلية ونضيف فقط حقول إرسال/تحديث المستخدم إلى مكتب.
# ============================================================
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils.html import format_html_join

try:
    from trainees.admin_users import RestrictedUserAdmin as _OriginalRestrictedUserAdmin
except Exception:  # fallback only if import fails
    from django.contrib.auth.admin import UserAdmin as _OriginalRestrictedUserAdmin

from .provisioning import payload_from_user_and_cleaned, create_user_provision_event


class _CentralOfficeProvisionUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="كلمة المرور", widget=forms.PasswordInput(render_value=True))
    password2 = forms.CharField(label="تأكيد كلمة المرور", widget=forms.PasswordInput(render_value=True))
    email = forms.EmailField(label="البريد الإلكتروني", required=False)
    first_name = forms.CharField(label="الاسم", required=False, max_length=150)
    last_name = forms.CharField(label="اللقب", required=False, max_length=150)
    is_active = forms.BooleanField(label="نشط", required=False, initial=True)
    is_staff = forms.BooleanField(label="يسمح له بدخول الإدارة داخل المكتب", required=False, initial=False)
    is_superuser = forms.BooleanField(label="مدير كامل في الخادم المركزي", required=False, initial=False)

    send_to_office = forms.BooleanField(
        label="إرسال هذا المستخدم إلى مكتب محلي عبر المزامنة",
        required=False,
        initial=True,
        help_text="فعّل هذا الخيار عندما تريد أن يستطيع المستخدم الدخول إلى برنامج تسيير المتكوّنين في مكتب محدد.",
    )
    target_office = forms.ModelChoiceField(
        label="المكتب الهدف",
        queryset=CentralOffice.objects.none(),
        required=False,
        help_text="اختر المكتب الذي سيُنشأ فيه المستخدم بعد تشغيل عامل المزامنة داخل ذلك المكتب.",
    )
    class Meta:
        model = get_user_model()
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_office"].queryset = CentralOffice.objects.filter(is_active=True).order_by("office_id")

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("password1") or "") != (cleaned.get("password2") or ""):
            raise forms.ValidationError("كلمتا المرور غير متطابقتين.")
        if cleaned.get("send_to_office") and not cleaned.get("target_office"):
            raise forms.ValidationError("اختر المكتب الهدف أو ألغِ خيار إرسال المستخدم إلى مكتب محلي.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email") or ""
        user.first_name = self.cleaned_data.get("first_name") or ""
        user.last_name = self.cleaned_data.get("last_name") or ""
        user.is_active = bool(self.cleaned_data.get("is_active"))
        user.is_staff = bool(self.cleaned_data.get("is_staff") or self.cleaned_data.get("can_admin_panel"))
        user.is_superuser = bool(self.cleaned_data.get("is_superuser"))
        user.set_password(self.cleaned_data.get("password1") or "")
        if commit:
            user.save()
        return user


class _CentralOfficeProvisionUserChangeForm(forms.ModelForm):
    # حقول اختيارية لا تغير الواجهة الأصلية جذريًا؛ تظهر أسفل صفحة التعديل فقط.
    new_password = forms.CharField(label="كلمة مرور جديدة للمكتب المحلي", required=False, widget=forms.PasswordInput(render_value=True), help_text="اتركها فارغة إذا كنت لا تريد تغيير كلمة المرور في المكتب المحلي.")
    send_to_office = forms.BooleanField(label="إرسال هذا التعديل إلى مكتب محلي عبر المزامنة", required=False, initial=False)
    target_office = forms.ModelChoiceField(label="المكتب الهدف", queryset=CentralOffice.objects.none(), required=False)
    class Meta:
        model = get_user_model()
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_office"].queryset = CentralOffice.objects.filter(is_active=True).order_by("office_id")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("send_to_office") and not cleaned.get("target_office"):
            raise forms.ValidationError("اختر المكتب الهدف عند إرسال تعديل المستخدم إلى مكتب محلي.")
        return cleaned


# حقول قديمة/مختصرة كانت تكرر نفس معنى صلاحيات المستخدم التفصيلية.
# نُخفيها من صفحة تعديل المستخدم المركزي حتى يكون التعديل من مكان واحد فقط:
# قسم "صلاحيات المستخدم" + قسم الإرسال للمكتب.
_CENTRAL_USER_EDIT_HIDDEN_FIELDS = {
    "is_staff",
    "can_add",
    "can_edit",
    "can_delete",
    "can_export",
    "can_admin_panel",
}


def _strip_fields_tree(fields):
    """Remove selected field names from nested Django admin field tuples."""
    if isinstance(fields, str):
        return None if fields in _CENTRAL_USER_EDIT_HIDDEN_FIELDS else fields
    if isinstance(fields, (list, tuple)):
        cleaned = []
        for item in fields:
            stripped = _strip_fields_tree(item)
            if stripped in (None, (), []):
                continue
            cleaned.append(stripped)
        return tuple(cleaned) if isinstance(fields, tuple) else cleaned
    return fields


def _central_user_fieldsets_without_duplicate_permissions(fieldsets):
    cleaned_fieldsets = []
    for title, opts in fieldsets or ():
        opts = dict(opts or {})
        opts["fields"] = _strip_fields_tree(opts.get("fields", ()))
        if not opts.get("fields"):
            continue
        if title == "حالة الحساب":
            opts["description"] = "إعدادات حالة الحساب الأساسية. مربع مفعّل يبقى هنا، أما الصلاحيات التفصيلية فتُعدّل من قسم صلاحيات المستخدم فقط."
        cleaned_fieldsets.append((title, opts))
    return tuple(cleaned_fieldsets)


class _CentralProvisionRestrictedUserAdmin(_OriginalRestrictedUserAdmin):
    """نفس واجهة المستخدمين الأصلية، مع قسم إرسال/تحديث المستخدم إلى مكتب بدون تكرار الصلاحيات."""
    add_form = _CentralOfficeProvisionUserCreationForm
    form = _CentralOfficeProvisionUserChangeForm
    list_display = ("username", "central_office_display", "full_name_display", "email", "is_active", "admin_role_badge", "access_state_badge", "granted_programs_display", "access_end_display", "last_login")

    def central_office_display(self, obj):
        events = (
            CentralSyncEvent.objects
            .filter(app_label="auth", model_name="User", operation="provision_user", is_deleted=False, object_pk=obj.username)
            .order_by("-id")
        )
        office_ids = []
        for event in events:
            extra = event.extra or {}
            payload = event.payload or {}
            office_id = str(extra.get("target_office_id") or payload.get("target_office_id") or "").strip()
            if office_id and office_id not in office_ids:
                office_ids.append(office_id)
        if not office_ids:
            return "—"
        offices = {office.office_id: office for office in CentralOffice.objects.filter(office_id__in=office_ids)}
        labels = []
        for office_id in office_ids:
            office = offices.get(office_id)
            labels.append((office.office_name if office and office.office_name else office_id, office_id))
        return format_html_join(" ", '<span class="tc-office-badge" title="{}">{}</span>', ((office_id, label) for label, office_id in labels))

    central_office_display.short_description = "المكتب"

    add_fieldsets = (
        ("بيانات الدخول", {"classes": ("wide", "tc-user-card", "tc-login-card"), "fields": ("username", "password1", "password2", "email", "first_name", "last_name", "is_active", "is_superuser")}),
        ("إرسال المستخدم إلى مكتب محلي", {"classes": ("wide", "tc-user-card", "tc-login-card"), "fields": ("send_to_office", "target_office"), "description": "فعّل الإرسال واختر المكتب. بعد إنشاء المستخدم يمكن ضبط صلاحياته من قسم صلاحيات المستخدم ثم إعادة الإرسال للمكتب."}),
    )

    fieldsets = _central_user_fieldsets_without_duplicate_permissions(getattr(_OriginalRestrictedUserAdmin, "fieldsets", ())) + (
        ("إرسال/تحديث المستخدم في مكتب محلي", {"classes": ("wide", "tc-user-card", "tc-login-card"), "fields": ("send_to_office", "target_office", "new_password"), "description": "فعّل مربع الإرسال عندما تريد إرسال بيانات المستخدم والصلاحيات الحالية إلى المكتب المختار. الصلاحيات تُؤخذ من قسم صلاحيات المستخدم في نفس الصفحة."}),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        return _central_user_fieldsets_without_duplicate_permissions(fieldsets)

    def _create_provision_event(self, request, obj, form, *, change: bool):
        if getattr(settings, "SYNC_MODE", "") != "central_server":
            return
        cleaned = getattr(form, "cleaned_data", {}) or {}
        if not cleaned.get("send_to_office"):
            return
        target = cleaned.get("target_office")
        if not target:
            return
        # نوحّد اسم حقل كلمة المرور بين الإضافة والتعديل.
        cleaned = dict(cleaned)
        if change:
            cleaned["password"] = cleaned.get("new_password") or ""
        else:
            cleaned["password"] = cleaned.get("password1") or ""
        payload = payload_from_user_and_cleaned(obj, cleaned, target)
        event = create_user_provision_event(
            target_office=target,
            user=obj,
            payload=payload,
            kind="user_update_from_admin" if change else "user_provision_from_admin",
        )
        messages.success(request, f"تم {'تحديث' if change else 'إنشاء'} المستخدم مركزيًا وإنشاء حدث مزامنة لإرساله إلى {target.office_name or target.office_id}. رقم الحدث: {event.id}. شغّل عامل المزامنة في المكتب ليظهر/يتحدث المستخدم هناك.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._create_provision_event(request, obj, form, change=change)


if getattr(settings, "SYNC_MODE", "") == "central_server":
    _UserModel = get_user_model()
    try:
        admin.site.unregister(_UserModel)
    except admin.sites.NotRegistered:
        pass
    admin.site.register(_UserModel, _CentralProvisionRestrictedUserAdmin)


@admin.register(CentralDeviceRegistration)
class CentralDeviceRegistrationAdmin(admin.ModelAdmin):
    list_display = ("hostname", "server_id", "status", "assigned_office", "lan_ip", "requested_at", "last_seen_at", "approved_at")
    list_filter = ("status", "assigned_office")
    search_fields = ("server_id", "hostname", "device_label", "lan_ip")
    readonly_fields = ("server_id", "request_secret", "device_token", "requested_at", "last_seen_at", "approved_at", "config_delivered_at")
    fieldsets = (
        ("الجهاز", {"fields": ("server_id", "hostname", "device_label", "lan_ip", "app_version", "central_url")}),
        ("الاعتماد", {"fields": ("status", "assigned_office", "device_token", "notes")}),
        ("حماية الطلب", {"fields": ("request_secret",)}),
        ("تواريخ", {"fields": ("requested_at", "last_seen_at", "approved_at", "config_delivered_at")}),
    )

    def save_model(self, request, obj, form, change):
        if obj.status == CentralDeviceRegistration.STATUS_APPROVED and obj.assigned_office and not obj.device_token:
            from .services import generate_sync_token
            obj.device_token = generate_sync_token()
            if not obj.approved_at:
                from django.utils import timezone
                obj.approved_at = timezone.now()
        super().save_model(request, obj, form, change)
