# Generated manually for access scheduling enhancements.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trainees', '0036_useraccessprofile_activation_window'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('create', 'إنشاء'), ('update', 'تحديث'), ('suspend', 'تعليق مؤقت'), ('reactivate', 'إعادة تفعيل'), ('auto_sync', 'مزامنة تلقائية')], default='update', max_length=20, verbose_name='نوع العملية')),
                ('reason', models.CharField(blank=True, default='', max_length=255, verbose_name='السبب')),
                ('before_data', models.TextField(blank=True, default='', verbose_name='قبل التعديل')),
                ('after_data', models.TextField(blank=True, default='', verbose_name='بعد التعديل')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ العملية')),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_audit_entries', to=settings.AUTH_USER_MODEL, verbose_name='تم التعديل بواسطة')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='trainees.useraccessprofile', verbose_name='ملف الصلاحيات')),
            ],
            options={
                'verbose_name': 'سجل تغييرات الصلاحيات',
                'verbose_name_plural': 'سجل تغييرات الصلاحيات',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='access_end_time',
            field=models.TimeField(blank=True, help_text='إذا تركته فارغًا فلن يتم تقييد نهاية الوقت داخل اليوم.', null=True, verbose_name='نهاية وقت الدخول اليومي'),
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='access_start_time',
            field=models.TimeField(blank=True, help_text='إذا تركته فارغًا فلن يتم تقييد بداية الوقت داخل اليوم.', null=True, verbose_name='بداية وقت الدخول اليومي'),
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='access_type',
            field=models.CharField(choices=[('permanent', 'دائم'), ('temporary', 'مؤقت'), ('trainee', 'متربص'), ('shift', 'مناوب'), ('visitor', 'زائر')], default='permanent', help_text='هذا الحقل يوضح هل المستخدم دائم أو مؤقت أو متربص أو مناوب أو زائر.', max_length=20, verbose_name='نوع الصلاحية'),
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='activated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_profiles_activated', to=settings.AUTH_USER_MODEL, verbose_name='فعّل بواسطة'),
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='allowed_weekdays',
            field=models.CharField(blank=True, default='', help_text='اكتب أرقام الأيام المسموحة مفصولة بفواصل. مثال: 0,1,2,3,6', max_length=20, verbose_name='الأيام المسموحة'),
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='deactivated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_profiles_deactivated', to=settings.AUTH_USER_MODEL, verbose_name='عطّل بواسطة'),
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='grace_period_days',
            field=models.PositiveSmallIntegerField(default=0, help_text='عدد الأيام الإضافية المسموح بها بعد تاريخ نهاية الصلاحية قبل المنع الكامل.', verbose_name='أيام السماح بعد الانتهاء'),
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='suspended_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='تاريخ التعليق'),
        ),
        migrations.AddField(
            model_name='useraccessprofile',
            name='suspended_reason',
            field=models.CharField(blank=True, default='', help_text='يمكن للمدير كتابة سبب التعليق المؤقت حتى يبقى موثقًا داخل النظام.', max_length=255, verbose_name='سبب التعليق المؤقت'),
        ),
    ]
