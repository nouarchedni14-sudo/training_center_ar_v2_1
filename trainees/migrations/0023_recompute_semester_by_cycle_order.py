from __future__ import annotations

from django.db import migrations


def forwards(apps, schema_editor):
    from trainees.semester_utils import compute_semester_for_trainee, clear_promotion_cache

    Promotion = apps.get_model('trainees', 'دفعة')
    promo_map = {p.id: p for p in Promotion.objects.all()}
    clear_promotion_cache()

    for model_name in ('حضوري_أولي', 'تمهين', 'مسائي_ومعابر'):
        Model = apps.get_model('trainees', model_name)
        fields = ['id', 'الدفعة', 'تاريخ_بداية_التكوين', 'تاريخ_نهاية_التكوين', 'السداسي']
        if model_name == 'تمهين':
            fields.append('معيد')
        to_update = []
        for obj in Model.objects.all().only(*fields).iterator(chunk_size=1000):
            promotion = promo_map.get(getattr(obj, 'الدفعة_id', None))
            sem = compute_semester_for_trainee(
                promotion,
                getattr(obj, 'تاريخ_بداية_التكوين', None),
                getattr(obj, 'تاريخ_نهاية_التكوين', None),
                is_repeater=bool(getattr(obj, 'معيد', False)),
            )
            if sem != getattr(obj, 'السداسي', None):
                obj.السداسي = sem
                to_update.append(obj)
        if to_update:
            Model.objects.bulk_update(to_update, ['السداسي'], batch_size=1000)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('trainees', '0022_recompute_semester_from_promotion'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
