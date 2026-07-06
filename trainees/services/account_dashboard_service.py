from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Iterable

PROGRAM_LABELS = {
    "initial": "الحضوري الأولي",
    "apprentice": "التكوين عن طريق التمهين",
    "evening": "الدروس المسائية",
    "crossing": "المعابر",
}


def _label_list(values: Iterable[str] | None) -> list[str]:
    cleaned: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def build_access_ui(access_summary: dict[str, Any]) -> dict[str, str]:
    state = access_summary.get("state") or "unknown"
    mapping = {
        "superuser": {
            "badge_class": "success",
            "title": "الحساب يعمل بصلاحية كاملة",
            "hint": "هذا الحساب يملك كل الصلاحيات ويمكنه الوصول إلى كل أقسام النظام.",
        },
        "active": {
            "badge_class": "success",
            "title": "الحساب مفعّل",
            "hint": "الصلاحيات الحالية تسمح باستعمال النظام ضمن النافذة المحددة.",
        },
        "expiring_soon": {
            "badge_class": "warn",
            "title": "الصلاحية تقترب من الانتهاء",
            "hint": "يفضل مراجعة نافذة التفعيل قبل انقطاع الوصول إلى النظام.",
        },
        "expired": {
            "badge_class": "danger",
            "title": "انتهت صلاحية الحساب",
            "hint": "يجب تجديد نافذة الصلاحية أو تمديدها من لوحة الإدارة.",
        },
        "inactive": {
            "badge_class": "danger",
            "title": "الحساب غير مفعّل",
            "hint": "فعّل الحساب أولاً ثم تحقق من إعدادات الصلاحيات والنافذة الزمنية.",
        },
        "outside_window": {
            "badge_class": "danger",
            "title": "الوصول خارج الفترة المسموح بها",
            "hint": "الحساب موجود لكن لا يمكنه الدخول الآن بسبب القيود الزمنية الحالية.",
        },
        "missing": {
            "badge_class": "warn",
            "title": "لا يوجد ملف صلاحيات",
            "hint": "أنشئ ملف صلاحيات لهذا المستخدم ثم امنحه البرامج المطلوبة.",
        },
        "anonymous": {
            "badge_class": "",
            "title": "يجب تسجيل الدخول",
            "hint": "لن تظهر الصلاحيات التفصيلية إلا بعد تسجيل الدخول بالحساب المعتمد.",
        },
    }
    default = {
        "badge_class": "",
        "title": access_summary.get("state_label") or "حالة الحساب",
        "hint": access_summary.get("message") or "راجع إعدادات الصلاحيات لهذا المستخدم.",
    }
    return mapping.get(state, default)


