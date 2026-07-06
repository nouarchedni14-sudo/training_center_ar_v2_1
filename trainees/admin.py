import re
from datetime import timedelta
from django.contrib import admin, messages  # استيراد عناصر محددة من مكتبة/وحدة
from django.http import HttpResponseRedirect, HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.db.models import Case, When, Value, IntegerField
from .models import حضوري_أولي, تمهين, مسائي_ومعابر, CustomField, دفعة, refresh_all_promotion_semester_starts, cohort_start_dates_for_model, UserAccessProfile, ActivityLog, AttendanceAction, DismissalDecision, SanctionRecord, SummonsRecord, AccessAuditLog, UserAccountAuditLog, ComprehensiveAuditLog, UserAttendanceSummaryArchive, serialize_access_profile_for_audit, diff_access_snapshots, get_access_audit_field_labels, ACCESS_PROFILE_AUDIT_LABELS
from .forms import PromotionAdminForm, DATE_INPUT_FORMATS, UserAccessProfileAdminForm
from .admin_filters import UnifiedStatusFilter  # استيراد عناصر محددة من مكتبة/وحدة
from .excel_import import ExcelImportAdminMixin  # استيراد عناصر محددة من مكتبة/وحدة
from .status_utils import unified_status_code  # استيراد عناصر محددة من مكتبة/وحدة
from .semester_utils import resolve_session_year, compute_semester_for_trainee
from .permissions import can_access_admin_panel
from .admin_mixins import AdminPanelPermissionMixin, SuperuserOnlyAdminMixin, BaseProgramAdmin
from .admin_users import RestrictedUserAdmin, AccessAuditLogAdmin, register_auth_admin
from django.shortcuts import render


def _fmt_date(obj, field_name: str):  # تعريف دالة (Function)
    v = getattr(obj, field_name, None)  # تعيين قيمة لمتغير/إعداد
    # If birth date is assumed (year/month/day incomplete) show year only
    if field_name == "تاريخ_الميلاد" and getattr(obj, "مفترض", False) and v:  # شرط (If)
        return f"{v.year:04d}"  # إرجاع قيمة من الدالة
    return v.strftime("%Y-%m-%d") if v else ""  # إرجاع قيمة من الدالة
_fmt_date.short_description = "تاريخ"  # تعيين قيمة لمتغير/إعداد

# أعمدة مشتركة (مع عرض التواريخ بصيغة رقمية + عمود مفترض)


def format_admin_datetime_ar(value):
    """تنسيق ثابت للتاريخ والوقت داخل الإدارة بصيغة رقمية عربية واضحة."""
    if not value:
        return "—"
    try:
        value = timezone.localtime(value)
    except Exception:
        pass
    return value.strftime("%d-%m-%Y %H:%M")


def get_user_display_name(user):
    """عرض الاسم الكامل للمستخدم بدل اسم الدخول متى كان متاحًا."""
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
    """صياغة عربية واضحة للملاحظات داخل سجل تدقيق الصلاحيات."""
    labels = get_access_audit_field_labels(changed_fields or [])
    if labels:
        return f"{base_text} الحقول المعدلة: {'، '.join(labels)}"
    return base_text


def localize_access_audit_text(text):
    """استبدال أسماء الحقول الداخلية بأسمائها العربية حتى في السجلات القديمة."""
    text = str(text or "").strip()
    if not text:
        return "—"
    for field_name in sorted(ACCESS_PROFILE_AUDIT_LABELS.keys(), key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(field_name)}\b", ACCESS_PROFILE_AUDIT_LABELS[field_name], text)
    return text

COMMON_LIST = (  # تعيين قيمة لمتغير/إعداد
    "تصنيف_الحالة",  # سطر كود لتنفيذ منطق/إعداد
    "الدفعة_الحالية",
    "الرقم_التعريفي",  # سطر كود لتنفيذ منطق/إعداد
    "اللقب",  # سطر كود لتنفيذ منطق/إعداد
    "الاسم",  # سطر كود لتنفيذ منطق/إعداد
    "تاريخ_الميلاد_رقمي",  # سطر كود لتنفيذ منطق/إعداد
    "مفترض",  # سطر كود لتنفيذ منطق/إعداد
    "رقم_الهاتف",  # سطر كود لتنفيذ منطق/إعداد
    "رقم_التسجيل",  # سطر كود لتنفيذ منطق/إعداد
    "التخصص",  # سطر كود لتنفيذ منطق/إعداد
    "الولاية",  # سطر كود لتنفيذ منطق/إعداد
    "تاريخ_بداية_التكوين_رقمي",  # سطر كود لتنفيذ منطق/إعداد
    "تاريخ_نهاية_التكوين_رقمي",  # سطر كود لتنفيذ منطق/إعداد
    "الحالة",  # سطر كود لتنفيذ منطق/إعداد
)  # سطر كود لتنفيذ منطق/إعداد

COMMON_SEARCH = (  # تعيين قيمة لمتغير/إعداد
    "الرقم_التعريفي",  # سطر كود لتنفيذ منطق/إعداد
    "اللقب",  # سطر كود لتنفيذ منطق/إعداد
    "الاسم",  # سطر كود لتنفيذ منطق/إعداد
    "رقم_الهاتف",  # سطر كود لتنفيذ منطق/إعداد
    "رقم_التسجيل",  # سطر كود لتنفيذ منطق/إعداد
    "رقم_التعريف_الوطني",  # سطر كود لتنفيذ منطق/إعداد
)  # سطر كود لتنفيذ منطق/إعداد

COMMON_FILTER = (UnifiedStatusFilter,)  # تعيين قيمة لمتغير/إعداد

PROMOTION_COMMON = ("الدفعة_الحالية",)

def _promotion_label(obj):
    return str(obj.الدفعة) if getattr(obj, "الدفعة", None) else ""



admin.site.site_header = "منظومة تسيير المتكوّنين"
admin.site.site_title = "المنظومة الإدارية"
admin.site.index_title = "التحكم المركزي والمتابعة"


