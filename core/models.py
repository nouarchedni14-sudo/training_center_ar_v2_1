from django.conf import settings
from django.db import models
from django.utils import timezone


class SystemConfiguration(models.Model):
    MODE_STANDALONE = "standalone"
    MODE_LAN_SERVER = "lan_server"
    MODE_HYBRID = "hybrid"
    MODE_CHOICES = [
        (MODE_STANDALONE, "محلي على جهاز واحد"),
        (MODE_LAN_SERVER, "سيرفر داخل الشبكة المحلية"),
        (MODE_HYBRID, "مختلط: محلي + تحديثات/دعم عند توفر الإنترنت"),
    ]

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    organization_name = models.CharField(max_length=255, blank=True, verbose_name="اسم المؤسسة")
    installation_id = models.CharField(max_length=64, unique=True, blank=True, verbose_name="معرّف التثبيت")
    app_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_LAN_SERVER, verbose_name="وضع التشغيل")
    allow_remote_updates = models.BooleanField(default=False, verbose_name="تفعيل فحص التحديثات عبر الإنترنت")
    developer_support_enabled = models.BooleanField(default=False, verbose_name="تفعيل الدعم الفني للمطور")
    update_server_url = models.URLField(blank=True, verbose_name="رابط خادم التحديث")
    current_version = models.CharField(max_length=32, blank=True, verbose_name="الإصدار الحالي")
    latest_version = models.CharField(max_length=32, blank=True, verbose_name="آخر إصدار معروف")
    update_available = models.BooleanField(default=False, verbose_name="يوجد تحديث")
    update_required = models.BooleanField(default=False, verbose_name="التحديث إجباري")
    update_message = models.TextField(blank=True, verbose_name="رسالة التحديث")
    update_download_url = models.URLField(blank=True, verbose_name="رابط تنزيل التحديث")
    last_update_check_at = models.DateTimeField(blank=True, null=True, verbose_name="آخر فحص للتحديث")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "إعداد النظام"
        verbose_name_plural = "إعدادات النظام"
        permissions = [
            ("manage_system_settings", "Can manage system settings"),
            ("check_system_updates", "Can check system updates"),
            ("view_system_health", "Can view system health and error logs"),
            ("manage_license_info", "Can manage license information"),
        ]

    def __str__(self):
        return self.organization_name or "إعداد النظام"

    @classmethod
    def get_solo(cls):
        defaults = {
            "current_version": getattr(settings, "APP_VERSION", "1.0.0"),
            "app_mode": getattr(settings, "APP_MODE", cls.MODE_LAN_SERVER),
            "allow_remote_updates": getattr(settings, "ALLOW_REMOTE_UPDATES", False),
            "developer_support_enabled": getattr(settings, "DEVELOPER_SUPPORT_ENABLED", False),
            "update_server_url": getattr(settings, "UPDATE_SERVER_URL", ""),
        }
        obj, _changed = cls.objects.get_or_create(singleton_key=1, defaults=defaults)
        fields_to_update = []
        for field_name, value in defaults.items():
            if not getattr(obj, field_name):
                setattr(obj, field_name, value)
                fields_to_update.append(field_name)
        if not obj.installation_id:
            obj.installation_id = timezone.now().strftime("TC-%Y%m%d-%H%M%S")
            fields_to_update.append("installation_id")
        if fields_to_update:
            obj.save(update_fields=fields_to_update + ["updated_at"])
        return obj


class LicenseInfo(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_TRIAL = "trial"
    STATUS_EXPIRED = "expired"
    STATUS_SUSPENDED = "suspended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "نشط"),
        (STATUS_TRIAL, ""),
        (STATUS_EXPIRED, "منتهي"),
        (STATUS_SUSPENDED, "معلّق"),
    ]

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    customer_name = models.CharField(max_length=255, blank=True, verbose_name="اسم العميل/المؤسسة")
    license_code = models.CharField(max_length=128, blank=True, verbose_name="رمز الترخيص")
    license_status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_TRIAL, verbose_name="حالة الترخيص")
    support_expires_at = models.DateField(blank=True, null=True, verbose_name="انتهاء الدعم الفني")
    max_devices = models.PositiveIntegerField(default=1, verbose_name="الحد الأقصى للأجهزة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات الترخيص")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "معلومات الترخيص"
        verbose_name_plural = "معلومات النسخة والترخيص"

    def __str__(self):
        return self.customer_name or "معلومات النسخة والترخيص"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(singleton_key=1)
        return obj


class UpdateCheckLog(models.Model):
    checked_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت الفحص")
    success = models.BooleanField(default=False, verbose_name="نجح الفحص")
    requested_version = models.CharField(max_length=32, blank=True, verbose_name="الإصدار المُرسل")
    received_version = models.CharField(max_length=32, blank=True, verbose_name="الإصدار المستلم")
    message = models.TextField(blank=True, verbose_name="الرسالة")
    details = models.JSONField(default=dict, blank=True, verbose_name="تفاصيل إضافية")

    class Meta:
        verbose_name = "سجل فحص تحديث"
        verbose_name_plural = "سجل فحص التحديثات"
        ordering = ["-checked_at"]

    def __str__(self):
        state = "ناجح" if self.success else "فشل"
        return f"{state} - {self.checked_at:%Y-%m-%d %H:%M}"


class SystemHealthLog(models.Model):
    LEVEL_OK = "ok"
    LEVEL_WARNING = "warning"
    LEVEL_ERROR = "error"
    LEVEL_CHOICES = [
        (LEVEL_OK, "سليم"),
        (LEVEL_WARNING, "تحذير"),
        (LEVEL_ERROR, "خطأ"),
    ]

    checked_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت التسجيل")
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default=LEVEL_OK, verbose_name="المستوى")
    component = models.CharField(max_length=64, verbose_name="المكوّن")
    message = models.CharField(max_length=255, verbose_name="الرسالة")
    details = models.JSONField(default=dict, blank=True, verbose_name="تفاصيل")

    class Meta:
        verbose_name = "سجل صحة النظام"
        verbose_name_plural = "سجل صحة النظام"
        ordering = ["-checked_at"]

    def __str__(self):
        return f"{self.get_level_display()} - {self.component}"


class SystemErrorLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت الخطأ")
    source = models.CharField(max_length=64, blank=True, verbose_name="المصدر")
    path = models.CharField(max_length=255, blank=True, verbose_name="المسار")
    user_display = models.CharField(max_length=150, blank=True, verbose_name="المستخدم")
    error_type = models.CharField(max_length=128, blank=True, verbose_name="نوع الخطأ")
    message = models.TextField(verbose_name="رسالة الخطأ")
    traceback_text = models.TextField(blank=True, verbose_name="تفاصيل التتبع")
    resolved = models.BooleanField(default=False, verbose_name="تمت المعالجة")
    details = models.JSONField(default=dict, blank=True, verbose_name="بيانات إضافية")

    class Meta:
        verbose_name = "سجل خطأ"
        verbose_name_plural = "سجل الأخطاء"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.error_type or 'Error'} - {self.created_at:%Y-%m-%d %H:%M}"
