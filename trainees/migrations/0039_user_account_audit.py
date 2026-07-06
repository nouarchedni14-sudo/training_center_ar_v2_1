from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0038_fix_accessauditlog_schema"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAccountAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[
                    ("login_failed", "محاولة دخول فاشلة"),
                    ("login_denied_window", "منع دخول بسبب نافذة الصلاحية"),
                    ("access_enabled", "تفعيل الحساب"),
                    ("access_disabled", "تعطيل الحساب"),
                    ("access_window_changed", "تغيير نافذة الصلاحية"),
                    ("role_changed", "تغيير الدور"),
                    ("sensitive_update", "تحديث إعداد حساس"),
                    ("password_force_enabled", "تفعيل إجبار تغيير كلمة المرور"),
                    ("password_force_disabled", "إلغاء إجبار تغيير كلمة المرور"),
                ], default="sensitive_update", max_length=40, verbose_name="نوع العملية")),
                ("changed_fields", models.JSONField(blank=True, default=list, verbose_name="الحقول المتغيرة")),
                ("before_data", models.JSONField(blank=True, default=dict, verbose_name="القيم قبل التغيير")),
                ("after_data", models.JSONField(blank=True, default=dict, verbose_name="القيم بعد التغيير")),
                ("notes", models.TextField(blank=True, default="", verbose_name="ملاحظات")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ العملية")),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="performed_sensitive_account_audits", to=settings.AUTH_USER_MODEL, verbose_name="تم بواسطة")),
                ("target_user", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="sensitive_account_audits", to=settings.AUTH_USER_MODEL, verbose_name="المستخدم المستهدف")),
            ],
            options={
                "verbose_name": "سجل تدقيق الحسابات الحساسة",
                "verbose_name_plural": "سجل تدقيق الحسابات الحساسة",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
