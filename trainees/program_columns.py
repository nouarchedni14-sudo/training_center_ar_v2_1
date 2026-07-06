# -*- coding: utf-8 -*-
"""
الأعمدة الرسمية لصفحات البرامج وقوالب/استيراد Excel.

تم ضبطها حسب ملف: اعمدة البرنامج.xlsx
- ورقة الإقامي       -> initial
- ورقة التمهين       -> apprentice
- ورقة دروس_م        -> evening
"""
from __future__ import annotations

from typing import Dict, List, Tuple

ColumnDef = Tuple[str, str]

COMMON_EXCEL_COLUMNS: List[ColumnDef] = [
    ("الرقم_التعريفي", "الرقم التعريفي"),
    ("اللقب", "اللقب"),
    ("الاسم", "الإسم"),
    ("الاسم_بالأجنبية", "الإسم الكامل باللغة الاجنبية"),
    ("تاريخ_الميلاد", "تاريخ الميلاد"),
    ("مفترض", "مفترض"),
    ("البلدية", "البلدية"),
    ("الولاية", "الولاية"),
    ("التخصص", "التخصص"),
    ("رقم_التسجيل", "رقم التسجيل"),
    ("تاريخ_بداية_التكوين", "تاريخ بداية التكوين"),
    ("تاريخ_نهاية_التكوين", "تاريخ نهاية التكوين"),
    ("السداسي", "السداسي"),
    ("الجنس", "الجنس"),
    ("الحالة", "الحالة"),
    ("تاريخ_الشطب", "تاريخ الشطب"),
    ("رقم_الشطب", "رقم/ م-الشطب"),
    ("رقم_مقرر_الفصل", "رقم مقرر الفصل"),
    ("رمز_التخصص", "رمز التخصص"),
    ("رقم_عقد_الميلاد", "رقم عقد الميلاد"),
    ("زمرة_الدم", "زمرة الدم"),
    ("اسم_الأب", "إسم الأب"),
    ("لقب_الأم", "لقب الأم"),
    ("اسم_الأم", "إسم الأم"),
    ("اسم_الأب_بالأجنبية", "إسم الأب بالأجنبية"),
    ("لقب_الأم_بالأجنبية", "لقب الأم بالأجنبية"),
    ("اسم_الأم_بالأجنبية", "إسم الأم بالأجنبية"),
    ("البريد_الإلكتروني", "البريد الإلكتروني"),
    ("رقم_الهاتف", "رقم الهاتف"),
    ("النظام", "النظام"),
    ("رقم_التعريف_الوطني", "ب-التعريف الوطنية"),
    ("رقم_الضمان_الاجتماعي", "رقم الضمان الاجتماعي"),
    ("العنوان_بالعربية", "العنوان بالعربية"),
    ("بلدية_الإقامة_بالعربية", "بلدية الإقامة بالعربية"),
    ("ولاية_الإقامة_بالعربية", "ولاية الإقامة بالعربية"),
    ("العنوان_بالأجنبية", "العنوان بالأجنبية"),
    ("ولاية_الإقامة_بالأجنبية", "ولاية الإقامة بالأجنبية"),
]

APPRENTICE_EXCEL_COLUMNS: List[ColumnDef] = [
    *COMMON_EXCEL_COLUMNS[:20],
    ("معيد", "معيد"),
    ("تاريخ_التكوين_السابق_للمعيدين", "تاريخ التكوين السابق للمعيدين"),
    *COMMON_EXCEL_COLUMNS[20:],
    ("المستخدم", "المستخدم"),
]

# عمود نوع التكوين اختياري في الاستيراد، لكنه يظهر في العرض/التصدير
# ويفصل الدروس المسائية عن المعابر داخل نفس جدول قاعدة البيانات.
EVENING_EXCEL_COLUMNS: List[ColumnDef] = [
    *COMMON_EXCEL_COLUMNS[:9],
    ("نوع_التكوين", "نوع التكوين"),
    *COMMON_EXCEL_COLUMNS[9:],
]

EXCEL_COLUMNS_BY_PROGRAM: Dict[str, List[ColumnDef]] = {
    "initial": COMMON_EXCEL_COLUMNS,
    "apprentice": APPRENTICE_EXCEL_COLUMNS,
    "evening": EVENING_EXCEL_COLUMNS,
    "crossing": EVENING_EXCEL_COLUMNS,
}

DISPLAY_PROGRAM_COLUMNS: Dict[str, List[ColumnDef]] = {
    key: [("__actions__", "إجراءات"), *cols]
    for key, cols in EXCEL_COLUMNS_BY_PROGRAM.items()
}

MODEL_NAME_TO_PROGRAM = {
    "حضوري_أولي": "initial",
    "تمهين": "apprentice",
    "مسائي_ومعابر": "evening",
}

# أعمدة موجودة في ملفات العرض/Excel لكنها محسوبة/داخلية ولا تُحفظ مباشرة أثناء الاستيراد.
# ملاحظة: رقم_مقرر_الفصل أصبح حقلاً حقيقياً في BaseTrainee ويُستورد من Excel.
IGNORED_IMPORT_FIELDS = {"السداسي", "الدفعة"}


def program_key_for_model(model_cls) -> str:
    return MODEL_NAME_TO_PROGRAM.get(getattr(model_cls, "__name__", ""), "initial")


def excel_columns_for_program(program: str) -> List[ColumnDef]:
    return list(EXCEL_COLUMNS_BY_PROGRAM.get(program, COMMON_EXCEL_COLUMNS))


def excel_columns_for_model(model_cls, include_assumed: bool = False) -> List[ColumnDef]:
    columns = excel_columns_for_program(program_key_for_model(model_cls))
    if include_assumed:
        return list(columns)
    # لا نجعل عمود مفترض ولا نوع التكوين إجباريين في الاستيراد، لكن عند وجودهما يتم قراءتهما.
    return [(field, label) for field, label in columns if field not in {"مفترض", "نوع_التكوين"}]
