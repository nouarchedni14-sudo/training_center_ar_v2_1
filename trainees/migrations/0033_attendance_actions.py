from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('trainees', '0032_alter_كشفغياب_يوم_الدراسة_1_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('program', models.CharField(choices=[('initial', 'حضوري أولي'), ('apprentice', 'تمهين'), ('evening', 'مسائي ومعابر')], max_length=20, verbose_name='النمط')),
                ('month', models.PositiveSmallIntegerField(verbose_name='الشهر')),
                ('year', models.PositiveIntegerField(verbose_name='السنة')),
                ('specialty', models.CharField(blank=True, default='', max_length=200, verbose_name='التخصص وقت الإنشاء')),
                ('trainee_object_id', models.PositiveIntegerField(verbose_name='معرّف المتكوّن')),
                ('trainee_name', models.CharField(max_length=255, verbose_name='اللقب والاسم')),
                ('trainee_specialty', models.CharField(blank=True, default='', max_length=200, verbose_name='التخصص')),
                ('trainee_address', models.CharField(blank=True, default='', max_length=255, verbose_name='العنوان')),
                ('action_type', models.CharField(choices=[('excuse_1', 'الإعذار الأول'), ('excuse_2', 'الإعذار الثاني'), ('excuse_3', 'الإعذار الثالث'), ('summon', 'الاستدعاء')], max_length=20, verbose_name='نوع الإجراء')),
                ('trigger_count', models.PositiveIntegerField(default=0, verbose_name='عدد الغيابات المحتسبة')),
                ('threshold_value', models.PositiveIntegerField(default=5, verbose_name='العتبة المعتمدة')),
                ('document_number', models.CharField(blank=True, default='', max_length=120, verbose_name='رقم الوثيقة')),
                ('absence_start_date', models.DateField(blank=True, null=True, verbose_name='تاريخ بداية الغياب')),
                ('send_date', models.DateField(blank=True, null=True, verbose_name='تاريخ الإرسال / التحرير')),
                ('status', models.CharField(choices=[('pending', 'بانتظار الإكمال'), ('ready', 'جاهز للطباعة'), ('issued', 'تم الإصدار'), ('delivered', 'تم التسليم'), ('cancelled', 'ملغى')], default='pending', max_length=20, verbose_name='الحالة')),
                ('notes', models.TextField(blank=True, default='', verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_actions', to='trainees.دفعة', verbose_name='الدفعة')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_attendance_actions', to=settings.AUTH_USER_MODEL, verbose_name='أُنشئ بواسطة')),
                ('trainee_content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='نوع المتكوّن')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_attendance_actions', to=settings.AUTH_USER_MODEL, verbose_name='آخر تعديل بواسطة')),
            ],
            options={
                'verbose_name': 'إجراء غياب',
                'verbose_name_plural': 'إجراءات الغياب',
                'ordering': ['-year', '-month', 'program', '-created_at', 'trainee_name'],
            },
        ),
        migrations.AddIndex(
            model_name='attendanceaction',
            index=models.Index(fields=['program', 'year', 'month', 'action_type'], name='trainees_at_program_3cc08f_idx'),
        ),
        migrations.AddIndex(
            model_name='attendanceaction',
            index=models.Index(fields=['program', 'status'], name='trainees_at_program_69e2b1_idx'),
        ),
        migrations.AddConstraint(
            model_name='attendanceaction',
            constraint=models.UniqueConstraint(fields=('program', 'year', 'month', 'batch', 'specialty', 'trainee_content_type', 'trainee_object_id', 'action_type'), name='trainees_unique_attendance_action_per_scope'),
        ),
    ]
