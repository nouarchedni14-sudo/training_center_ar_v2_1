# Generated manually for مقرر الفصل feature
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('trainees', '0043_comprehensiveauditlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='DismissalDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('program', models.CharField(choices=[('initial', 'حضوري أولي'), ('apprentice', 'تمهين'), ('evening', 'مسائي ومعابر')], max_length=20, verbose_name='النمط')),
                ('decision_scope', models.CharField(choices=[('current', 'الحاليين'), ('graduated', 'المتخرجين')], default='current', max_length=20, verbose_name='قسم مقرر الفصل')),
                ('trainee_object_id', models.PositiveIntegerField(verbose_name='معرّف المتكوّن')),
                ('trainee_name', models.CharField(max_length=255, verbose_name='اسم المتكوّن وقت الإنشاء')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='تاريخ الميلاد')),
                ('birth_place', models.CharField(blank=True, default='', max_length=255, verbose_name='مكان الميلاد')),
                ('registration_number', models.CharField(blank=True, default='', max_length=80, verbose_name='رقم التسجيل')),
                ('specialty', models.CharField(blank=True, default='', max_length=200, verbose_name='التخصص')),
                ('training_start_date', models.DateField(blank=True, null=True, verbose_name='بداية التربص')),
                ('training_end_date', models.DateField(blank=True, null=True, verbose_name='نهاية التربص')),
                ('group_code', models.CharField(blank=True, default='', max_length=120, verbose_name='رمز الفرع / الفوج')),
                ('semester', models.CharField(blank=True, default='', max_length=80, verbose_name='السداسي')),
                ('removal_date', models.DateField(blank=True, null=True, verbose_name='تاريخ الشطب')),
                ('removal_number', models.CharField(blank=True, default='', max_length=120, verbose_name='رقم الشطب')),
                ('decision_number', models.CharField(blank=True, default='', max_length=120, verbose_name='رقم مقرر الفصل')),
                ('disciplinary_record_number', models.CharField(blank=True, default='', max_length=120, verbose_name='رقم محضر اللجنة التأديبية')),
                ('disciplinary_record_date', models.DateField(blank=True, null=True, verbose_name='تاريخ محضر اللجنة التأديبية')),
                ('dismissal_start_date', models.DateField(blank=True, null=True, verbose_name='تاريخ بداية الفصل')),
                ('decision_date', models.DateField(blank=True, null=True, verbose_name='تاريخ تحرير المقرر')),
                ('status', models.CharField(choices=[('draft', 'مسودة'), ('ready', 'جاهز للطباعة'), ('issued', 'تم الإصدار'), ('cancelled', 'ملغى')], default='draft', max_length=20, verbose_name='حالة المقرر')),
                ('notes', models.TextField(blank=True, default='', verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_dismissal_decisions', to=settings.AUTH_USER_MODEL, verbose_name='أُنشئ بواسطة')),
                ('trainee_content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='نوع المتكوّن')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_dismissal_decisions', to=settings.AUTH_USER_MODEL, verbose_name='آخر تعديل بواسطة')),
            ],
            options={
                'verbose_name': 'مقرر فصل',
                'verbose_name_plural': 'مقررات الفصل',
                'ordering': ['program', 'decision_scope', 'specialty', 'trainee_name', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='dismissaldecision',
            index=models.Index(fields=['program', 'decision_scope', 'status'], name='trainees_di_program_1c2215_idx'),
        ),
        migrations.AddIndex(
            model_name='dismissaldecision',
            index=models.Index(fields=['program', 'specialty'], name='trainees_di_program_4437d0_idx'),
        ),
        migrations.AddConstraint(
            model_name='dismissaldecision',
            constraint=models.UniqueConstraint(fields=('program', 'decision_scope', 'trainee_content_type', 'trainee_object_id'), name='trainees_unique_dismissal_decision_per_trainee'),
        ),
    ]
