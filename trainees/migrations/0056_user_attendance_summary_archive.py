# Generated manually for the user attendance summary archive feature.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('trainees', '0055_attendance_study_days_4_5'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserAttendanceSummaryArchive',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('program', models.CharField(choices=[('initial', 'حضوري أولي'), ('apprentice', 'تمهين'), ('evening', 'دروس مسائية'), ('crossing', 'معابر')], default='apprentice', max_length=20, verbose_name='النمط')),
                ('title', models.CharField(max_length=255, verbose_name='عنوان التقرير')),
                ('filters_json', models.JSONField(blank=True, default=dict, verbose_name='الفلاتر المستعملة')),
                ('rows_json', models.JSONField(blank=True, default=list, verbose_name='صفوف التقرير')),
                ('row_count', models.PositiveIntegerField(default=0, verbose_name='عدد المتكونين')),
                ('total_present', models.PositiveIntegerField(default=0, verbose_name='مجموع الحضور في الفترة')),
                ('total_absent', models.PositiveIntegerField(default=0, verbose_name='مجموع الغيابات في الفترة')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الأرشفة')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_attendance_summary_archives', to=settings.AUTH_USER_MODEL, verbose_name='أرشف بواسطة')),
            ],
            options={
                'verbose_name': 'أرشيف متابعة حضور وغيابات المستخدم',
                'verbose_name_plural': 'أرشيف متابعة الحضور والغيابات لدى المستخدم',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='userattendancesummaryarchive',
            index=models.Index(fields=['program', 'created_at'], name='trainees_us_program_54b03c_idx'),
        ),
    ]
