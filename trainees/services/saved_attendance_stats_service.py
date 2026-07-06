from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Max

from ..models import AttendanceStatSnapshot, دفعة


def _parse_optional_month(raw_month):
    raw_month = (raw_month or '').strip()
    if raw_month.isdigit():
        month_value = int(raw_month)
        if 1 <= month_value <= 12:
            return month_value
    return None


def _parse_optional_year(raw_year):
    raw_year = (raw_year or '').strip()
    if raw_year.isdigit():
        year_value = int(raw_year)
        if 2000 <= year_value <= 2100:
            return year_value
    return None


def _resolve_optional_batch(raw_batch_id):
    raw_batch_id = (raw_batch_id or '').strip()
    if raw_batch_id.isdigit():
        return دفعة.objects.filter(pk=int(raw_batch_id)).first()
    return None


def build_saved_attendance_stats_archive_context(
    request,
    *,
    attendance_saved_stats_program_options,
    attendance_programs,
    attendance_month_choices,
    unique_clean_values,
):
    program_options = attendance_saved_stats_program_options(request.user)
    if not program_options:
        raise PermissionDenied('غير مصرح لك بعرض إحصائيات الغياب المحفوظة.')

    allowed_program_codes = [item['code'] for item in program_options]
    selected_program = (request.GET.get('program') or '').strip()
    if selected_program and selected_program not in allowed_program_codes:
        raise PermissionDenied('غير مصرح لك بعرض هذا النمط.')

    selected_month = _parse_optional_month(request.GET.get('month'))
    selected_year = _parse_optional_year(request.GET.get('year'))
    selected_batch = _resolve_optional_batch(request.GET.get('batch_id'))
    selected_specialty = (request.GET.get('specialty') or '').strip()

    base_qs = AttendanceStatSnapshot.objects.all()
    if selected_program:
        base_qs = base_qs.filter(program=selected_program)
    else:
        base_qs = base_qs.filter(program__in=allowed_program_codes)
    if selected_month:
        base_qs = base_qs.filter(month=selected_month)
    if selected_year:
        base_qs = base_qs.filter(year=selected_year)

    scope_summaries = list(
        base_qs.values(
            'program',
            'year',
            'month',
            'batch_id',
            'batch__السنة',
            'batch__رقم_الدورة',
            'specialty',
        ).annotate(
            trainee_count=Count('id'),
            average_absence_rate=Avg('absence_rate'),
            latest_saved_at=Max('updated_at'),
        ).order_by('-year', '-month', 'program', 'batch__السنة', 'batch__رقم_الدورة', 'specialty')
    )

    for item in scope_summaries:
        item['program_label'] = attendance_programs.get(item['program'], {}).get('label', item['program'])
        item['specialty_display'] = item['specialty'] or 'كل التخصصات'
        if item.get('batch_id'):
            year_label = item.get('batch__السنة') or ''
            cycle_label = item.get('batch__رقم_الدورة') or ''
            item['batch_display'] = f'دفعة {year_label} / {cycle_label}'
        else:
            item['batch_display'] = 'كل الدفعات'
        item['average_absence_rate'] = round(item.get('average_absence_rate') or 0, 2)

    available_years = list(
        AttendanceStatSnapshot.objects.filter(program__in=allowed_program_codes)
        .values_list('year', flat=True)
        .distinct()
        .order_by('-year')
    )
    batch_options = list(
        base_qs.exclude(batch__isnull=True)
        .values('batch_id', 'batch__السنة', 'batch__رقم_الدورة')
        .distinct()
        .order_by('-batch__السنة', '-batch__رقم_الدورة')
    )
    specialty_options = sorted(
        unique_clean_values(
            base_qs.order_by()
            .exclude(specialty='')
            .values_list('specialty', flat=True)
        )
    )

    detail_qs = None
    detail_scope = None
    detail_rows = []
    detail_summary = {
        'trainee_count': 0,
        'average_absence_rate': 0,
        'latest_saved_at': None,
    }
    if selected_program and selected_month and selected_year:
        detail_qs = AttendanceStatSnapshot.objects.filter(
            program=selected_program,
            month=selected_month,
            year=selected_year,
        )
        if selected_batch is not None:
            detail_qs = detail_qs.filter(batch=selected_batch)
        if selected_specialty:
            detail_qs = detail_qs.filter(specialty=selected_specialty)

        detail_qs = detail_qs.order_by('-absence_rate', '-absent_count', 'trainee_specialty', 'trainee_name')
        if detail_qs.exists():
            detail_scope = {
                'program': selected_program,
                'program_label': attendance_programs[selected_program]['label'],
                'month': selected_month,
                'year': selected_year,
                'batch': selected_batch,
                'specialty': selected_specialty,
                'specialty_display': selected_specialty or 'كل التخصصات',
            }
            detail_rows = list(detail_qs)
            summary = detail_qs.aggregate(
                trainee_count=Count('id'),
                average_absence_rate=Avg('absence_rate'),
                latest_saved_at=Max('updated_at'),
            )
            detail_summary = {
                'trainee_count': summary.get('trainee_count') or 0,
                'average_absence_rate': round(summary.get('average_absence_rate') or 0, 2),
                'latest_saved_at': summary.get('latest_saved_at'),
            }

    return {
        'title': 'أرشيف إحصائيات الغيابات المحفوظة',
        'program_options': program_options,
        'selected_program': selected_program,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'selected_batch_id': selected_batch.pk if selected_batch else '',
        'selected_specialty': selected_specialty,
        'month_choices': [{'value': value, 'label': label} for value, label in attendance_month_choices],
        'year_choices': available_years,
        'scope_summaries': scope_summaries,
        'scope_count': len(scope_summaries),
        'batch_options': batch_options,
        'specialty_options': specialty_options,
        'detail_rows': detail_rows,
        'detail_scope': detail_scope,
        'detail_summary': detail_summary,
        'current_query': request.GET.urlencode(),
        'can_view_live_stats': bool(detail_scope),
    }
