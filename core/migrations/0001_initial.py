from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SystemConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton_key", models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ("organization_name", models.CharField(blank=True, max_length=255, verbose_name="اسم المؤسسة")),
                ("installation_id", models.CharField(blank=True, max_length=64, unique=True, verbose_name="معرّف التثبيت")),
                ("app_mode", models.CharField(choices=[("standalone", "محلي على جهاز واحد"), ("lan_server", "سيرفر داخل الشبكة المحلية"), ("hybrid", "مختلط: محلي + تحديثات/دعم عند توفر الإنترنت")], default="lan_server", max_length=20, verbose_name="وضع التشغيل")),
                ("allow_remote_updates", models.BooleanField(default=False, verbose_name="تفعيل فحص التحديثات عبر الإنترنت")),
                ("developer_support_enabled", models.BooleanField(default=False, verbose_name="تفعيل الدعم الفني للمطور")),
                ("update_server_url", models.URLField(blank=True, verbose_name="رابط خادم التحديث")),
                ("current_version", models.CharField(blank=True, max_length=32, verbose_name="الإصدار الحالي")),
                ("latest_version", models.CharField(blank=True, max_length=32, verbose_name="آخر إصدار معروف")),
                ("update_available", models.BooleanField(default=False, verbose_name="يوجد تحديث")),
                ("update_required", models.BooleanField(default=False, verbose_name="التحديث إجباري")),
                ("update_message", models.TextField(blank=True, verbose_name="رسالة التحديث")),
                ("update_download_url", models.URLField(blank=True, verbose_name="رابط تنزيل التحديث")),
                ("last_update_check_at", models.DateTimeField(blank=True, null=True, verbose_name="آخر فحص للتحديث")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "إعداد النظام", "verbose_name_plural": "إعدادات النظام"},
        ),
        migrations.CreateModel(
            name="UpdateCheckLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("checked_at", models.DateTimeField(auto_now_add=True, verbose_name="وقت الفحص")),
                ("success", models.BooleanField(default=False, verbose_name="نجح الفحص")),
                ("requested_version", models.CharField(blank=True, max_length=32, verbose_name="الإصدار المُرسل")),
                ("received_version", models.CharField(blank=True, max_length=32, verbose_name="الإصدار المستلم")),
                ("message", models.TextField(blank=True, verbose_name="الرسالة")),
                ("details", models.JSONField(blank=True, default=dict, verbose_name="تفاصيل إضافية")),
            ],
            options={"verbose_name": "سجل فحص تحديث", "verbose_name_plural": "سجل فحص التحديثات", "ordering": ["-checked_at"]},
        ),
    ]
