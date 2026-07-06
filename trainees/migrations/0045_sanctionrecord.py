# Generated manually for العقوبات feature
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('trainees', '0044_dismissaldecision'),
    ]

    operations = [
        migrations.CreateModel(
            name='SanctionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('program', models.CharField(choices=[('initial', 'حضوري أولي'), ('apprentice', 'تمهين'), ('evening', 'مسائي ومعابر')], max_length=20, verbose_name='النمط')),
                ('sanction_scope', models.CharField(choices=[('current', 'الحاليين'), ('graduated', 'المتخرجين')], default='current', max_length=20, verbose_name='قسم العقوبة')),
                ('trainee_object_id', models.PositiveIntegerField(verbose_name='معرّف المتكوّن')),
                ('trainee_name', models.CharField(max_length=255, verbose_name='اسم المتكوّن وقت الإنشاء')),
                ('registration_number', models.CharField(blank=True, default='', max_length=80, verbose_name='رقم التسجيل')),
                ('specialty', models.CharField(blank=True, default='', max_length=200, verbose_name='التخصص')),
                ('group_code', models.CharField(blank=True, default='', max_length=120, verbose_name='رمز الفرع / الفوج')),
                ('semester', models.CharField(blank=True, default='', max_length=80, verbose_name='السداسي')),
                ('document_number', models.CharField(blank=True, default='', max_length=120, verbose_name='رقم العقوبة')),
                ('sanction_text', models.CharField(blank=True, default='', max_length=255, verbose_name='العقوبة')),
                ('disciplinary_record_number', models.CharField(blank=True, default='', max_length=120, verbose_name='رقم محضر اللجنة التأديبية')),
                ('disciplinary_record_date', models.DateField(blank=True, null=True, verbose_name='تاريخ محضر اللجنة التأديبية')),
                ('decision_date', models.DateField(blank=True, null=True, verbose_name='تاريخ تحرير العقوبة')),
                ('status', models.CharField(choices=[('draft', 'مسودة'), ('ready', 'جاهزة للطباعة'), ('issued', 'تم الإصدار'), ('delivered', 'تم التسليم للمتكون'), ('cancelled', 'ملغاة')], default='draft', max_length=20, verbose_name='حالة العقوبة')),
                ('notes', models.TextField(blank=True, default='', verbose_name='ملاحظات')),
                ('is_archived', models.BooleanField(default=False, verbose_name='مؤرشفة')),
                ('archived_at', models.DateTimeField(blank=True, null=True, verbose_name='تاريخ الأرشفة')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_sanction_records', to=settings.AUTH_USER_MODEL, verbose_name='أُنشئ بواسطة')),
                ('trainee_content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='نوع المتكوّن')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_sanction_records', to=settings.AUTH_USER_MODEL, verbose_name='آخر تعديل بواسطة')),
            ],
            options={
                'verbose_name': 'عقوبة',
                'verbose_name_plural': 'العقوبات',
                'ordering': ['program', 'sanction_scope', 'is_archived', 'specialty', 'trainee_name', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='sanctionrecord',
            index=models.Index(fields=['program', 'sanction_scope', 'status'], name='trainees_sa_program_d2701f_idx'),
        ),
        migrations.AddIndex(
            model_name='sanctionrecord',
            index=models.Index(fields=['program', 'sanction_scope', 'is_archived'], name='trainees_sa_program_6b6924_idx'),
        ),
        migrations.AddIndex(
            model_name='sanctionrecord',
            index=models.Index(fields=['program', 'specialty'], name='trainees_sa_program_eac76f_idx'),
        ),
        migrations.AddConstraint(
            model_name='sanctionrecord',
            constraint=models.UniqueConstraint(fields=('program', 'sanction_scope', 'trainee_content_type', 'trainee_object_id'), name='trainees_unique_sanction_record_per_trainee'),
        ),
    ]
