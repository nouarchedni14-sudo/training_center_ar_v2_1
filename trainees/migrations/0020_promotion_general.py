from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0019_merge_20260218_1325"),
    ]

    operations = [
        migrations.CreateModel(
            name="دفعة",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("اسم_الدفعة", models.CharField(choices=[("فيفري", "فيفري"), ("سبتمبر", "سبتمبر")], max_length=20, verbose_name="اسم الدفعة")),
                ("رقم_الدورة", models.PositiveSmallIntegerField(choices=[(1, "1"), (2, "2")], verbose_name="رقم الدورة")),
                ("السنة", models.PositiveIntegerField(verbose_name="السنة")),
                ("تاريخ_الدخول_الرسمي", models.DateField(verbose_name="تاريخ الدخول الرسمي")),
                ("بداية_السداسي_1", models.DateField(verbose_name="بداية السداسي 1")),
                ("بداية_السداسي_2", models.DateField(verbose_name="بداية السداسي 2")),
                ("بداية_السداسي_3", models.DateField(verbose_name="بداية السداسي 3")),
                ("بداية_السداسي_4", models.DateField(verbose_name="بداية السداسي 4")),
                ("بداية_السداسي_5", models.DateField(blank=True, null=True, verbose_name="بداية السداسي 5")),
                ("مفعلة", models.BooleanField(default=True, verbose_name="مفعلة")),
            ],
            options={
                "verbose_name": "دفعة",
                "verbose_name_plural": "الدفعات",
                "ordering": ["-السنة", "-رقم_الدورة"],
            },
        ),
        migrations.AddConstraint(
            model_name="دفعة",
            constraint=models.UniqueConstraint(fields=("رقم_الدورة", "السنة"), name="trainees_unique_session_year_promotion"),
        ),
        migrations.AddField(
            model_name="حضوري_أولي",
            name="الدفعة",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="حضوري_أولي_trainees", to="trainees.دفعة", verbose_name="الدفعة"),
        ),
        migrations.AddField(
            model_name="تمهين",
            name="الدفعة",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="تمهين_trainees", to="trainees.دفعة", verbose_name="الدفعة"),
        ),
        migrations.AddField(
            model_name="مسائي_ومعابر",
            name="الدفعة",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="مسائي_ومعابر_trainees", to="trainees.دفعة", verbose_name="الدفعة"),
        ),
    ]
