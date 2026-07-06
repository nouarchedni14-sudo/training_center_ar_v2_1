from django.db import migrations, models


def sync_promotion_schedule(apps, schema_editor):
    Promotion = apps.get_model("trainees", "دفعة")
    promotions = list(Promotion.objects.order_by("تاريخ_الدخول_الرسمي", "السنة", "رقم_الدورة", "id"))
    for idx, promo in enumerate(promotions):
        future = promotions[idx:idx + 5]
        promo.اسم_الدفعة = "فيفري" if promo.رقم_الدورة == 1 else "سبتمبر"
        promo.بداية_السداسي_1 = promo.تاريخ_الدخول_الرسمي
        promo.بداية_السداسي_2 = future[1].تاريخ_الدخول_الرسمي if len(future) > 1 else None
        promo.بداية_السداسي_3 = future[2].تاريخ_الدخول_الرسمي if len(future) > 2 else None
        promo.بداية_السداسي_4 = future[3].تاريخ_الدخول_الرسمي if len(future) > 3 else None
        promo.بداية_السداسي_5 = future[4].تاريخ_الدخول_الرسمي if len(future) > 4 else None
        promo.save(update_fields=["اسم_الدفعة", "بداية_السداسي_1", "بداية_السداسي_2", "بداية_السداسي_3", "بداية_السداسي_4", "بداية_السداسي_5"])


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0020_promotion_general"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="دفعة",
            options={"ordering": ["تاريخ_الدخول_الرسمي", "السنة", "رقم_الدورة"], "verbose_name": "دفعة", "verbose_name_plural": "الدفعات"},
        ),
        migrations.AlterField(
            model_name="دفعة",
            name="بداية_السداسي_2",
            field=models.DateField(blank=True, null=True, verbose_name="بداية السداسي 2"),
        ),
        migrations.AlterField(
            model_name="دفعة",
            name="بداية_السداسي_3",
            field=models.DateField(blank=True, null=True, verbose_name="بداية السداسي 3"),
        ),
        migrations.AlterField(
            model_name="دفعة",
            name="بداية_السداسي_4",
            field=models.DateField(blank=True, null=True, verbose_name="بداية السداسي 4"),
        ),
        migrations.RunPython(sync_promotion_schedule, migrations.RunPython.noop),
    ]
