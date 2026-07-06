from __future__ import annotations

from django.db import migrations


def _expected_cycle(official_start):
    if not official_start:
        return None, None
    session_no = 2 if official_start.month >= 9 else 1
    year_value = official_start.year
    return session_no, year_value


def forwards(apps, schema_editor):
    Promotion = apps.get_model('trainees', 'دفعة')
    trainee_models = [
        apps.get_model('trainees', 'حضوري_أولي'),
        apps.get_model('trainees', 'تمهين'),
        apps.get_model('trainees', 'مسائي_ومعابر'),
    ]

    promotions = list(Promotion.objects.all().order_by('تاريخ_الدخول_الرسمي', 'id'))
    canonical_by_key = {}
    merges = []

    for promo in promotions:
        session_no, year_value = _expected_cycle(getattr(promo, 'تاريخ_الدخول_الرسمي', None))
        if not session_no or not year_value:
            continue

        desired_name = 'فيفري' if session_no == 1 else 'سبتمبر'
        key = (session_no, year_value)
        canonical = canonical_by_key.get(key)

        if canonical is None:
            canonical_by_key[key] = promo
            changed = False
            if promo.رقم_الدورة != session_no:
                promo.رقم_الدورة = session_no
                changed = True
            if promo.السنة != year_value:
                promo.السنة = year_value
                changed = True
            if promo.اسم_الدفعة != desired_name:
                promo.اسم_الدفعة = desired_name
                changed = True
            if changed:
                promo.save(update_fields=['رقم_الدورة', 'السنة', 'اسم_الدفعة'])
        else:
            merges.append((promo.id, canonical.id))

    for source_id, target_id in merges:
        for Model in trainee_models:
            Model.objects.filter(الدفعة_id=source_id).update(الدفعة_id=target_id)

    if merges:
        Promotion.objects.filter(id__in=[source_id for source_id, _ in merges]).delete()

    try:
        from trainees.semester_utils import compute_semester_for_trainee, clear_promotion_cache
        clear_promotion_cache()
        promo_map = {p.id: p for p in Promotion.objects.all()}
        for Model in trainee_models:
            fields = ['id', 'الدفعة', 'تاريخ_بداية_التكوين', 'تاريخ_نهاية_التكوين', 'السداسي']
            if Model.__name__ == 'تمهين':
                fields.append('معيد')
            to_update = []
            for obj in Model.objects.all().only(*fields).iterator(chunk_size=1000):
                sem = compute_semester_for_trainee(
                    promo_map.get(getattr(obj, 'الدفعة_id', None)),
                    getattr(obj, 'تاريخ_بداية_التكوين', None),
                    getattr(obj, 'تاريخ_نهاية_التكوين', None),
                    is_repeater=bool(getattr(obj, 'معيد', False)),
                )
                if sem != getattr(obj, 'السداسي', None):
                    obj.السداسي = sem
                    to_update.append(obj)
            if to_update:
                Model.objects.bulk_update(to_update, ['السداسي'], batch_size=1000)
    except Exception:
        pass


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('trainees', '0023_recompute_semester_by_cycle_order'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
