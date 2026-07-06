from collections import Counter  # استيراد عناصر محددة من مكتبة/وحدة
import calendar  # استيراد مكتبة/وحدة بايثون
import json  # استيراد مكتبة/وحدة بايثون
from decimal import Decimal, ROUND_HALF_UP  # استيراد عناصر محددة من مكتبة/وحدة
from django.utils import timezone  # استيراد عناصر محددة من مكتبة/وحدة
from django.utils.safestring import mark_safe  # استيراد عناصر محددة من مكتبة/وحدة
from django.db.models import Q  # استيراد عناصر محددة من مكتبة/وحدة

from django import template  # استيراد عناصر محددة من مكتبة/وحدة

from trainees.models import حضوري_أولي, تمهين, مسائي_ومعابر  # استيراد عناصر محددة من مكتبة/وحدة
from trainees.admin_filters import status_group, q_active, q_removed  # استيراد عناصر محددة من مكتبة/وحدة
from trainees.status_utils import unified_status_code  # استيراد عناصر محددة من مكتبة/وحدة

register = template.Library()  # تعيين قيمة لمتغير/إعداد

MODELS = [  # تعيين قيمة لمتغير/إعداد
    ("حضوري أولي", حضوري_أولي),  # سطر كود لتنفيذ منطق/إعداد
    ("التمهين", تمهين),  # سطر كود لتنفيذ منطق/إعداد
    ("الدروس المسائية والمعابر", مسائي_ومعابر),  # سطر كود لتنفيذ منطق/إعداد
]  # سطر كود لتنفيذ منطق/إعداد


def _counter_for_field(field_name: str) -> Counter:  # تعريف دالة (Function)
    # تعريف حقل/علاقة في نموذج Django
    """Aggregate counts for a text field across all trainee models."""
    c = Counter()  # تعيين قيمة لمتغير/إعداد
    for _, m in MODELS:  # حلقة تكرار (For)
        # values_list can return None/''
        for v in m.objects.values_list(field_name, flat=True):  # حلقة تكرار (For)
            if not v:  # شرط (If)
                continue  # سطر كود لتنفيذ منطق/إعداد
            v = str(v).strip()  # تعيين قيمة لمتغير/إعداد
            if not v:  # شرط (If)
                continue  # سطر كود لتنفيذ منطق/إعداد
            c[status_group(v) if field_name == "الحالة" else v] += 1  # تعيين قيمة لمتغير/إعداد
    return c  # إرجاع قيمة من الدالة


def _top_items(c: Counter, limit: int = 12):  # تعريف دالة (Function)
    return [{"name": k, "count": v} for k, v in c.most_common(limit)]  # إرجاع قيمة من الدالة


def _to_chart_series(items):  # تعريف دالة (Function)
    # سطر كود لتنفيذ منطق/إعداد
    """Convert a list of {name,count} into (labels, counts) for Chart.js."""
    return [i["name"] for i in items], [i["count"] for i in items]  # إرجاع قيمة من الدالة


def _subtract_one_month(d):  # تعريف دالة (Function)
    month = d.month - 1  # تعيين قيمة لمتغير/إعداد
    year = d.year  # تعيين قيمة لمتغير/إعداد
    if month == 0:  # شرط (If)
        month = 12  # تعيين قيمة لمتغير/إعداد
        year -= 1  # تعيين قيمة لمتغير/إعداد
    day = min(d.day, calendar.monthrange(year, month)[1])  # تعيين قيمة لمتغير/إعداد
    return d.replace(year=year, month=month, day=day)  # إرجاع قيمة من الدالة


def _is_counted_removed(status_value, removal_date):  # تعريف دالة (Function)
    """Count as removed only after one full month has passed since removal date.
    If removal date is missing, keep counting it as removed immediately.  # سطر كود لتنفيذ منطق/إعداد
    """
    if unified_status_code(status_value) != "removed":  # شرط (If)
        return False  # إرجاع قيمة من الدالة
    if not removal_date:  # شرط (If)
        return True  # إرجاع قيمة من الدالة
    cutoff = _subtract_one_month(timezone.localdate())  # تعيين قيمة لمتغير/إعداد
    return removal_date <= cutoff  # إرجاع قيمة من الدالة


