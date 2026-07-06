from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0042_merge_20260409_1444"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ComprehensiveAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username_snapshot", models.CharField(blank=True, default="", max_length=150, verbose_name="اسم المستخدم وقت العملية")),
                ("action", models.CharField(choices=[("screen_view", "فتح شاشة"), ("request", "طلب"), ("mutation", "عملية تغيير"), ("auth", "مصادقة"), ("error", "خطأ")], default="request", max_length=20, verbose_name="نوع السجل")),
                ("method", models.CharField(blank=True, default="GET", max_length=10, verbose_name="الطريقة")),
                ("status_code", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="حالة الاستجابة")),
                ("success", models.BooleanField(default=True, verbose_name="نجحت العملية")),
                ("screen_name", models.CharField(blank=True, default="", max_length=255, verbose_name="اسم الشاشة")),
                ("view_name", models.CharField(blank=True, default="", max_length=255, verbose_name="اسم العرض")),
                ("model_label", models.CharField(blank=True, default="", max_length=255, verbose_name="نوع الكيان")),
                ("object_pk", models.CharField(blank=True, default="", max_length=64, verbose_name="معرف السجل")),
                ("object_repr", models.CharField(blank=True, default="", max_length=255, verbose_name="وصف السجل")),
                ("path", models.CharField(blank=True, default="", max_length=500, verbose_name="المسار")),
                ("query_string", models.TextField(blank=True, default="", verbose_name="نص الاستعلام")),
                ("details", models.TextField(blank=True, default="", verbose_name="تفاصيل")),
                ("before_data", models.JSONField(blank=True, default=dict, verbose_name="القيم قبل التغيير")),
                ("after_data", models.JSONField(blank=True, default=dict, verbose_name="القيم بعد التغيير")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP")),
                ("user_agent", models.TextField(blank=True, default="", verbose_name="المتصفح/العميل")),
                ("session_key", models.CharField(blank=True, default="", max_length=64, verbose_name="الجلسة")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاريخ العملية")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="comprehensive_audit_logs", to=settings.AUTH_USER_MODEL, verbose_name="المستخدم")),
            ],
            options={
                "verbose_name": "السجل الشامل للعمليات",
                "verbose_name_plural": "السجل الشامل للعمليات",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="comprehensiveauditlog",
            index=models.Index(fields=["-created_at"], name="trainees_co_created_dcf257_idx"),
        ),
        migrations.AddIndex(
            model_name="comprehensiveauditlog",
            index=models.Index(fields=["action", "success"], name="trainees_co_action_363f55_idx"),
        ),
        migrations.AddIndex(
            model_name="comprehensiveauditlog",
            index=models.Index(fields=["view_name"], name="trainees_co_view_na_c03e65_idx"),
        ),
        migrations.AddIndex(
            model_name="comprehensiveauditlog",
            index=models.Index(fields=["model_label", "object_pk"], name="trainees_co_model_l_41cc1f_idx"),
        ),
    ]
