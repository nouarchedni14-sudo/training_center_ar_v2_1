from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("trainees", "0006_add_unified_status"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(model_name="تمهين", name="الحالة_الموحدة"),
                migrations.RemoveField(model_name="حضوري_أولي", name="الحالة_الموحدة"),
                migrations.RemoveField(model_name="مسائي_ومعابر", name="الحالة_الموحدة"),
            ],
        ),
    ]