def _summarize_rows(rows):  # تعريف دالة (Function)
    total = 0  # تعيين قيمة لمتغير/إعداد
    active = 0  # تعيين قيمة لمتغير/إعداد
    active_m = 0  # تعيين قيمة لمتغير/إعداد
    active_f = 0  # تعيين قيمة لمتغير/إعداد
    removed = 0  # تعيين قيمة لمتغير/إعداد
    removed_m = 0  # تعيين قيمة لمتغير/إعداد
    removed_f = 0  # تعيين قيمة لمتغير/إعداد
    recent_removed = 0  # تعيين قيمة لمتغير/إعداد

    for row in rows:  # حلقة تكرار (For)
        total += 1  # تعيين قيمة لمتغير/إعداد
        g = _gender_code(row.get("الجنس"))  # تعيين قيمة لمتغير/إعداد
        raw_removed = (unified_status_code(row.get("الحالة")) == "removed")  # تعيين قيمة لمتغير/إعداد
        counted_removed = _is_counted_removed(row.get("الحالة"), row.get("تاريخ_الشطب"))  # تعيين قيمة لمتغير/إعداد
        if counted_removed:  # شرط (If)
            removed += 1  # تعيين قيمة لمتغير/إعداد
            if g == "m":  # شرط (If)
                removed_m += 1  # تعيين قيمة لمتغير/إعداد
            elif g == "f":  # شرط بديل (Elif)
                removed_f += 1  # تعيين قيمة لمتغير/إعداد
        else:  # فرع بديل (Else)
            active += 1  # تعيين قيمة لمتغير/إعداد
            if raw_removed and row.get("تاريخ_الشطب"):  # شرط (If)
                recent_removed += 1  # تعيين قيمة لمتغير/إعداد
            if g == "m":  # شرط (If)
                active_m += 1  # تعيين قيمة لمتغير/إعداد
            elif g == "f":  # شرط بديل (Elif)
                active_f += 1  # تعيين قيمة لمتغير/إعداد

    return {  # إرجاع قيمة من الدالة
        "total": total,  # سطر كود لتنفيذ منطق/إعداد
        "active": active,  # سطر كود لتنفيذ منطق/إعداد
        "active_m": active_m,  # سطر كود لتنفيذ منطق/إعداد
        "active_f": active_f,  # سطر كود لتنفيذ منطق/إعداد
        "removed": removed,  # سطر كود لتنفيذ منطق/إعداد
        "removed_m": removed_m,  # سطر كود لتنفيذ منطق/إعداد
        "removed_f": removed_f,  # سطر كود لتنفيذ منطق/إعداد
        "recent_removed": recent_removed,  # سطر كود لتنفيذ منطق/إعداد
    }  # سطر كود لتنفيذ منطق/إعداد




def _summary_bundle(rows, label=None):  # تعريف دالة (Function)
    summary = _summarize_rows(rows)
    return {
        "label": label or "",
        "total": summary["total"],
        "active": summary["active"],
        "removed": summary["removed"],
        "recent_removed": summary["recent_removed"],
        "active_m": summary["active_m"],
        "active_f": summary["active_f"],
        "removed_m": summary["removed_m"],
        "removed_f": summary["removed_f"],
    }

