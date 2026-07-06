from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sync_core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="centraloffice",
            name="office_api_url",
            field=models.URLField(blank=True, help_text="مثال: http://192.168.1.20:8000", verbose_name="رابط خادم المكتب للسحب"),
        ),
        migrations.AddField(
            model_name="centraloffice",
            name="pull_enabled",
            field=models.BooleanField(default=True, verbose_name="السماح للمطور بسحب السجلات"),
        ),
        migrations.AddField(
            model_name="centraloffice",
            name="last_pull_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="آخر سحب من المطور"),
        ),
        migrations.AddField(
            model_name="centraloffice",
            name="last_pull_cursor",
            field=models.CharField(blank=True, default="0", max_length=200, verbose_name="آخر مؤشر سحب"),
        ),
        migrations.AddField(
            model_name="centraloffice",
            name="last_pull_error",
            field=models.TextField(blank=True, verbose_name="آخر خطأ في السحب"),
        ),
    ]