def _admin_status_label(obj):  # تعريف دالة (Function)
    raw = getattr(obj, "الحالة", "")
    if unified_status_code(raw) != "removed":
        return "حالي"
    removal_date = getattr(obj, "تاريخ_الشطب", None)
    if not removal_date:
        return "مشطوب"
    return "مشطوب" if _is_counted_removed(raw, removal_date) else "مشطوب حديثًا"


def _subtract_one_month(d):  # تعريف دالة (Function)
    import calendar
    month = d.month - 1
    year = d.year
    if month == 0:
        month = 12
        year -= 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def _is_counted_removed(status_value, removal_date):  # تعريف دالة (Function)
    from django.utils import timezone
    if unified_status_code(status_value) != "removed":
        return False
    if not removal_date:
        return True
    cutoff = _subtract_one_month(timezone.localdate())
    return removal_date <= cutoff

class StyledTraineeAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True

    def تصنيف_الحالة(self, obj):
        return _admin_status_label(obj)
    تصنيف_الحالة.short_description = "تصنيف الحالة"

    def الدفعة_الحالية(self, obj):
        return str(obj.الدفعة) if getattr(obj, "الدفعة", None) else ""
    الدفعة_الحالية.short_description = "الدفعة"

    class Media:
        css = {"all": ("admin/custom_admin.css",)}
        js = ("admin/custom_admin_tables.js", "admin/admin_row_status.js")


@admin.register(حضوري_أولي)  # سطر كود لتنفيذ منطق/إعداد
class InitialAdmin(ExcelImportAdminMixin, BaseProgramAdmin):  # تعريف كلاس (Class)
    list_display = COMMON_LIST  # تعيين قيمة لمتغير/إعداد
    search_fields = COMMON_SEARCH  # تعيين قيمة لمتغير/إعداد
    list_filter = COMMON_FILTER  # تعيين قيمة لمتغير/إعداد


@admin.register(تمهين)  # سطر كود لتنفيذ منطق/إعداد
class ApprenticeAdmin(ExcelImportAdminMixin, BaseProgramAdmin):  # تعريف كلاس (Class)
    list_display = COMMON_LIST + ("معيد", "المستخدم")  # تعيين قيمة لمتغير/إعداد
    search_fields = COMMON_SEARCH + ("المستخدم",)  # تعيين قيمة لمتغير/إعداد
    list_filter = COMMON_FILTER + ("معيد",)  # تعيين قيمة لمتغير/إعداد


@admin.register(مسائي_ومعابر)  # سطر كود لتنفيذ منطق/إعداد
class EveningAdmin(ExcelImportAdminMixin, BaseProgramAdmin):  # تعريف كلاس (Class)
    list_display = COMMON_LIST + ("نوع_التكوين",)  # تعيين قيمة لمتغير/إعداد
    search_fields = COMMON_SEARCH  # تعيين قيمة لمتغير/إعداد
    list_filter = COMMON_FILTER + ("نوع_التكوين",)  # تعيين قيمة لمتغير/إعداد


from django.utils.html import format_html  # استيراد عناصر محددة من مكتبة/وحدة
from django import forms

@admin.register(CustomField)  # سطر كود لتنفيذ منطق/إعداد
class CustomFieldAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    list_display = ("label", "key", "program", "field_type", "required", "active", "order", "delete_link")

    list_filter = ("program", "field_type", "required", "active")  # تعيين قيمة لمتغير/إعداد
    search_fields = ("label", "key")  # تعيين قيمة لمتغير/إعداد
    readonly_fields = ("key",)  # تعيين قيمة لمتغير/إعداد
    ordering = ("program", "order", "id")  # تعيين قيمة لمتغير/إعداد

    def delete_link(self, obj):  # تعريف دالة (Function)
        url = reverse("admin:trainees_customfield_delete", args=[obj.pk])  # تعيين قيمة لمتغير/إعداد
        # إرجاع قيمة من الدالة
        return format_html('<a class="button" style="color:#a00;" href="{}">حذف</a>', url)
    delete_link.short_description = "حذف"  # تعيين قيمة لمتغير/إعداد

    class Media:  # تعريف كلاس (Class)
        css = {"all": ("trainees/admin_custom_fields_fix.css",)}  # تعيين قيمة لمتغير/إعداد




@admin.register(DismissalDecision)
class DismissalDecisionAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    list_display = ("trainee_name", "program", "decision_scope", "specialty", "decision_number", "disciplinary_record_number", "disciplinary_record_date", "status", "is_archived", "updated_at")
    list_filter = ("program", "decision_scope", "status", "is_archived")
    search_fields = ("trainee_name", "registration_number", "specialty", "decision_number", "disciplinary_record_number")
    readonly_fields = ("trainee_content_type", "trainee_object_id", "created_by", "updated_by", "created_at", "updated_at", "archived_at")
    ordering = ("program", "decision_scope", "is_archived", "specialty", "trainee_name")



@admin.register(SummonsRecord)
class SummonsRecordAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    list_display = ("trainee_name", "program", "summons_scope", "summons_type", "specialty", "document_number", "issue_date", "status", "updated_at")
    list_filter = ("program", "summons_scope", "summons_type", "status")
    search_fields = ("trainee_name", "registration_number", "specialty", "document_number")
    readonly_fields = ("trainee_content_type", "trainee_object_id", "created_by", "updated_by", "created_at", "updated_at")
    ordering = ("program", "summons_scope", "summons_type", "specialty", "trainee_name")


@admin.register(SanctionRecord)
class SanctionRecordAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    list_display = ("trainee_name", "program", "sanction_scope", "specialty", "document_number", "sanction_text", "disciplinary_record_number", "disciplinary_record_date", "status", "is_archived", "updated_at")
    list_filter = ("program", "sanction_scope", "status", "is_archived")
    search_fields = ("trainee_name", "registration_number", "specialty", "document_number", "sanction_text", "disciplinary_record_number")
    readonly_fields = ("trainee_content_type", "trainee_object_id", "created_by", "updated_by", "created_at", "updated_at", "archived_at")
    ordering = ("program", "sanction_scope", "is_archived", "specialty", "trainee_name")


