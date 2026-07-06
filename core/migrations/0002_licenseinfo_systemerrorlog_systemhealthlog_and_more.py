from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="systemconfiguration",
            options={
                "verbose_name": "إعداد النظام",
                "verbose_name_plural": "إعدادات النظام",
                "permissions": [
                    ("manage_system_settings", "Can manage system settings"),
                    ("check_system_updates", "Can check system updates"),
                    ("view_system_health", "Can view system health and error logs"),
                    ("manage_license_info", "Can manage license information"),
                ],
            },
        ),
        migrations.CreateModel(
            name="LicenseInfo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton_key", models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ("customer_name", models.CharField(blank=True, max_length=255, verbose_name="اسم العميل/المؤسسة")),
                ("license_code", models.CharField(blank=True, max_length=128, verbose_name="رمز الترخيص")),
                ("license_status", models.CharField(choices=[("active", "نشط"), ("trial", ""), ("expired", "منتهي"), ("suspended", "معلّق")], default="trial", max_length=16, verbose_name="حالة الترخيص")),
                ("support_expires_at", models.DateField(blank=True, null=True, verbose_name="انتهاء الدعم الفني")),
                ("max_devices", models.PositiveIntegerField(default=1, verbose_name="الحد الأقصى للأجهزة")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات الترخيص")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "معلومات الترخيص", "verbose_name_plural": "معلومات النسخة والترخيص"},
        ),
        migrations.CreateModel(
            name="SystemErrorLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="وقت الخطأ")),
                ("source", models.CharField(blank=True, max_length=64, verbose_name="المصدر")),
                ("path", models.CharField(blank=True, max_length=255, verbose_name="المسار")),
                ("user_display", models.CharField(blank=True, max_length=150, verbose_name="المستخدم")),
                ("error_type", models.CharField(blank=True, max_length=128, verbose_name="نوع الخطأ")),
                ("message", models.TextField(verbose_name="رسالة الخطأ")),
                ("traceback_text", models.TextField(blank=True, verbose_name="تفاصيل التتبع")),
                ("resolved", models.BooleanField(default=False, verbose_name="تمت المعالجة")),
                ("details", models.JSONField(blank=True, default=dict, verbose_name="بيانات إضافية")),
            ],
            options={"verbose_name": "سجل خطأ", "verbose_name_plural": "سجل الأخطاء", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SystemHealthLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("checked_at", models.DateTimeField(auto_now_add=True, verbose_name="وقت التسجيل")),
                ("level", models.CharField(choices=[("ok", "سليم"), ("warning", "تحذير"), ("error", "خطأ")], default="ok", max_length=16, verbose_name="المستوى")),
                ("component", models.CharField(max_length=64, verbose_name="المكوّن")),
                ("message", models.CharField(max_length=255, verbose_name="الرسالة")),
                ("details", models.JSONField(blank=True, default=dict, verbose_name="تفاصيل")),
            ],
            options={"verbose_name": "سجل صحة النظام", "verbose_name_plural": "سجل صحة النظام", "ordering": ["-checked_at"]},
        ),
    ]