def build_account_context(user: Any, build_access_summary_func: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
    access_summary = build_access_summary_func(user)
    allowed_programs_verbose = _label_list(access_summary.get("allowed_programs"))
    permission_cards = [
        {"label": "لوحة الإدارة", "value": "مسموح" if access_summary.get("can_access_admin") else "غير مسموح", "active": bool(access_summary.get("can_access_admin"))},
        {"label": "التقارير", "value": "مفعّل" if access_summary.get("can_view_reports") else "غير مفعّل", "active": bool(access_summary.get("can_view_reports"))},
        {"label": "التصدير", "value": "مفعّل" if access_summary.get("can_export_data") else "غير مفعّل", "active": bool(access_summary.get("can_export_data"))},
        {"label": "الأيام المسموح بها", "value": access_summary.get("allowed_weekdays") or "—", "active": True},
        {"label": "النافذة اليومية", "value": access_summary.get("daily_window") or "—", "active": True},
        {"label": "نوع الحساب", "value": access_summary.get("access_type") or "—", "active": True},
    ]
    return {
        "access_summary": access_summary,
        "access_ui": build_access_ui(access_summary),
        "allowed_programs_verbose": allowed_programs_verbose,
        "permission_cards": permission_cards,
    }


def _safe_reverse(reverse_func: Callable[..., str], name: str, *args: Any) -> str | None:
    try:
        return reverse_func(name, args=args or None)
    except Exception:
        try:
            return reverse_func(name)
        except Exception:
            return None


def _count_by_semester(rows: Iterable[Any]) -> list[dict[str, Any]]:
    counter = Counter(getattr(obj, "السداسي", "") or "غير محدد" for obj in rows)
    order = ["الأول", "الثاني", "الثالث", "الرابع", "الخامس", "غير محدد"]
    known = [{"السداسي": sem, "total": counter[sem]} for sem in order if counter.get(sem)]
    extras = [{"السداسي": sem, "total": total} for sem, total in counter.items() if sem not in order]
    extras.sort(key=lambda item: item["السداسي"])
    return known + extras


def _count_by_promotion(rows: Iterable[Any]) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, Any], int] = Counter()
    for obj in rows:
        promotion = getattr(obj, "الدفعة", None)
        name = getattr(promotion, "اسم_الدفعة", None) or "بدون دفعة"
        year = getattr(promotion, "السنة", None) or ""
        counter[(name, year)] += 1
    items = [
        {"الدفعة__اسم_الدفعة": name, "الدفعة__السنة": year, "total": total}
        for (name, year), total in counter.items()
    ]
    items.sort(key=lambda item: (str(item["الدفعة__اسم_الدفعة"]), str(item["الدفعة__السنة"])))
    return items


def build_dashboard_context(
    user: Any,
    *,
    program_specs: list[tuple[str, str, Any]],
    today: Any,
    allowed_programs: list[str],
    admin_access: bool,
    promotion_count: int,
    get_ordered_rows: Callable[[Any, str, bool], Iterable[Any]],
    refresh_rows_live_semesters: Callable[[Iterable[Any], Any], Iterable[Any]],
    build_access_summary_func: Callable[[Any], dict[str, Any]],
    reverse_func: Callable[..., str],
) -> dict[str, Any]:
    context = build_account_context(user, build_access_summary_func=build_access_summary_func)
    cards: list[dict[str, Any]] = []
    semester_stats: list[dict[str, Any]] = []
    promotion_stats: list[dict[str, Any]] = []

    for code, label, model_cls in program_specs:
        if allowed_programs and code not in allowed_programs and not admin_access:
            continue
        current_rows = list(refresh_rows_live_semesters(get_ordered_rows(model_cls, code, graduates=False), model_cls))
        graduate_rows = list(get_ordered_rows(model_cls, code, graduates=True))
        cards.append({
            "code": code,
            "label": label,
            "total_count": len(current_rows) + len(graduate_rows),
            "current_count": len(current_rows),
            "graduate_count": len(graduate_rows),
            "attendance_url": _safe_reverse(reverse_func, "attendance_program", code),
            "actions_url": _safe_reverse(reverse_func, "attendance_actions", code),
            "dismissal_url": _safe_reverse(reverse_func, "management_dismissal_redirect", code),
            "sanctions_url": _safe_reverse(reverse_func, "management_sanctions_redirect", code),
        })
        semester_stats.append({"code": code, "label": label, "items": _count_by_semester(current_rows)})
        promotion_stats.append({"code": code, "label": label, "items": _count_by_promotion(current_rows)})

    quick_links = []
    account_url = _safe_reverse(reverse_func, "account_overview")
    attendance_url = _safe_reverse(reverse_func, "attendance_home")
    if account_url:
        quick_links.append({"label": "حالة الحساب", "url": account_url})
    if attendance_url and (allowed_programs or admin_access):
        quick_links.append({"label": "جداول الغيابات", "url": attendance_url})
    if admin_access:
        quick_links.append({"label": "لوحة الإدارة", "url": "/admin/"})

    context.update({
        "today": today,
        "allowed_programs": allowed_programs,
        "cards": cards,
        "promotion_count": promotion_count,
        "semester_stats": semester_stats,
        "promotion_stats": promotion_stats,
        "quick_links": quick_links,
    })
    return context