# ----------------------------
# Auth (Users only) - Hide Groups and restrict user management to Admins
# ----------------------------
from django.contrib.auth.models import User, Group  # استيراد عناصر محددة من مكتبة/وحدة
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin  # استيراد عناصر محددة من مكتبة/وحدة
from django.contrib.auth.forms import UserChangeForm, AdminPasswordChangeForm  # استيراد عناصر محددة من مكتبة/وحدة
from django.utils.safestring import mark_safe  # استيراد عناصر محددة من مكتبة/وحدة


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
        value = int(value)
        return queryset.filter(_programs_count=value)


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
            "fields": (
                ("access_enabled",),
                ("access_start_date", "access_end_date"),
                ("can_access_admin_panel", "can_manage_all_programs"),
                ("can_view_reports", "can_export_data"),
                ("force_password_change",),
            ),
        }),
        ("صلاحيات الحضوري الأولي", {
            "classes": ("wide", "tc-permission-card", "tc-program-permissions"),
            "description": "صلاحيات خاصة بمتابعة متكوني الحضوري الأولي.",
            "fields": (("initial_view", "initial_add", "initial_change", "initial_delete"),),
        }),
        ("صلاحيات التمهين", {
            "classes": ("wide", "tc-permission-card", "tc-program-permissions"),
            "description": "صلاحيات خاصة بمتابعة متكوني التمهين.",
            "fields": (("apprentice_view", "apprentice_add", "apprentice_change", "apprentice_delete"),),
        }),
        ("صلاحيات المسائي والمعابر", {
            "classes": ("wide", "tc-permission-card", "tc-program-permissions"),
            "description": "صلاحيات خاصة بمتابعة متكوني المسائي والمعابر.",
            "fields": (("evening_view", "evening_add", "evening_change", "evening_delete"),),
        }),
    )

    def current_access_state(self, obj):
        # هذا الحقل المقروء فقط يعرض الحالة الفعلية الآن حتى لا يضطر المدير لحسابها يدويًا.
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
        date_part = value.strftime("%Y-%m-%d")
        time_part = value.strftime("%H:%M")

        return format_html(
            '<div class="tc-audit-datetime">'
            '<div class="tc-audit-datetime__date">{}</div>'
            '<div class="tc-audit-datetime__time">{}</div>'
            '</div>',
            date_part,
            time_part,
        )

    created_at_display.short_description = "تاريخ العملية"

    def actor_display(self, obj):
        # نعرض اسم من قام بالتعديل بشكل واضح داخل صفحة المستخدم.
        return get_user_display_name(obj.actor)
    actor_display.short_description = "تم بواسطة"

    def changed_fields_display(self, obj):
        return format_html(
            '<div style="min-width:170px;white-space:normal;line-height:1.8;">{}</div>',
            obj.changed_fields_labels(),
        )
    changed_fields_display.short_description = "الحقول المتغيرة"

    def notes_display(self, obj):
        return format_html(
            '<div class="tc-audit-notes">{}</div>',
            localize_access_audit_text(obj.notes),
        )

    notes_display.short_description = "ملاحظات"

    def before_after_preview(self, obj):
        # هذا الحقل يعرض ملخصًا نصيًا للتغييرات قبل/بعد داخل صندوق أوضح وأسهل قراءة.
        return format_html(
            '<div style="min-width:360px;max-width:460px;background:#f8faf8;border:1px solid #d8e6dd;border-radius:12px;padding:12px 14px;white-space:pre-line;line-height:1.9;box-shadow:inset 0 1px 0 rgba(255,255,255,0.65);">{}</div>',
            obj.before_after_summary(),
        )
    before_after_preview.short_description = "قبل / بعد"

