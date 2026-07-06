from django.apps import AppConfig


class SyncCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sync_core"
    verbose_name = "إعدادات المزامنة المركزية"

    def ready(self):
        # ربط إشارات الحفظ والحذف بعد جاهزية تطبيقات Django.
        # إذا كانت جداول المزامنة غير منشأة بعد، يتم تجاهل أخطاء التسجيل بأمان.
        try:
            from . import signals  # noqa: F401
            signals.connect_central_office_cleanup_signal()
            signals.connect_sync_tracking_signals()
        except Exception:
            # لا نريد أن يتوقف تشغيل الخادم بسبب إعداد ناقص في مرحلة التجهيز.
            pass
