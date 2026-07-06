# Generated manually for independent-device approval flow
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('sync_core', '0002_centraloffice_pull_audit'),
    ]

    operations = [
        migrations.CreateModel(
            name='CentralDeviceRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('server_id', models.CharField(max_length=100, unique=True, verbose_name='معرف الجهاز')),
                ('request_secret', models.CharField(max_length=255, verbose_name='سر طلب الربط')),
                ('device_token', models.CharField(blank=True, max_length=255, verbose_name='رمز الجهاز بعد الاعتماد')),
                ('hostname', models.CharField(blank=True, max_length=180, verbose_name='اسم الجهاز')),
                ('device_label', models.CharField(blank=True, max_length=180, verbose_name='تسمية الجهاز')),
                ('lan_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP الجهاز')),
                ('app_version', models.CharField(blank=True, max_length=50, verbose_name='نسخة البرنامج')),
                ('central_url', models.URLField(blank=True, verbose_name='رابط المركز كما يراه الجهاز')),
                ('status', models.CharField(choices=[('pending', 'بانتظار موافقة المطوّر'), ('approved', 'معتمد'), ('rejected', 'مرفوض')], default='pending', max_length=20, verbose_name='الحالة')),
                ('requested_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='وقت أول طلب')),
                ('last_seen_at', models.DateTimeField(blank=True, null=True, verbose_name='آخر اتصال قبل الاعتماد')),
                ('approved_at', models.DateTimeField(blank=True, null=True, verbose_name='وقت الاعتماد')),
                ('config_delivered_at', models.DateTimeField(blank=True, null=True, verbose_name='وقت تسليم الإعدادات للجهاز')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('assigned_office', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_registrations', to='sync_core.centraloffice', verbose_name='المكتب المعتمد')),
            ],
            options={
                'verbose_name': 'جهاز ينتظر الربط',
                'verbose_name_plural': 'الأجهزة بانتظار الربط',
                'ordering': ['-requested_at'],
            },
        ),
    ]