class ArabicUserChangeForm(UserChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        password_field = self.fields.get("password")
        if password_field:
            password_field.help_text = mark_safe(
                'لا يتم حفظ كلمات المرور بصيغتها الأصلية، لذلك لا يمكن عرض كلمة مرور هذا المستخدم.'
            )


class ArabicAdminPasswordChangeForm(AdminPasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        usable_password = self.fields.get("usable_password")
        if usable_password:
            usable_password.label = "المصادقة باستخدام كلمة المرور"
            usable_password.help_text = (
                "تحديد ما إذا كان المستخدم سيتمكن من تسجيل الدخول باستعمال كلمة مرور أم لا. "
                "إذا تم تعطيل ذلك، فقد يظل قادرًا على المصادقة عبر وسائل أخرى مثل تسجيل الدخول الأحادي أو LDAP."
            )
            translated = []
            for value, label in usable_password.choices:
                label_text = str(label)
                if label_text == "Enabled":
                    label_text = "مفعّل"
                elif label_text == "Disabled":
                    label_text = "معطّل"
                translated.append((value, label_text))
            usable_password.choices = translated


class RestrictedUserAdmin(SuperuserOnlyAdminMixin, DjangoUserAdmin):  # تعريف كلاس (Class)
    form = ArabicUserChangeForm
    change_password_form = ArabicAdminPasswordChangeForm
    inlines = (UserAccessProfileInline, AccessAuditLogInline)

    # هذا العداد يُستخدم في شاشة التقارير لتحديد المستخدمين الذين يحتاجون متابعة خلال أسبوع.
    expiry_warning_days = 7
    list_display = (
        "username",
        "full_name_display",
        "email",
        "is_active",
        "admin_role_badge",
        "access_state_badge",
        "granted_programs_display",
        "access_end_display",
        "last_login",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", UserAccessStateFilter, UserProgramsCountFilter)
    search_fields = ("username", "first_name", "last_name", "email")
    actions = ("activate_selected_access", "disable_selected_access", "extend_access_7_days", "extend_access_15_days", "extend_access_30_days", "enable_force_password_change", "disable_force_password_change")
    change_list_template = "admin/auth/user/change_list.html"
    fieldsets = (
        ("بيانات الدخول", {
            "classes": ("wide", "tc-user-card", "tc-login-card"),
            "fields": ("username", "password"),
        }),
        ("المعلومات الشخصية", {
            "classes": ("wide", "tc-user-card", "tc-personal-card"),
            "fields": (("first_name", "last_name"), "email"),
        }),
        ("حالة الحساب", {
            "classes": ("wide", "tc-user-card", "tc-account-status-group"),
            "fields": (("is_active", "is_staff"), "is_superuser"),
            "description": "إعدادات الحساب الأساسية الخاصة بالنشاط، إمكانية دخول لوحة الإدارة، والصلاحيات العليا للمستخدم.",
        }),
        ("تواريخ مهمة", {
            "classes": ("wide", "tc-user-card", "tc-dates-card"),
            "fields": ("last_login", "date_joined"),
        }),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide", "tc-user-card", "tc-login-card"),
            "fields": ("username", "password1", "password2", "is_active", "is_superuser"),
        }),
    )

    class Media:
        css = {"all": ("admin/custom_admin.css",)}
        js = ("admin/permission_select_all.js",)

    def get_inline_instances(self, request, obj=None):
        # عند إنشاء مستخدم جديد لا نعرض Inline الصلاحيات
        # لأن signal في models.py ينشئ UserAccessProfile تلقائيًا،
        # وإذا ظهر الـ Inline في صفحة الإضافة سيحاول Django إنشاء سجل ثانٍ
        # لنفس المستخدم، وهذا يسبب خطأ UNIQUE على user_id.
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # هذا المسار يضيف صفحة تقارير إدارية مرتبطة بنفس قسم المستخدمين داخل لوحة الإدارة.
            path("access-reports/", self.admin_site.admin_view(self.access_reports_view), name="auth_user_access_reports"),
            # هذا المسار يصدّر تقرير الصلاحيات بصيغة CSV لمن يريد نسخة خارجية بدون تغيير شكل الواجهة.
            path("export-access-report/", self.admin_site.admin_view(self.export_access_report_csv), name="auth_user_export_access_report"),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        # نمرر رابط شاشة التقارير إلى القالب حتى نظهر زرًا سريعًا فوق قائمة المستخدمين.
        extra_context = extra_context or {}
        extra_context["access_reports_url"] = reverse("admin:auth_user_access_reports")
        extra_context["export_access_report_url"] = reverse("admin:auth_user_export_access_report")
        extra_context["expiry_warning_days"] = self.expiry_warning_days
        return super().changelist_view(request, extra_context=extra_context)

    def access_reports_view(self, request):
        # نبني تقريرًا إداريًا مختصرًا عن حالات الوصول والصلاحيات القريبة من الانتهاء.
        qs = self.get_queryset(request).order_by("username")
        users = list(qs)

        total_users = len(users)
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
                {"label": "إجمالي المستخدمين", "value": total_users, "color": "#175cd3"},
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
        # هذه الدالة تجمع منطق إنشاء سجل التدقيق في مكان واحد حتى نستخدمها من الحفظ والإجراءات الجماعية.
        changed_fields = diff_access_snapshots(before_data, after_data)
        AccessAuditLog.objects.create(
            actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            target_user=target_user,
            profile=profile,
            action=action,
            changed_fields=changed_fields,
            before_data=before_data or {},
            after_data=after_data or {},
            notes=notes or "",
        )

    def save_formset(self, request, form, formset, change):
        # هنا نلتقط أي تعديل تم من خلال Inline الصلاحيات داخل صفحة المستخدم.
        if getattr(formset, "model", None) is not UserAccessProfile:
            return super().save_formset(request, form, formset, change)

        before_map = {obj.pk: serialize_access_profile_for_audit(obj) for obj in formset.get_queryset()}
        response = super().save_formset(request, form, formset, change)

        for obj, changed_fields in getattr(formset, "changed_objects", []):
            before_data = before_map.get(obj.pk, {})
            after_data = serialize_access_profile_for_audit(obj)
            notes = build_access_audit_notes("تم تعديل الصلاحيات من داخل صفحة المستخدم.", changed_fields)
            self._log_access_audit(request, obj.user, obj, "update", before_data, after_data, notes=notes)

        for obj in getattr(formset, "new_objects", []):
            self._log_access_audit(
                request,
                obj.user,
                obj,
                "create",
                {},
                serialize_access_profile_for_audit(obj),
                notes="تم إنشاء ملف صلاحيات جديد من داخل لوحة الإدارة.",
            )

        for obj in getattr(formset, "deleted_objects", []):
            self._log_access_audit(
                request,
                getattr(obj, "user", None),
                None,
                "delete",
                before_map.get(obj.pk, serialize_access_profile_for_audit(obj)),
                {},
                notes="تم حذف ملف الصلاحيات من داخل لوحة الإدارة.",
            )
        return response

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # نجهز استعلام المستخدمين مع ملف الصلاحيات وحساب عدد الأنماط لتسريع العرض والفلاتر.
        return qs.select_related("access_profile").annotate(
            _programs_count=(
                Case(When(access_profile__initial_view=True, then=Value(1)), default=Value(0), output_field=IntegerField()) +
                Case(When(access_profile__apprentice_view=True, then=Value(1)), default=Value(0), output_field=IntegerField()) +
                Case(When(access_profile__evening_view=True, then=Value(1)), default=Value(0), output_field=IntegerField())
            )
        )


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
        state = profile.access_state_code()
        mapping = {
            "active": ("نشطة", "#067647"),
            "pending": ("لم تبدأ", "#b54708"),
            "expired": ("منتهية", "#b42318"),
            "disabled": ("معطلة", "#475467"),
        }
        label, color = mapping.get(state, ("غير معروفة", "#475467"))
        return format_html('<strong style="color:{};">{}</strong>', color, label)
    access_state_badge.short_description = "حالة الصلاحية"

    def granted_programs_display(self, obj):
        profile = self._profile(obj)
        if not profile:
            return "—"
        labels = profile.granted_program_labels()
        if not labels:
            return "بدون أنماط"
        return "، ".join(labels)
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
            if remaining < 0:
                suffix = f" (منذ {abs(remaining)} يوم)"
            else:
                suffix = f" (بعد {remaining} يوم)"
        return f"{profile.access_end_date:%Y-%m-%d}{suffix}"
    access_end_display.short_description = "نهاية الصلاحية"

    @admin.action(description="تفعيل الصلاحيات للمستخدمين المحددين")
    def activate_selected_access(self, request, queryset):
        updated = 0
        for user in queryset:
            profile, _ = UserAccessProfile.objects.get_or_create(user=user)
            if not profile.access_enabled:
                before_data = serialize_access_profile_for_audit(profile)
                profile.access_enabled = True
                profile.save(update_fields=["access_enabled", "updated_at"])
                self._log_access_audit(request, user, profile, "activate", before_data, serialize_access_profile_for_audit(profile), notes="تم تفعيل الصلاحيات عبر إجراء جماعي.")
                updated += 1
        self.message_user(request, f"تم تفعيل الصلاحيات لـ {updated} مستخدم/مستخدمين.", level=messages.SUCCESS)

    @admin.action(description="تعطيل الصلاحيات للمستخدمين المحددين")
    def disable_selected_access(self, request, queryset):
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
        self.message_user(request, f"تم تعطيل الصلاحيات لـ {updated} مستخدم/مستخدمين.", level=messages.WARNING)

    def _extend_access(self, request, queryset, days):
        # هذه الدالة الداخلية تمنع تكرار منطق التمديد بين 7 و15 و30 يومًا.
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
        # هذا التصدير يحفظ نسخة CSV من تقرير الصلاحيات مع الإبقاء على نفس شكل الواجهة القديمة.
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="user_access_report.csv"'
        import csv
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["اسم المستخدم", "الاسم الكامل", "مفعلة", "بداية الصلاحية", "نهاية الصلاحية", "الأيام المتبقية", "درجة الاستعجال", "الأنماط", "لوحة الإدارة", "إجبار تغيير كلمة المرور"])
        for user in self.get_queryset(request):
            profile = self._profile(user)
            if not profile:
                continue
            writer.writerow([
                user.username,
                user.get_full_name().strip(),
                "نعم" if profile.access_enabled else "لا",
                profile.access_start_date or "",
                profile.access_end_date or "",
                profile.days_until_expiry() if profile.days_until_expiry() is not None else "",
                profile.expiry_urgency_label(),
                "، ".join(profile.granted_program_labels()) if profile.granted_program_labels() else "",
                "نعم" if profile.can_access_admin_panel else "لا",
                "نعم" if profile.force_password_change else "لا",
            ])
        return response