@register.inclusion_tag("admin/dashboard_cards.html", takes_context=True)  # سطر كود لتنفيذ منطق/إعداد
def dashboard_cards(context):  # تعريف دالة (Function)
    request = context.get("request")
    selected = ""
    cohort = "all"
    if request:
        selected = (request.GET.get("report") or "").strip().lower()
        cohort = (request.GET.get("cohort") or "all").strip().lower()

    cohort, cohort_label = _cohort_meta(cohort)
    selected_info = _PROGRAM_MAP.get(selected)

    metric_mode = "all"
    metric_title_1 = "إجمالي المتكوّنين"
    metric_title_2 = "الحالي"
    metric_title_3 = "المشطوب"
    metric_title_4 = "مشطوب حديثًا"
    metric_note_1 = ""
    metric_note_2 = ""
    metric_note_3 = ""
    metric_note_4 = "قبل مرور شهر على تاريخ الشطب"

    if selected_info:
        selected_label, selected_model = selected_info
        rows = _rows_for_cohort(selected_model, cohort)
        metrics = _summary_bundle(rows, selected_label)
        total_m, total_f = _gender_totals(rows)

        grand_total = len(rows)
        title = f"إحصائيات {selected_label}"
        if cohort != "all":
            title += f" — {cohort_label}"
        chart_title = f"الرسم البياني لتفصيل {selected_label}"
        if cohort == "current":
            chart_title += " — الحاليون فقط"
            totals = [
                {"label": "الحاليون", "count": grand_total},
                {"label": "ذكور الحاليين", "count": total_m},
                {"label": "إناث الحاليين", "count": total_f},
            ]
            totals_labels = ["الحاليون", "ذكور الحاليين", "إناث الحاليين"]
            totals_counts = [grand_total, total_m, total_f]
            metric_mode = "current"
            metric_title_1 = "الحاليون"
            metric_title_2 = "ذكور الحاليين"
            metric_title_3 = "إناث الحاليين"
            metric_title_4 = "النسبة من النظام"
            metric_note_1 = selected_label
            metric_note_2 = selected_label
            metric_note_3 = selected_label
            metric_note_4 = f"من {selected_label}"
            total_all_rows = _rows_for_cohort(selected_model, "all")
            total_all_count = len(total_all_rows)
            current_share = _pct(grand_total, total_all_count)
            metrics = {
                **metrics,
                "total": grand_total,
                "active": total_m,
                "removed": total_f,
                "recent_removed": current_share,
            }
        elif cohort == "graduates":
            chart_title += " — المتخرجون فقط"
            totals = [
                {"label": "المتخرجون", "count": grand_total},
                {"label": "ذكور المتخرجين", "count": total_m},
                {"label": "إناث المتخرجين", "count": total_f},
            ]
            totals_labels = ["المتخرجون", "ذكور المتخرجين", "إناث المتخرجين"]
            totals_counts = [grand_total, total_m, total_f]
            metric_mode = "graduates"
            metric_title_1 = "المتخرجون"
            metric_title_2 = "ذكور المتخرجين"
            metric_title_3 = "إناث المتخرجين"
            metric_title_4 = "النسبة من النظام"
            metric_note_1 = selected_label
            metric_note_2 = selected_label
            metric_note_3 = selected_label
            metric_note_4 = f"من {selected_label}"
            total_all_rows = _rows_for_cohort(selected_model, "all")
            total_all_count = len(total_all_rows)
            grad_share = _pct(grand_total, total_all_count)
            metrics = {
                **metrics,
                "total": grand_total,
                "active": total_m,
                "removed": total_f,
                "recent_removed": grad_share,
            }
        else:
            total_count = metrics["total"]
            active_count = metrics["active"]
            active_m = metrics["active_m"]
            active_f = metrics["active_f"]
            removed_count = metrics["removed"]
            removed_m = metrics["removed_m"]
            removed_f = metrics["removed_f"]
            metric_note_2 = f"ذكور {active_m} · إناث {active_f}"
            metric_note_3 = f"ذكور {removed_m} · إناث {removed_f}"
            totals = [
                {"label": selected_label, "count": total_count},
                {"label": "الحالي", "count": active_count},
                {"label": "المشطوبين", "count": removed_count},
                {"label": "مشطوب حديثًا", "count": metrics["recent_removed"]},
            ]
            totals_labels = ["التعداد الحالي", "ذكور الحالي", "إناث الحالي", "تعداد المشطوبين", "ذكور المشطوبين", "إناث المشطوبين"]
            totals_counts = [active_count, active_m, active_f, removed_count, removed_m, removed_f]
    else:
        all_rows = []
        program_totals = []
        for label, m in MODELS:
            rows = list(m.objects.all().values("الجنس", "الحالة", "تاريخ_الشطب"))
            all_rows.extend(rows)
            program_totals.append(_summary_bundle(rows, label))
        metrics = _summary_bundle(all_rows, "إجمالي المتكوّنين")
        totals = [{"label": item["label"], "count": item["total"]} for item in program_totals]
        grand_total = metrics["total"]
        metric_note_2 = f"ذكور {metrics['active_m']} · إناث {metrics['active_f']}"
        metric_note_3 = f"ذكور {metrics['removed_m']} · إناث {metrics['removed_f']}"
        title = "إجمالي المتكوّنين"
        chart_title = "الرسم البياني الإجمالي حسب النظام"
        totals_labels = [t["label"] for t in totals]
        totals_counts = [t["count"] for t in totals]

    charts_json = {
        "totals_labels": totals_labels,
        "totals_counts": totals_counts,
        "status_labels": [],
        "status_counts": [],
        "specialty_labels": [],
        "specialty_counts": [],
        "wilaya_labels": [],
        "wilaya_counts": [],
    }

    return {
        "grand_total": grand_total,
        "totals": totals,
        "charts_json": mark_safe(json.dumps(charts_json, ensure_ascii=False)),
        "selected_report": selected,
        "summary_title": title,
        "chart_title": chart_title,
        "metrics": metrics,
        "cohort": cohort,
        "cohort_label": cohort_label,
        "metric_mode": metric_mode,
        "metric_title_1": metric_title_1,
        "metric_title_2": metric_title_2,
        "metric_title_3": metric_title_3,
        "metric_title_4": metric_title_4,
        "metric_note_1": metric_note_1,
        "metric_note_2": metric_note_2,
        "metric_note_3": metric_note_3,
        "metric_note_4": metric_note_4,
    }


