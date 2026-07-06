from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('trainees', '0037_accessauditlog_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name='accessauditlog',
            old_name='changed_by',
            new_name='actor',
        ),
        migrations.AddField(
            model_name='accessauditlog',
            name='target_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='access_audit_logs',
                to=settings.AUTH_USER_MODEL,
                verbose_name='المستخدم المستهدف',
            ),
        ),
        migrations.AddField(
            model_name='accessauditlog',
            name='changed_fields',
            field=models.JSONField(blank=True, default=list, verbose_name='الحقول المتغيرة'),
        ),
        migrations.AddField(
            model_name='accessauditlog',
            name='notes',
            field=models.TextField(blank=True, default='', verbose_name='ملاحظات'),
        ),
        migrations.RemoveField(
            model_name='accessauditlog',
            name='reason',
        ),
        migrations.AlterField(
            model_name='accessauditlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('create', 'إنشاء ملف صلاحيات'),
                    ('update', 'تعديل الصلاحيات'),
                    ('delete', 'حذف ملف الصلاحيات'),
                    ('activate', 'تفعيل الصلاحيات'),
                    ('disable', 'تعطيل الصلاحيات'),
                    ('extend', 'تمديد الصلاحية'),
                    ('force_password_on', 'تفعيل إجبار تغيير كلمة المرور'),
                    ('force_password_off', 'إلغاء إجبار تغيير كلمة المرور'),
                ],
                default='update',
                max_length=40,
                verbose_name='نوع العملية',
            ),
        ),
        migrations.AlterField(
            model_name='accessauditlog',
            name='before_data',
            field=models.JSONField(blank=True, default=dict, verbose_name='القيم قبل التغيير'),
        ),
        migrations.AlterField(
            model_name='accessauditlog',
            name='after_data',
            field=models.JSONField(blank=True, default=dict, verbose_name='القيم بعد التغيير'),
        ),
        migrations.AlterField(
            model_name='accessauditlog',
            name='profile',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='audit_logs',
                to='trainees.useraccessprofile',
                verbose_name='ملف الصلاحيات',
            ),
        ),
        migrations.RunPython(noop, reverse_code=noop),
    ]
