# Generated manually for the summons feature
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('trainees', '0046_attendance_slots'),
    ]

    operations = [
        migrations.CreateModel(
            name='SummonsRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('program', models.CharField(choices=[('initial', 'حضوري أولي'), ('apprentice', 'تمهين'), ('evening', 'مسائي ومعابر')], max_length=20, verbose_name='النمط')),
                ('summons_scope', models.CharField(choices=[('current', 'الحاليين'), ('graduated', 'المتخرجين')], default='current', max_length=20, verbose_name='قسم الاستدعاء')),
                ('summons_type', models.CharField(choices=[('graduate_title', 'عدم استلام عنوان مذكرة التخرج'), ('contract_termination', 'فسخ العقد من المستخدم'), ('employer_absence', 'غيابات المستخدم'), ('intermittent_absence', 'الغيابات المتذبذبة'), ('specific_session_absence', 'عدم حضور حصة معينة'), ('disciplinary_council', 'المجلس التأديبي'), ('supervisor_absence', 'استدعاء المؤطر')], default='graduate_title', max_length=40, verbose_name='نوع الاستدعاء')),
                ('trainee_object_id', models.PositiveIntegerField(verbose_name='معرّف المتكوّن')),
                ('trainee_name', models.CharField(max_length=255, verbose_name='اسم المتكوّن وقت الإنشاء')),
                ('registration_number', models.CharField(blank=True, default='', max_length=80, verbose_name='رقم التسجيل')),
                ('address', models.CharField(blank=True, default='', max_length=255, verbose_name='العنوان')),
                ('specialty', models.CharField(blank=True, default='', max_length=200, verbose_name='التخصص')),
                ('group_code', models.CharField(blank=True, default='', max_length=120, verbose_name='رمز الفرع / الفوج')),
                ('semester', models.CharField(blank=True, default='', max_length=80, verbose_name='السداسي')),
                ('document_number', models.CharField(blank=True, default='', max_length=120, verbose_name='رقم الاستدعاء')),
                ('issue_date', models.DateField(blank=True, null=True, verbose_name='تاريخ تحرير الاستدعاء')),
                ('from_date', models.DateField(blank=True, null=True, verbose_name='منذ تاريخ')),
                ('contract_termination_date', models.DateField(blank=True, null=True, verbose_name='تاريخ فسخ العقد')),
                ('council_date', models.DateField(blank=True, null=True, verbose_name='يوم المجلس')),
                ('council_time', models.CharField(blank=True, default='', max_length=80, verbose_name='ساعة المجلس')),
                ('lesson_name', models.CharField(blank=True, default='', max_length=160, verbose_name='الحصة')),
                ('notes', models.TextField(blank=True, default='', verbose_name='ملاحظات')),
                ('status', models.CharField(choices=[('draft', 'مسودة'), ('ready', 'جاهز للطباعة'), ('issued', 'تم الإصدار'), ('delivered', 'تم التسليم للمتكون'), ('cancelled', 'ملغى')], default='draft', max_length=20, verbose_name='حالة الاستدعاء')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_summons_records', to=settings.AUTH_USER_MODEL, verbose_name='أُنشئ بواسطة')),
                ('trainee_content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='نوع المتكوّن')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_summons_records', to=settings.AUTH_USER_MODEL, verbose_name='آخر تعديل بواسطة')),
            ],
            options={
                'verbose_name': 'استدعاء',
                'verbose_name_plural': 'الاستدعاءات',
                'ordering': ['program', 'summons_scope', 'summons_type', 'specialty', 'trainee_name', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='summonsrecord',
            index=models.Index(fields=['program', 'summons_scope', 'summons_type'], name='trainees_su_program_4c1894_idx'),
        ),
        migrations.AddIndex(
            model_name='summonsrecord',
            index=models.Index(fields=['program', 'status'], name='trainees_su_program_08e17c_idx'),
        ),
        migrations.AddIndex(
            model_name='summonsrecord',
            index=models.Index(fields=['program', 'specialty'], name='trainees_su_program_c3c31b_idx'),
        ),
        migrations.AddConstraint(
            model_name='summonsrecord',
            constraint=models.UniqueConstraint(fields=('program', 'summons_scope', 'summons_type', 'trainee_content_type', 'trainee_object_id'), name='trainees_unique_summons_per_type_trainee'),
        ),
    ]
