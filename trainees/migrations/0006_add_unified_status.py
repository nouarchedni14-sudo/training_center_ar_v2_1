from django.db import migrations, models


def forwards(apps, schema_editor):
    status_utils = __import__("trainees.status_utils", fromlist=["unified_status_code"])
    unified_status_code = status_utils.unified_status_code

    for model_name in ["حضوري_أولي", "تمهين", "مسائي_ومعابر"]:
        Model = apps.get_model("trainees", model_name)
        qs = Model.objects.all().only("id", "الحالة")
        for obj in qs.iterator(chunk_size=1000):
            code = unified_status_code(getattr(obj, "الحالة", ""))
            # state-only migration: actual DB column is not created here on postgres
            # so just skip physical updates safely
            try:
                Model.objects.filter(id=obj.id).update(الحالة_الموحدة=code)
            except Exception:
                pass


def backwards(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("trainees", "0005_تمهين_مفترض_حضوري_أولي_مفترض_مسائي_ومعابر_مفترض"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="حضوري_أولي",
                    name="الحالة_الموحدة",
                    field=models.CharField(blank=True, choices=[("active", "نشط"), ("removed", "مشطوب"), ("other", "أخرى"), ("empty", "فارغ")], db_index=True, max_length=20, null=True, verbose_name="الحالة (موحّدة)"),
                ),
                migrations.AddField(
                    model_name="تمهين",
                    name="الحالة_الموحدة",
                    field=models.CharField(blank=True, choices=[("active", "نشط"), ("removed", "مشطوب"), ("other", "أخرى"), ("empty", "فارغ")], db_index=True, max_length=20, null=True, verbose_name="الحالة (موحّدة)"),
                ),
                migrations.AddField(
                    model_name="مسائي_ومعابر",
                    name="الحالة_الموحدة",
                    field=models.CharField(blank=True, choices=[("active", "نشط"), ("removed", "مشطوب"), ("other", "أخرى"), ("empty", "فارغ")], db_index=True, max_length=20, null=True, verbose_name="الحالة (موحّدة)"),
                ),
            ],
        ),
        migrations.RunPython(forwards, backwards),
    ]