# ---------- تقرير حسب التخصص/السداسي ----------

_PROGRAM_MAP = {  # تعيين قيمة لمتغير/إعداد
    "initial": ("حضوري أولي", حضوري_أولي),  # سطر كود لتنفيذ منطق/إعداد
    "apprentice": ("التمهين", تمهين),  # سطر كود لتنفيذ منطق/إعداد
    "evening": ("الدروس المسائية", مسائي_ومعابر),  # سطر كود لتنفيذ منطق/إعداد
    "crossing": ("المعابر", مسائي_ومعابر),  # سطر كود لتنفيذ منطق/إعداد
}  # سطر كود لتنفيذ منطق/إعداد


def _filter_program_queryset(Model, key):
    qs = Model.objects.all()
    if Model.__name__ == "مسائي_ومعابر":
        if key == "evening":
            qs = qs.filter(نوع_التكوين="مسائي")
        elif key == "crossing":
            qs = qs.filter(نوع_التكوين="معابر")
    return qs

def _gender_code(raw: str) -> str:  # تعريف دالة (Function)
    s = str(raw or "").strip()  # تعيين قيمة لمتغير/إعداد
    if not s:  # شرط (If)
        return ""  # إرجاع قيمة من الدالة
    # allow common variants
    if "ذكر" in s or s.lower() in ("m", "male"):  # شرط (If)
        return "m"  # إرجاع قيمة من الدالة
    if "أنث" in s or "انث" in s or s.lower() in ("f", "female"):  # شرط (If)
        return "f"  # إرجاع قيمة من الدالة
    return ""  # إرجاع قيمة من الدالة



def _is_graduate(end_date):  # تعريف دالة (Function)
    if not end_date:  # شرط (If)
        return False  # إرجاع قيمة من الدالة
    return end_date <= timezone.localdate()  # إرجاع قيمة من الدالة


def _cohort_meta(code: str):  # تعريف دالة (Function)
    value = (code or "all").strip().lower()
    if value not in {"all", "current", "graduates"}:
        value = "all"
    labels = {
        "all": "الكل",
        "current": "الحاليون",
        "graduates": "المتخرجون",
    }
    return value, labels[value]


