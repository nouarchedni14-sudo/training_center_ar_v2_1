from django.db import migrations, models  # استيراد عناصر محددة من مكتبة/وحدة


class Migration(migrations.Migration):  # تعريف كلاس (Class)

    dependencies = [  # تعيين قيمة لمتغير/إعداد
        ("trainees", "0010_custom_fields"),  # سطر كود لتنفيذ منطق/إعداد
    ]  # سطر كود لتنفيذ منطق/إعداد

    operations = [  # تعيين قيمة لمتغير/إعداد
        migrations.AlterField(  # سطر كود لتنفيذ منطق/إعداد
            model_name="customfield",  # تعيين قيمة لمتغير/إعداد
            name="key",  # تعيين قيمة لمتغير/إعداد
            field=models.SlugField(blank=True, editable=False, help_text="يُنشأ تلقائيًا (cf_1, cf_2, ...).", max_length=80, unique=True, verbose_name="المفتاح (فريد)"),  # تعريف حقل/علاقة في نموذج Django
        ),  # سطر كود لتنفيذ منطق/إعداد
    ]  # سطر كود لتنفيذ منطق/إعداد
