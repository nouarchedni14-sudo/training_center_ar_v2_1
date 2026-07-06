from __future__ import annotations

from collections import Counter
from typing import Iterable, List, Dict, Any

CATEGORY_LABELS = {
    "header_mismatch": "عدم تطابق الأعمدة",
    "missing_required": "بيانات أساسية ناقصة",
    "invalid_date": "تواريخ غير صالحة",
    "invalid_birthdate": "تاريخ ميلاد غير صالح",
    "duplicate_in_file": "تكرار داخل نفس الملف",
    "duplicate_existing": "سجل موجود مسبقًا",
    "invalid_registration": "تعذر تحليل رقم التسجيل",
    "save_error": "أخطاء أثناء الحفظ",
    "generic": "ملاحظات عامة",
}

CATEGORY_PRIORITY = [
    "header_mismatch",
    "missing_required",
    "invalid_date",
    "invalid_birthdate",
    "duplicate_in_file",
    "duplicate_existing",
    "invalid_registration",
    "save_error",
    "generic",
]


def build_import_issue(category: str, message: str, row_index: int | None = None, row_identity: str = "") -> Dict[str, Any]:
    prefix = []
    if row_index is not None:
        prefix.append(f"السطر {row_index}")
    if row_identity:
        prefix.append(str(row_identity).strip())
    rendered_prefix = " — ".join([part for part in prefix if part])
    rendered_message = f"{rendered_prefix}: {message}" if rendered_prefix else str(message)
    return {
        "category": category or "generic",
        "category_label": CATEGORY_LABELS.get(category or "generic", CATEGORY_LABELS["generic"]),
        "row_index": row_index,
        "row_identity": row_identity,
        "message": rendered_message,
        "raw_message": str(message),
    }


def summarize_import_issues(issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = list(issues)
    counts = Counter(issue.get("category") or "generic" for issue in normalized)
    ordered_categories = sorted(
        counts,
        key=lambda item: (
            CATEGORY_PRIORITY.index(item) if item in CATEGORY_PRIORITY else len(CATEGORY_PRIORITY),
            item,
        ),
    )
    return [
        {
            "category": category,
            "label": CATEGORY_LABELS.get(category, CATEGORY_LABELS["generic"]),
            "count": counts[category],
        }
        for category in ordered_categories
    ]


def group_import_issues(issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        category = issue.get("category") or "generic"
        buckets.setdefault(category, []).append(issue)

    ordered_categories = sorted(
        buckets,
        key=lambda item: (
            CATEGORY_PRIORITY.index(item) if item in CATEGORY_PRIORITY else len(CATEGORY_PRIORITY),
            item,
        ),
    )
    return [
        {
            "category": category,
            "label": CATEGORY_LABELS.get(category, CATEGORY_LABELS["generic"]),
            "count": len(buckets[category]),
            "items": buckets[category],
        }
        for category in ordered_categories
    ]


def categorize_import_message(message: str) -> str:
    text = str(message or "")
    lowered = text.lower()
    if "الأعمدة" in text or "header" in lowered:
        return "header_mismatch"

    # أخطاء الحفظ يجب تصنيفها أولاً.
    # كانت تُحسب خطأً كـ "تعذر تحليل رقم التسجيل" لأن رسالة السطر تحتوي على
    # هوية المتكون وفيها عبارة "رقم التسجيل" مع "تعذر الحفظ الفردي".
    if (
        "خطأ أثناء الحفظ" in text
        or "تعذر الحفظ" in text
        or "violates not-null" in lowered
        or "null value in column" in lowered
        or "constraint" in lowered
        or "save" in lowered
    ):
        return "save_error"

    if "تاريخ الميلاد غير صالح" in text:
        return "invalid_birthdate"
    if "غير صالح" in text or "أقدم من" in text or "تاريخ" in text:
        return "invalid_date"
    if "ناقصة" in text or "مطلوب" in text:
        return "missing_required"
    if "مكرر داخل الملف" in text or "مكرر" in text and "داخل الملف" in text:
        return "duplicate_in_file"
    if "موجود من قبل" in text or "موجود مسبقا" in text or "موجود مسبقًا" in text:
        return "duplicate_existing"
    if "رقم التسجيل" in text and ("تعذر استخراج رقم الدورة" in text or "غير صالح" in text):
        return "invalid_registration"
    return "generic"