register_auth_admin(admin.site)




class LegacyAccessAuditLogAdmin(admin.ModelAdmin):
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
        return format_html(
            '<div class="tc-audit-before-after">{}</div>',
            obj.before_after_summary(),
        )

    before_after_preview.short_description = "قبل / بعد"


    fieldsets = (
        (None, {
            "fields": (("created_at_display", "action"), ("target_user_display", "actor_display"), "profile")
        }),
        ("التغييرات", {
            "fields": ("changed_fields_display", "notes_display", "before_after_preview")
        }),
    )

@admin.register(دفعة)
class PromotionAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    form = PromotionAdminForm

    list_display = (
        "اسم_الدفعة",
        "رقم_الدورة",
        "السنة",
        "تاريخ_الدخول_الرسمي_منسق",
        "بداية_السداسي_2_منسق",
        "بداية_السداسي_3_منسق",
        "بداية_السداسي_4_منسق",
        "بداية_السداسي_5_منسق",
        "مفعلة",
        "زر_التعديل",
        "زر_الحذف",
    )
    list_filter = ("اسم_الدفعة", "رقم_الدورة", "السنة", "مفعلة")
    search_fields = ("السنة",)
    ordering = ("-السنة", "-رقم_الدورة")
    change_list_template = "admin/promotions_change_list.html"
    readonly_fields = ("اسم_الدفعة", "بداية_السداسي_1", "بداية_السداسي_2", "بداية_السداسي_3", "بداية_السداسي_4", "بداية_السداسي_5")
    fields = ("اسم_الدفعة", "رقم_الدورة", "السنة", "تاريخ_الدخول_الرسمي", "بداية_السداسي_1", "بداية_السداسي_2", "بداية_السداسي_3", "بداية_السداسي_4", "بداية_السداسي_5", "مفعلة")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if isinstance(formfield, forms.DateField):
            formfield.input_formats = DATE_INPUT_FORMATS
        return formfield

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get("مفعلة__exact") in {"0", "1"}:
            return qs
        return qs.filter(مفعلة=True)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("relink/", self.admin_site.admin_view(self.relink_view), name="trainees_دفعة_relink"),
        ]
        return custom + urls

    def تاريخ_الدخول_الرسمي_منسق(self, obj):
        return _fmt_date(obj, "تاريخ_الدخول_الرسمي")
    تاريخ_الدخول_الرسمي_منسق.short_description = "تاريخ الدخول الرسمي"

    def بداية_السداسي_2_منسق(self, obj):
        return _fmt_date(obj, "بداية_السداسي_2")
    بداية_السداسي_2_منسق.short_description = "بداية السداسي 2"

    def بداية_السداسي_3_منسق(self, obj):
        return _fmt_date(obj, "بداية_السداسي_3")
    بداية_السداسي_3_منسق.short_description = "بداية السداسي 3"

    def بداية_السداسي_4_منسق(self, obj):
        return _fmt_date(obj, "بداية_السداسي_4")
    بداية_السداسي_4_منسق.short_description = "بداية السداسي 4"

    def بداية_السداسي_5_منسق(self, obj):
        return _fmt_date(obj, "بداية_السداسي_5")
    بداية_السداسي_5_منسق.short_description = "بداية السداسي 5"

    def زر_التعديل(self, obj):
        url = reverse("admin:trainees_دفعة_change", args=[obj.pk])
        return format_html(
            '<a class="button" style="font-family:\'Times New Roman\',\'Times New Roman (Headings CS)\',serif!important;font-weight:900!important;min-height:20px!important;padding:3px 7px!important;font-size:12px!important;border-radius:10px!important;line-height:1.1!important;" href="{}"><b style="font-family:\'Times New Roman\',\'Times New Roman (Headings CS)\',serif!important;font-weight:900!important;">تعديل</b></a>',
            url,
        )
    زر_التعديل.short_description = "تعديل"

    def زر_الحذف(self, obj):
        url = reverse("admin:trainees_دفعة_delete", args=[obj.pk])
        return format_html(
            '<a class="button" style="font-family:\'Times New Roman\',\'Times New Roman (Headings CS)\',serif!important;font-weight:900!important;background:#b42318!important;color:#fff!important;min-height:20px!important;padding:4px 7px!important;font-size:12px!important;border-radius:10px!important;line-height:1.1!important;" href="{}"><b style="font-family:\'Times New Roman\',\'Times New Roman (Headings CS)\',serif!important;font-weight:900!important;">حذف</b></a>',
            url,
        )
    زر_الحذف.short_description = "حذف"

    def _recompute_trainees_for_promotion(self, promotion):
        """إعادة حساب السداسي للمتكونين المرتبطين بدفعة بعد الدمج."""
        recalculated = 0
        models = [حضوري_أولي, تمهين, مسائي_ومعابر]
        for model in models:
            pending = []
            field_names = {f.name for f in model._meta.get_fields()}
            cohort_starts = cohort_start_dates_for_model(model)
            for obj in model.objects.filter(الدفعة_id=promotion.pk).iterator(chunk_size=2000):
                changed = False
                if bool(getattr(obj, "معيد", False)) and hasattr(obj, "تاريخ_التكوين_السابق_للمعيدين"):
                    from .semester_utils import normalize_repeater_training_dates
                    if normalize_repeater_training_dates(obj):
                        changed = True
                semester_label = compute_semester_for_trainee(
                    promotion,
                    getattr(obj, "تاريخ_بداية_التكوين", None),
                    getattr(obj, "تاريخ_نهاية_التكوين", None),
                    is_repeater=bool(getattr(obj, "معيد", False)),
                    cohort_starts=cohort_starts,
                    original_end_date=getattr(obj, "تاريخ_التكوين_السابق_للمعيدين", None),
                )
                if obj.السداسي != semester_label:
                    obj.السداسي = semester_label
                    changed = True
                if changed:
                    pending.append(obj)
            if pending:
                update_fields = ["السداسي"]
                if "تاريخ_نهاية_التكوين" in field_names:
                    update_fields.append("تاريخ_نهاية_التكوين")
                if "تاريخ_التكوين_السابق_للمعيدين" in field_names:
                    update_fields.append("تاريخ_التكوين_السابق_للمعيدين")
                model.objects.bulk_update(pending, update_fields, batch_size=1000)
                recalculated += len(pending)
        return recalculated

    def _merge_duplicate_promotion(self, request, source, target):
        """دمج دفعة خاطئة داخل دفعة صحيحة موجودة بدل إظهار خطأ القيد الفريد."""
        if not source.pk or not target.pk or source.pk == target.pk:
            return 0, 0
        source_label = str(source)
        target_label = str(target)
        moved = 0
        for model in [حضوري_أولي, تمهين, مسائي_ومعابر]:
            moved += model.objects.filter(الدفعة_id=source.pk).update(الدفعة=target)
        source.delete()
        refresh_all_promotion_semester_starts()
        recalculated = self._recompute_trainees_for_promotion(target)
        self.message_user(
            request,
            f"تم دمج الدفعة الخاطئة {source_label} داخل الدفعة الموجودة {target_label}. تم نقل {moved} متكون، وإعادة حساب السداسي لـ {recalculated} سجل. لم يتم إنشاء دفعة مكررة.",
            level=messages.SUCCESS,
        )
        return moved, recalculated

    def _delete_empty_suspicious_promotions(self):
        """حذف الدفعات الخاطئة الفارغة جداً مثل سبتمبر 2053 بعد إعادة الربط.

        هذه الدفعات تنتج غالباً من رقم تسجيل زائد مثل 00452253R.
        بعد إصلاح التحليل وإعادة الربط تنتقل المتكونون إلى دفعة 2025،
        فنحذف دفعة 2053 إذا لم يعد يرتبط بها أي متكون.
        """
        current_year = timezone.localdate().year
        deleted = 0
        suspicious = دفعة.objects.filter(مفعلة=True, السنة__gt=current_year + 10)
        for promotion in suspicious:
            has_trainees = any(
                model.objects.filter(الدفعة_id=promotion.pk).exists()
                for model in (حضوري_أولي, تمهين, مسائي_ومعابر)
            )
            if has_trainees:
                continue
            try:
                promotion.delete()
                deleted += 1
            except Exception:
                pass
        return deleted

    def save_model(self, request, obj, form, change):
        merge_target = getattr(form, "merge_target", None)
        if change and merge_target and obj.pk and obj.pk != merge_target.pk:
            self._merge_duplicate_promotion(request, obj, merge_target)
            obj.pk = merge_target.pk
            obj.id = merge_target.pk
            obj._merged_into_existing = True
            return
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        self.message_user(request, "تم حفظ الدفعة بنجاح.", level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:trainees_دفعة_changelist"))

    def response_change(self, request, obj):
        if getattr(obj, "_merged_into_existing", False):
            return HttpResponseRedirect(reverse("admin:trainees_دفعة_changelist"))
        self.message_user(request, "تم تعديل الدفعة بنجاح.", level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:trainees_دفعة_changelist"))

    def response_delete(self, request, obj_display, obj_id):
        self.message_user(request, "تم حذف الدفعة بنجاح.", level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:trainees_دفعة_changelist"))

    def relink_view(self, request):
        refresh_all_promotion_semester_starts()
        total = linked = updated = invalid = unmatched = unchanged = 0
        promotion_map = {
            (p.رقم_الدورة, p.السنة): p
            for p in دفعة.objects.filter(مفعلة=True).only("id", "رقم_الدورة", "السنة", "بداية_السداسي_1", "بداية_السداسي_2", "بداية_السداسي_3", "بداية_السداسي_4", "بداية_السداسي_5")
        }
        models = [حضوري_أولي, تمهين, مسائي_ومعابر]
        for model in models:
            pending = []
            field_names = {f.name for f in model._meta.get_fields()}
            cohort_starts = cohort_start_dates_for_model(model)
            for obj in model.objects.select_related("الدفعة").iterator(chunk_size=2000):
                total += 1
                session_no, year_value = resolve_session_year(getattr(obj, "رقم_التسجيل", ""), getattr(obj, "تاريخ_بداية_التكوين", None))
                if not session_no or not year_value:
                    invalid += 1
                    continue
                promotion = promotion_map.get((session_no, year_value))
                if not promotion:
                    unmatched += 1
                    continue
                changed = False
                if obj.الدفعة_id != promotion.id:
                    obj.الدفعة = promotion
                    linked += 1
                    changed = True
                if bool(getattr(obj, "معيد", False)) and hasattr(obj, "تاريخ_التكوين_السابق_للمعيدين"):
                    from .semester_utils import normalize_repeater_training_dates
                    normalize_repeater_training_dates(obj)
                semester_label = compute_semester_for_trainee(
                    promotion,
                    getattr(obj, "تاريخ_بداية_التكوين", None),
                    getattr(obj, "تاريخ_نهاية_التكوين", None),
                    is_repeater=bool(getattr(obj, "معيد", False)),
                    cohort_starts=cohort_starts,
                    original_end_date=getattr(obj, "تاريخ_التكوين_السابق_للمعيدين", None),
                )
                if obj.السداسي != semester_label:
                    obj.السداسي = semester_label
                    updated += 1
                    changed = True
                if changed:
                    pending.append(obj)
                else:
                    unchanged += 1
            if pending:
                update_fields = ["الدفعة", "السداسي"]
                if "تاريخ_نهاية_التكوين" in field_names:
                    update_fields.append("تاريخ_نهاية_التكوين")
                if "تاريخ_التكوين_السابق_للمعيدين" in field_names:
                    update_fields.append("تاريخ_التكوين_السابق_للمعيدين")
                model.objects.bulk_update(pending, update_fields, batch_size=1000)
        deleted_suspicious = self._delete_empty_suspicious_promotions()
        cleanup_msg = f"، تم حذف دفعات خاطئة فارغة: {deleted_suspicious}" if deleted_suspicious else ""
        self.message_user(
            request,
            f"تمت إعادة ربط المتكوّنين بالدفعات بنجاح. إجمالي السجلات: {total}، تم الربط: {linked}، تم تحديث السداسي: {updated}، السجلات الصحيحة أصلًا: {unchanged}، أرقام التسجيل غير الصالحة: {invalid}، بلا دفعة مطابقة: {unmatched}{cleanup_msg}.",
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect(reverse("admin:trainees_دفعة_changelist"))




@admin.register(UserAccountAuditLog)
class UserAccountAuditLogAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    list_per_page = 100
    list_display = ("created_at", "actor", "target_user", "action", "ip_address", "short_notes")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "target_user__username", "notes")
    ordering = ("-created_at", "-id")
    readonly_fields = ("created_at", "actor", "target_user", "action", "changed_fields", "before_data", "after_data", "notes", "ip_address")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def short_notes(self, obj):
        return (obj.notes or "—")[:120]
    short_notes.short_description = "ملاحظات"


@admin.register(ComprehensiveAuditLog)
class ComprehensiveAuditLogAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    list_per_page = 100
    list_display = ("created_at", "user_or_snapshot", "action", "method", "status_code", "success", "screen_name", "object_repr", "ip_address")
    list_filter = ("action", "method", "success", "created_at")
    search_fields = ("username_snapshot", "user__username", "screen_name", "view_name", "object_repr", "path", "details", "model_label", "object_pk")
    ordering = ("-created_at", "-id")
    readonly_fields = ("created_at", "user", "username_snapshot", "action", "method", "status_code", "success", "screen_name", "view_name", "model_label", "object_pk", "object_repr", "path", "query_string", "details", "before_data", "after_data", "ip_address", "user_agent", "session_key")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def user_or_snapshot(self, obj):
        return obj.username_snapshot or get_user_display_name(obj.user)
    user_or_snapshot.short_description = "المستخدم"

@admin.register(ActivityLog)
class ActivityLogAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    change_list_template = "admin/activitylog_change_list.html"
    actions = ("delete_selected_logs",)
    actions_selection_counter = False
    list_per_page = 100
    list_max_show_all = 200
    show_full_result_count = False
    list_display = ("created_at", "user", "action", "program", "object_repr", "path", "ip_address")
    list_filter = ("action", "program", "created_at")
    search_fields = ("user__username", "object_repr", "details", "path")
    ordering = ("-created_at", "-id")
    readonly_fields = ("created_at", "user", "action", "program", "object_repr", "details", "path", "ip_address")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def _build_activitylog_context(self, request, *, title, count, delete_scope, submit_label, cancel_label="إلغاء", extra=None):
        changelist_url = reverse("admin:trainees_activitylog_changelist")
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": title,
            "model_verbose": "سجل النشاط",
            "count": count,
            "delete_scope": delete_scope,
            "submit_label": submit_label,
            "cancel_label": cancel_label,
            "changelist_url": changelist_url,
        }
        if extra:
            context.update(extra)
        return context

    def _get_filtered_queryset(self, request):
        changelist = self.get_changelist_instance(request)
        return changelist.get_queryset(request)

    def _clean_querystring(self, request):
        querydict = request.GET.copy()
        for key in ["p", "_changelist_filters"]:
            querydict.pop(key, None)
        return querydict.urlencode()

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("clear-all/", self.admin_site.admin_view(self.clear_all_view), name="trainees_activitylog_clear_all"),
            path("clear-filtered/", self.admin_site.admin_view(self.clear_filtered_view), name="trainees_activitylog_clear_filtered"),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        querystring = self._clean_querystring(request)
        clear_filtered_url = reverse("admin:trainees_activitylog_clear_filtered")
        if querystring:
            clear_filtered_url = f"{clear_filtered_url}?{querystring}"
        extra_context["clear_all_url"] = reverse("admin:trainees_activitylog_clear_all")
        extra_context["clear_filtered_url"] = clear_filtered_url
        extra_context["has_active_filters"] = bool(querystring)
        extra_context["page_title_ar"] = "سجل النشاط"
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description="احذف سجل النشاط المحددة")
    def delete_selected_logs(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "فقط المدير العام يمكنه حذف السجلات المحددة.",
                level=messages.ERROR,
            )
            return

        count = queryset.count()
        if count == 0:
            self.message_user(request, "لم يتم تحديد أي سجل للحذف.", level=messages.WARNING)
            return

        queryset.delete()
        self.message_user(
            request,
            f"تم حذف {count} سجل/سجلات محددة بنجاح.",
            level=messages.SUCCESS,
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def clear_all_view(self, request):
        if not request.user.is_superuser:
            self.message_user(request, "فقط المدير العام يمكنه حذف كامل سجل النشاط.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:trainees_activitylog_changelist"))

        changelist_url = reverse("admin:trainees_activitylog_changelist")
        count = ActivityLog.objects.count()
        if request.method == "POST":
            if request.POST.get("confirm") == "yes":
                ActivityLog.objects.all().delete()
                self.message_user(request, f"تم حذف كامل سجل النشاط ({count} سجل) بنجاح.", level=messages.SUCCESS)
            else:
                self.message_user(request, "تم إلغاء عملية حذف سجل النشاط.", level=messages.INFO)
            return HttpResponseRedirect(changelist_url)

        context = self._build_activitylog_context(
            request,
            title="حذف كامل سجل النشاط",
            count=count,
            delete_scope="كامل السجل",
            submit_label="نعم، احذف الكل",
        )
        return render(request, "admin/delete_all_confirm.html", context)

    def clear_filtered_view(self, request):
        if not request.user.is_superuser:
            self.message_user(request, "فقط المدير العام يمكنه حذف السجلات المفلترة.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:trainees_activitylog_changelist"))

        changelist_url = reverse("admin:trainees_activitylog_changelist")
        querystring = self._clean_querystring(request)
        if querystring:
            changelist_url = f"{changelist_url}?{querystring}"

        queryset = self._get_filtered_queryset(request)
        count = queryset.count()
        if request.method == "POST":
            if request.POST.get("confirm") == "yes":
                deleted_count = queryset.count()
                queryset.delete()
                self.message_user(request, f"تم حذف {deleted_count} سجل/سجلات من النتائج الحالية بنجاح.", level=messages.SUCCESS)
            else:
                self.message_user(request, "تم إلغاء عملية حذف السجلات المفلترة.", level=messages.INFO)
            return HttpResponseRedirect(changelist_url)

        context = self._build_activitylog_context(
            request,
            title="حذف النتائج الحالية من سجل النشاط",
            count=count,
            delete_scope="النتائج الحالية حسب الفلاتر والبحث",
            submit_label="نعم، احذف النتائج الحالية",
            extra={
                "querystring": querystring,
                "filters_note": "سيتم حذف كل السجلات المطابقة للبحث والفلاتر الحالية، وليس فقط سجلات الصفحة الظاهرة.",
            },
        )
        return render(request, "admin/delete_all_confirm.html", context)