def _rows_for_cohort(model_cls, cohort: str):
    today = timezone.localdate()
    qs = model_cls.objects.all()
    if cohort == "current":
        qs = qs.filter(Q(تاريخ_نهاية_التكوين__isnull=True) | Q(تاريخ_نهاية_التكوين__gt=today))
        qs = qs.exclude(Q(الحالة__icontains="شطب") & (Q(تاريخ_الشطب__isnull=True) | Q(تاريخ_الشطب__lte=_subtract_one_month(today))))
    elif cohort == "graduates":
        qs = qs.filter(تاريخ_نهاية_التكوين__isnull=False, تاريخ_نهاية_التكوين__lte=today)
    return list(qs.values("الجنس", "الحالة", "تاريخ_الشطب", "تاريخ_نهاية_التكوين"))


def _gender_totals(rows):
    total_m = total_f = 0
    for row in rows:
        g = _gender_code(row.get("الجنس"))
        if g == "m":
            total_m += 1
        elif g == "f":
            total_f += 1
    return total_m, total_f

def _pct(n, d, places: int = 2) -> str:  # تعريف دالة (Function)
    # سطر كود لتنفيذ منطق/إعداد
    """Percent with fixed decimals (default 2). Returns string without '%' sign.
    Uses denominator d; if d is 0 returns '0.00'.  # سطر كود لتنفيذ منطق/إعداد
    # سطر كود لتنفيذ منطق/إعداد
    """
    try:  # سطر كود لتنفيذ منطق/إعداد
        n = Decimal(str(int(n or 0)))  # تعيين قيمة لمتغير/إعداد
        d = Decimal(str(int(d or 0)))  # تعيين قيمة لمتغير/إعداد
    except Exception:  # سطر كود لتنفيذ منطق/إعداد
        return f"{0:.{places}f}"  # إرجاع قيمة من الدالة
    if d <= 0:  # شرط (If)
        return f"{0:.{places}f}"  # إرجاع قيمة من الدالة
    p = (n * Decimal("100")) / d  # تعيين قيمة لمتغير/إعداد
    # تعيين قيمة لمتغير/إعداد
    q = Decimal("1").scaleb(-places)  # 10^-places
    p = p.quantize(q, rounding=ROUND_HALF_UP)  # تعيين قيمة لمتغير/إعداد
    # format keeps trailing zeros
    return f"{p:.{places}f}"  # إرجاع قيمة من الدالة


