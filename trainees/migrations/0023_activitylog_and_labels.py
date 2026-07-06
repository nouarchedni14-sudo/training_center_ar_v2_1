from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    """Legacy duplicate branch kept as a no-op for compatibility.

    The final schema for ActivityLog/UserAccessProfile comes from
    0023_alter_#U062f#U0641#U0639#U0629_options_activitylog_useraccessprofile.py. Keeping this
    branch as a no-op allows old migration graphs to merge cleanly without
    trying to recreate tables that already exist.
    """

    dependencies = [
        ('trainees', '0022_recompute_semester_from_promotion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
