from django.db import migrations


def compact_registration_numbers(apps, schema_editor):
    from trainees.models import format_registration_number

    for model_name in ("حضوري_أولي", "تمهين", "مسائي_ومعابر"):
        Model = apps.get_model("trainees", model_name)
        updates = []
        for obj in Model.objects.exclude(رقم_التسجيل__isnull=True).exclude(رقم_التسجيل=""):
            normalized = format_registration_number(obj.رقم_التسجيل)
            if normalized and normalized != obj.رقم_التسجيل:
                obj.رقم_التسجيل = normalized
                updates.append(obj)
        if updates:
            Model.objects.bulk_update(updates, ["رقم_التسجيل"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("trainees", "0025_normalize_registration_numbers"),
    ]

    operations = [
        migrations.RunPython(compact_registration_numbers, migrations.RunPython.noop),
    ]