@admin.register(AttendanceAction)
class AttendanceActionAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    list_display = ("program", "year", "month", "trainee_name", "trainee_specialty", "action_type", "trigger_count", "status", "is_archived", "document_number", "send_date")
    list_filter = ("program", "action_type", "status", "is_archived", "year", "month")
    search_fields = ("trainee_name", "trainee_specialty", "trainee_address", "document_number")
    readonly_fields = ("program", "month", "year", "batch", "specialty", "trainee_content_type", "trainee_object_id", "trainee_name", "trainee_specialty", "trainee_address", "action_type", "trigger_count", "threshold_value", "is_archived", "archived_at", "created_by", "updated_by", "created_at", "updated_at")
    ordering = ("-year", "-month", "program", "trainee_name")



@admin.register(UserAttendanceSummaryArchive)
class UserAttendanceSummaryArchiveAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
    delete_requires_superuser = True
    list_display = ("title", "program", "row_count", "total_present", "total_absent", "created_by", "created_at")
    list_filter = ("program", "created_at")
    search_fields = ("title", "created_by__username")
    readonly_fields = ("program", "title", "filters_json", "rows_json", "row_count", "total_present", "total_absent", "created_by", "created_at")
    ordering = ("-created_at", "-id")


# ----------------------------
# Attendance slots system - نظام الغياب الجديد بالحصة
# ----------------------------
try:
    from .attendance_slots_models import AttendanceSlotSheet, AttendanceSlotCell

    @admin.register(AttendanceSlotSheet)
    class AttendanceSlotSheetAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
        delete_requires_superuser = True
        list_display = ("البرنامج", "التخصص", "الدفعة", "الشهر", "السنة", "يوم_الدراسة_1", "يوم_الدراسة_2", "يوم_الدراسة_3", "يوم_الدراسة_4", "يوم_الدراسة_5", "created_at")
        list_filter = ("البرنامج", "الشهر", "السنة")
        search_fields = ("التخصص",)
        readonly_fields = ("created_by", "created_at", "updated_at")
        ordering = ("-السنة", "-الشهر", "البرنامج", "التخصص")

    @admin.register(AttendanceSlotCell)
    class AttendanceSlotCellAdmin(AdminPanelPermissionMixin, admin.ModelAdmin):
        delete_requires_superuser = True
        list_display = ("الكشف", "trainee_id", "التاريخ", "رقم_الحصة", "الحالة", "recorded_by", "updated_at")
        list_filter = ("الحالة", "رقم_الحصة", "التاريخ")
        search_fields = ("trainee_id",)
        readonly_fields = ("created_at", "updated_at")
        ordering = ("-التاريخ", "trainee_id", "رقم_الحصة")
except admin.sites.AlreadyRegistered:
    pass
