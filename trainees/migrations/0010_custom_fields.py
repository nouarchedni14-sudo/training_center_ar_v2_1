from django.db import migrations, models  # استيراد عناصر محددة من مكتبة/وحدة
import django.db.models.deletion  # استيراد مكتبة/وحدة بايثون

class Migration(migrations.Migration):  # تعريف كلاس (Class)

    dependencies = [  # تعيين قيمة لمتغير/إعداد
        ("contenttypes", "0002_remove_content_type_name"),  # سطر كود لتنفيذ منطق/إعداد
        ("trainees", "0009_recompute_semester_overwrite"),  # سطر كود لتنفيذ منطق/إعداد
    ]  # سطر كود لتنفيذ منطق/إعداد

    operations = [  # تعيين قيمة لمتغير/إعداد
        migrations.CreateModel(  # سطر كود لتنفيذ منطق/إعداد
            name="CustomField",  # تعيين قيمة لمتغير/إعداد
            fields=[  # تعيين قيمة لمتغير/إعداد
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),  # تعريف حقل/علاقة في نموذج Django
                ("key", models.SlugField(help_text="اسم داخلي فريد (بدون مسافات). مثال: رقم_ملف", max_length=80, unique=True, verbose_name="المفتاح (فريد)")),  # تعريف حقل/علاقة في نموذج Django
                ("label", models.CharField(max_length=120, verbose_name="اسم العمود")),  # تعريف حقل/علاقة في نموذج Django
                ("field_type", models.CharField(choices=[("text", "نص"), ("number", "رقم"), ("date", "تاريخ"), ("bool", "نعم/لا"), ("choice", "قائمة خيارات")], default="text", max_length=20, verbose_name="نوع الحقل")),  # تعريف حقل/علاقة في نموذج Django
                ("required", models.BooleanField(default=False, verbose_name="إجباري")),  # تعريف حقل/علاقة في نموذج Django
                ("choices", models.TextField(blank=True, default="", help_text="يستخدم فقط لنوع (قائمة خيارات). اكتب خيار في كل سطر.", verbose_name="الخيارات (سطر لكل خيار)")),  # تعريف حقل/علاقة في نموذج Django
                ("active", models.BooleanField(default=True, verbose_name="مفعل")),  # تعريف حقل/علاقة في نموذج Django
                ("order", models.PositiveIntegerField(default=100, verbose_name="الترتيب")),  # تعريف حقل/علاقة في نموذج Django
            ],  # سطر كود لتنفيذ منطق/إعداد
            options={"ordering": ["order", "id"],},  # تعيين قيمة لمتغير/إعداد
        ),  # سطر كود لتنفيذ منطق/إعداد
        migrations.CreateModel(  # سطر كود لتنفيذ منطق/إعداد
            name="CustomFieldValue",  # تعيين قيمة لمتغير/إعداد
            fields=[  # تعيين قيمة لمتغير/إعداد
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),  # تعريف حقل/علاقة في نموذج Django
                ("object_id", models.PositiveIntegerField()),  # تعريف حقل/علاقة في نموذج Django
                ("value_text", models.TextField(blank=True, default="")),  # تعريف حقل/علاقة في نموذج Django
                ("created_at", models.DateTimeField(auto_now_add=True)),  # تعريف حقل/علاقة في نموذج Django
                ("updated_at", models.DateTimeField(auto_now=True)),  # تعريف حقل/علاقة في نموذج Django
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),  # تعريف حقل/علاقة في نموذج Django
                ("field", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="trainees.customfield")),  # تعريف حقل/علاقة في نموذج Django
            ],  # سطر كود لتنفيذ منطق/إعداد
            options={  # تعيين قيمة لمتغير/إعداد
                "unique_together": {("field", "content_type", "object_id")},  # سطر كود لتنفيذ منطق/إعداد
            },  # سطر كود لتنفيذ منطق/إعداد
        ),  # سطر كود لتنفيذ منطق/إعداد
        migrations.AddIndex(  # سطر كود لتنفيذ منطق/إعداد
            model_name="customfieldvalue",  # تعيين قيمة لمتغير/إعداد
            index=models.Index(fields=["content_type", "object_id"], name="trainees_cus_content_7a6c1e_idx"),  # تعريف حقل/علاقة في نموذج Django
        ),  # سطر كود لتنفيذ منطق/إعداد
        migrations.AddIndex(  # سطر كود لتنفيذ منطق/إعداد
            model_name="customfieldvalue",  # تعيين قيمة لمتغير/إعداد
            index=models.Index(fields=["field"], name="trainees_cus_field_2e9a6e_idx"),  # تعريف حقل/علاقة في نموذج Django
        ),  # سطر كود لتنفيذ منطق/إعداد
    ]  # سطر كود لتنفيذ منطق/إعداد
