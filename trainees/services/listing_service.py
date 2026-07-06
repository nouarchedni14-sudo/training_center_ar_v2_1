from __future__ import annotations

from typing import Any, Iterable

from django.db.models import Q

SEMESTER_RANK = {"الأول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4, "الخامس": 5}


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def unique_clean_values(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = normalize_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def extract_list_filters(get_data) -> dict[str, str]:
    return {
        "q": normalize_text(get_data.get("q")),
        "semester": normalize_text(get_data.get("semester")),
        "year": normalize_text(get_data.get("year")),
        "promotion": normalize_text(get_data.get("promotion")),
        "status": normalize_text(get_data.get("status")),
        "specialty": normalize_text(get_data.get("specialty")),
    }


def apply_advanced_filters(qs, filters: dict[str, str]):
    q = filters.get("q", "")
    semester = filters.get("semester", "")
    year = filters.get("year", "")
    promotion_id = filters.get("promotion", "")
    status = filters.get("status", "")
    specialty = filters.get("specialty", "")

    if q:
        qs = qs.filter(
            Q(الرقم_التعريفي__icontains=q)
            | Q(اللقب__icontains=q)
            | Q(الاسم__icontains=q)
            | Q(التخصص__icontains=q)
            | Q(رقم_التسجيل__icontains=q)
            | Q(رقم_الهاتف__icontains=q)
        )
    if semester:
        qs = qs.filter(السداسي=semester)
    if specialty:
        qs = qs.filter(التخصص=specialty)
    if year.isdigit():
        qs = qs.filter(الدفعة__السنة=int(year))
    if promotion_id.isdigit():
        qs = qs.filter(الدفعة_id=int(promotion_id))
    if status == "active":
        qs = qs.exclude(الحالة__icontains="مشطوب").exclude(الحالة__icontains="شطب")
    elif status == "removed":
        qs = qs.filter(
            Q(الحالة__icontains="مشطوب")
            | Q(الحالة__icontains="شطب")
            | Q(الحالة__icontains="مفصول")
            | Q(الحالة__icontains="منقطع")
        )
    return qs


def build_semester_options(values: Iterable[Any]) -> list[str]:
    return sorted(unique_clean_values(values), key=lambda value: (SEMESTER_RANK.get(value, 99), value))


def build_specialty_options(values: Iterable[Any]) -> list[str]:
    return sorted(unique_clean_values(values))


def build_query_string_without_page(querydict) -> str:
    preserved = querydict.copy()
    preserved.pop("page", None)
    return preserved.urlencode()


def build_program_title(program: str, titles: dict[str, str], graduates: bool = False) -> str:
    title = titles.get(program, "المتكوّنون")
    return f"متخرجون - {title}" if graduates else title


def can_export_for_user(user) -> bool:
    profile = getattr(user, "access_profile", None)
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(profile, "can_export_data", False)
        or getattr(profile, "can_manage_all_programs", False)
    )
