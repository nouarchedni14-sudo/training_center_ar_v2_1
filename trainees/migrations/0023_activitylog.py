from django.db import migrations


class Migration(migrations.Migration):
    """Legacy duplicate branch kept as a no-op for compatibility.

    The ActivityLog model is created by
    0023_alter_#U062f#U0641#U0639#U0629_options_activitylog_useraccessprofile.py. This branch used
    to create the same table with a different shape, which breaks `migrate`
    on existing databases because the table already exists.
    """

    dependencies = [
        ('trainees', '0022_recompute_semester_from_promotion'),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
