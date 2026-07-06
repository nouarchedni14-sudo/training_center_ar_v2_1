# -*- coding: utf-8 -*-
"""أدوات فصل الدروس المسائية عن المعابر مع بقاء نفس جدول قاعدة البيانات."""
from __future__ import annotations

import re
from typing import Any

EVENING_TRAINING_TYPE_EVENING = "مسائي"
EVENING_TRAINING_TYPE_CROSSING = "معابر"
EVENING_TRAINING_TYPE_CHOICES = [
    (EVENING_TRAINING_TYPE_EVENING, "دروس مسائية"),
    (EVENING_TRAINING_TYPE_CROSSING, "معابر"),
]

_CROSSING_WORDS_RE = re.compile(r"\s*(?:[-–—_/\\|،,؛;:]*\s*)?(?:معابر|معبر)\s*", re.IGNORECASE)
_SEMESTER_ORDER = ["الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس"]


def normalize_evening_training_type(value: Any) -> str:
    text = str(value or "").strip().replace("ـ", "")
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text)
    if "معابر" in compact or "معبر" in compact or compact.lower() in {"crossing", "passerelle"}:
        return EVENING_TRAINING_TYPE_CROSSING
    if "مسائي" in compact or "المسائية" in compact or "عادي" in compact or compact.lower() in {"evening", "normal"}:
        return EVENING_TRAINING_TYPE_EVENING
    return ""


def clean_crossing_specialty_label(value: Any) -> str:
    """احذف كلمة معابر من اسم التخصص حتى لا تتكرر تخصصات مثل: مصمم البساتين/مصمم البساتين معابر."""
    text = str(value or "").replace("\u00A0", " ").strip()
    if not text:
        return ""
    text = _CROSSING_WORDS_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—_/\\|،,؛;:")
    return text.strip()


def contains_crossing_marker(*values: Any) -> bool:
    joined = " ".join(str(v or "") for v in values)
    return "معابر" in joined or "معبر" in joined


def training_duration_months(start_date, end_date):
    if not start_date or not end_date:
        return None
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day >= start_date.day:
        months += 1
    return months


def detect_evening_training_type(data_or_obj: Any, respect_explicit_evening: bool = True) -> str:
    """حدد هل السطر/المتكون مسائي عادي أم معابر.

    الأولوية:
    1) إذا كانت القيمة الصريحة معابر نعتمدها دائماً.
    2) إذا كانت القيمة الصريحة مسائي نعتمدها فقط عند respect_explicit_evening=True.
       هذا مهم لأن الهجرة تضيف القيمة الافتراضية مسائي للسجلات القديمة، ولا نريد أن تمنع التصنيف حسب المدة.
    3) وجود كلمة معابر/معبر في التخصص أو النظام.
    4) مدة تكوين سنة تقريباً <= 14 شهراً.
    5) الافتراضي: مسائي.
    """
    def get(name: str):
        if isinstance(data_or_obj, dict):
            return data_or_obj.get(name)
        return getattr(data_or_obj, name, None)

    explicit = normalize_evening_training_type(get("نوع_التكوين") or get("نوع التكوين") or get("نمط_التكوين") or get("نمط التكوين"))
    if explicit == EVENING_TRAINING_TYPE_CROSSING:
        return EVENING_TRAINING_TYPE_CROSSING
    if explicit == EVENING_TRAINING_TYPE_EVENING and respect_explicit_evening:
        return EVENING_TRAINING_TYPE_EVENING

    if contains_crossing_marker(get("التخصص"), get("النظام"), get("رمز_التخصص"), get("رمز التخصص")):
        return EVENING_TRAINING_TYPE_CROSSING

    months = training_duration_months(get("تاريخ_بداية_التكوين"), get("تاريخ_نهاية_التكوين"))
    if months is not None and months <= 14:
        return EVENING_TRAINING_TYPE_CROSSING

    return EVENING_TRAINING_TYPE_EVENING


def clamp_semester_for_evening_type(semester: Any, training_type: str) -> str:
    semester = str(semester or "").strip()
    if training_type != EVENING_TRAINING_TYPE_CROSSING:
        return semester
    if not semester:
        return semester
    if semester in {"الأول", "الثاني"}:
        return semester
    if semester in _SEMESTER_ORDER:
        return "الثاني"
    return semester