@register.inclusion_tag("admin/dashboard_report.html", takes_context=True)  # تعيين قيمة لمتغير/إعداد
def dashboard_report(context):  # تعريف دالة (Function)
    request = context.get("request")  # تعيين قيمة لمتغير/إعداد
    selected = ""  # تعيين قيمة لمتغير/إعداد
    cohort = "all"  # تعيين قيمة لمتغير/إعداد
    if request:  # شرط (If)
        selected = (request.GET.get("report") or "").strip().lower()  # تعيين قيمة لمتغير/إعداد
        cohort = (request.GET.get("cohort") or "all").strip().lower()  # تعيين قيمة لمتغير/إعداد

    label, Model = _PROGRAM_MAP.get(selected, ("", None))  # تعيين قيمة لمتغير/إعداد
    cohort, cohort_label = _cohort_meta(cohort)

    if not Model:  # شرط (If)
        return {"report": {"rows": [], "label": "", "selected": selected, "totals": {}, "cohort": cohort, "cohort_label": cohort_label}}  # إرجاع قيمة من الدالة

    # طبّق الفصل على مستوى الاستعلام نفسه حتى لا تبقى أي سجلات مختلطة في الجدول.
    today = timezone.localdate()
    qs = _filter_program_queryset(Model, selected)
    if cohort == "current":
        qs = qs.filter(Q(تاريخ_نهاية_التكوين__isnull=True) | Q(تاريخ_نهاية_التكوين__gt=today))
        # الحاليون = غير متخرجين وغير مشطوبين محسوبين.
        qs = qs.exclude(Q(الحالة__icontains="شطب") & (Q(تاريخ_الشطب__isnull=True) | Q(تاريخ_الشطب__lte=_subtract_one_month(today))))
    elif cohort == "graduates":
        # المتخرجون = من انتهى تكوينهم فعلاً بغض النظر عن الحالة النصية.
        qs = qs.filter(تاريخ_نهاية_التكوين__isnull=False, تاريخ_نهاية_التكوين__lte=today)

    qs = qs.values("رمز_التخصص", "التخصص", "السداسي", "الجنس", "الحالة", "تاريخ_الشطب", "تاريخ_نهاية_التكوين")  # تعيين قيمة لمتغير/إعداد

    # Aggregate in Python (simple + clear for SQLite)
    agg = {}  # تعيين قيمة لمتغير/إعداد
    totals = dict(total=0, total_m=0, total_f=0, active=0, active_m=0, active_f=0, removed=0, removed_m=0, removed_f=0)  # تعيين قيمة لمتغير/إعداد

    for row in qs.iterator(chunk_size=2000):  # حلقة تكرار (For)
        counted_removed = _is_counted_removed(row.get("الحالة"), row.get("تاريخ_الشطب"))  # تعيين قيمة لمتغير/إعداد
        is_graduate = _is_graduate(row.get("تاريخ_نهاية_التكوين"))  # تعيين قيمة لمتغير/إعداد

        code = (row.get("رمز_التخصص") or "").strip()  # تعيين قيمة لمتغير/إعداد
        spec = (row.get("التخصص") or "").strip()  # تعيين قيمة لمتغير/إعداد
        sem = (row.get("السداسي") or "").strip()  # تعيين قيمة لمتغير/إعداد
        key = (code, spec, sem)  # تعيين قيمة لمتغير/إعداد
        if key not in agg:  # شرط (If)
            agg[key] = dict(code=code, specialty=spec, semester=sem,  # تعيين قيمة لمتغير/إعداد
                            total=0, total_m=0, total_f=0,  # تعيين قيمة لمتغير/إعداد
                            active=0, active_m=0, active_f=0,  # تعيين قيمة لمتغير/إعداد
                            removed=0, removed_m=0, removed_f=0)  # تعيين قيمة لمتغير/إعداد
        g = _gender_code(row.get("الجنس"))  # تعيين قيمة لمتغير/إعداد

        # total (عدد المدمجين)
        agg[key]["total"] += 1  # تعيين قيمة لمتغير/إعداد
        totals["total"] += 1  # تعيين قيمة لمتغير/إعداد
        if g == "m":  # شرط (If)
            agg[key]["total_m"] += 1  # تعيين قيمة لمتغير/إعداد
            totals["total_m"] += 1  # تعيين قيمة لمتغير/إعداد
        elif g == "f":  # شرط بديل (Elif)
            agg[key]["total_f"] += 1  # تعيين قيمة لمتغير/إعداد
            totals["total_f"] += 1  # تعيين قيمة لمتغير/إعداد

        # current / removed
        # التعداد الحالي = كل من ليس مشطوباً
        if not counted_removed:  # شرط (If)
            agg[key]["active"] += 1  # تعيين قيمة لمتغير/إعداد
            totals["active"] += 1  # تعيين قيمة لمتغير/إعداد
            if g == "m":  # شرط (If)
                agg[key]["active_m"] += 1  # تعيين قيمة لمتغير/إعداد
                totals["active_m"] += 1  # تعيين قيمة لمتغير/إعداد
            elif g == "f":  # شرط بديل (Elif)
                agg[key]["active_f"] += 1  # تعيين قيمة لمتغير/إعداد
                totals["active_f"] += 1  # تعيين قيمة لمتغير/إعداد
        if counted_removed:  # شرط (If)
            agg[key]["removed"] += 1  # تعيين قيمة لمتغير/إعداد
            totals["removed"] += 1  # تعيين قيمة لمتغير/إعداد
            if g == "m":  # شرط (If)
                agg[key]["removed_m"] += 1  # تعيين قيمة لمتغير/إعداد
                totals["removed_m"] += 1  # تعيين قيمة لمتغير/إعداد
            elif g == "f":  # شرط بديل (Elif)
                agg[key]["removed_f"] += 1  # تعيين قيمة لمتغير/إعداد
                totals["removed_f"] += 1  # تعيين قيمة لمتغير/إعداد

    
    # Build rows + percentages
    rows = []  # تعيين قيمة لمتغير/إعداد
    for (_, _, _), r in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):  # حلقة تكرار (For)
        total = r["total"]  # تعيين قيمة لمتغير/إعداد

        # % الحالي و % المشطوب نسبةً إلى عدد المدمجين
        r["active_pct"] = _pct(r["active"], total)  # تعيين قيمة لمتغير/إعداد
        r["removed_pct"] = _pct(r["removed"], total)  # تعيين قيمة لمتغير/إعداد

        # % ذكور/إناث داخل "الحالي" (نسبةً إلى التعداد الحالي)
        r["active_m_pct"] = _pct(r["active_m"], r["active"])  # تعيين قيمة لمتغير/إعداد
        r["active_f_pct"] = _pct(r["active_f"], r["active"])  # تعيين قيمة لمتغير/إعداد

        # % ذكور/إناث داخل "المشطوب" (نسبةً إلى تعداد المشطوبين)
        r["removed_m_pct"] = _pct(r["removed_m"], r["removed"])  # تعيين قيمة لمتغير/إعداد
        r["removed_f_pct"] = _pct(r["removed_f"], r["removed"])  # تعيين قيمة لمتغير/إعداد

        rows.append(r)  # سطر كود لتنفيذ منطق/إعداد


    # Totals percentages
    # - % الحالي / % المشطوب على الإجمالي
    totals["active_pct"] = _pct(totals["active"], totals["total"])  # تعيين قيمة لمتغير/إعداد
    totals["removed_pct"] = _pct(totals["removed"], totals["total"])  # تعيين قيمة لمتغير/إعداد

    # - توزيع الذكور/الإناث داخل الحالي / المشطوب على الإجمالي
    totals["active_m_pct"] = _pct(totals["active_m"], totals["active"])  # تعيين قيمة لمتغير/إعداد
    totals["active_f_pct"] = _pct(totals["active_f"], totals["active"])  # تعيين قيمة لمتغير/إعداد

    totals["removed_m_pct"] = _pct(totals["removed_m"], totals["removed"])  # تعيين قيمة لمتغير/إعداد
    totals["removed_f_pct"] = _pct(totals["removed_f"], totals["removed"])  # تعيين قيمة لمتغير/إعداد

    return {"report": {"rows": rows, "label": label, "selected": selected, "totals": totals, "cohort": cohort, "cohort_label": cohort_label}}  # إرجاع قيمة من الدالة


