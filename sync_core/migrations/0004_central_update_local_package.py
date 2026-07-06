# Generated manually for central update package upload support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sync_core", "0003_central_device_registration"),
    ]

    operations = [
        migrations.AddField(
            model_name="centralupdaterelease",
            name="local_package_name",
            field=models.CharField(blank=True, max_length=255, verbose_name="ملف التحديث المرفوع"),
        ),
    ]