@register.simple_tag  # سطر كود لتنفيذ منطق/إعداد
def quick_counts():  # تعريف دالة (Function)
    # سطر كود لتنفيذ منطق/إعداد
    """Counts for the top quick buttons (all/active/removed) per program.
    - active = كل من ليس مشطوباً  # تعيين قيمة لمتغير/إعداد
    - repeater = للتمهين فقط (معيد)  # تعيين قيمة لمتغير/إعداد
    # سطر كود لتنفيذ منطق/إعداد
    """
    data = {}  # تعيين قيمة لمتغير/إعداد
    for key, (label, Model) in _PROGRAM_MAP.items():  # حلقة تكرار (For)
        qs = _filter_program_queryset(Model, key)
        summary = _summarize_rows(qs.values("الجنس", "الحالة", "تاريخ_الشطب"))  # تعيين قيمة لمتغير/إعداد
        total = summary["total"]  # تعيين قيمة لمتغير/إعداد
        active = summary["active"]  # تعيين قيمة لمتغير/إعداد
        removed = summary["removed"]  # تعيين قيمة لمتغير/إعداد
        recent_removed = summary["recent_removed"]  # تعيين قيمة لمتغير/إعداد
        repeater = 0  # تعيين قيمة لمتغير/إعداد
        if key == "apprentice":  # شرط (If)
            repeater = qs.filter(معيد=True).count()  # تعيين قيمة لمتغير/إعداد
        data[key] = {"label": label, "total": total, "active": active, "removed": removed, "recent_removed": recent_removed, "repeater": repeater}  # تعيين قيمة لمتغير/إعداد
    return data  # إرجاع قيمة من الدالة
