# -*- coding: utf-8 -*-
"""مساعدات مركزية لفصل الدروس المسائية عن المعابر في كل الصفحات.

الفكرة الأساسية:
- الدروس المسائية والمعابر يبقيان في نفس جدول المتكونين `مسائي_ومعابر`.
- كل الصفحات التي تستعمل البرنامج `evening` يجب أن ترى فقط `نوع_التكوين = مسائي`.
- كل الصفحات التي تستعمل البرنامج `crossing` يجب أن ترى فقط `نوع_التكوين = معابر`.
"""
from __future__ import annotations

from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet

from .evening_training_type import (
    EVENING_TRAINING_TYPE_EVENING,
    EVENING_TRAINING_TYPE_CROSSING,
)

EVENING_SPLIT_PROGRAMS = {"evening", "crossing"}


INACTIVE_TRAINEE_STATUS_KEYWORDS = (
    "مشطوب",
    "شطب",
    "مفصول",
    "فصل",
    "متوقف",
    "موقوف",
    "توقف",
    "منقطع",
    "انسحب",
)


def inactive_trainee_status_filter() -> Q:
    """فلتر الحالات التي لا يجب إدراجها في الوثائق الإدارية العادية.

    هذه الحالات تبقى خاصة بمقرر الفصل أو الأرشيف التاريخي، ولا تدخل في
    العقوبات أو الاستدعاءات أو الإعذارات الجديدة.
    """
    condition = Q()
    for keyword in INACTIVE_TRAINEE_STATUS_KEYWORDS:
        condition |= Q(الحالة__icontains=keyword)
    return condition


def exclude_inactive_trainees(qs: QuerySet) -> QuerySet:
    """إرجاع المتكونين النشطين فقط للمتابعة الإدارية العادية."""
    return qs.exclude(inactive_trainee_status_filter())


def is_inactive_trainee(trainee) -> bool:
    status = str(getattr(trainee, "الحالة", "") or "").strip()
    return any(keyword in status for keyword in INACTIVE_TRAINEE_STATUS_KEYWORDS)


def active_trainee_ids_for_program(model_cls, program: str):
    qs = model_cls.objects.all()
    qs = filter_evening_trainee_queryset_by_program(qs, program)
    qs = exclude_inactive_trainees(qs)
    return qs.values_list("pk", flat=True)


def filter_generic_records_to_active_trainees(
    qs: QuerySet,
    program: str,
    model_cls,
    *,
    content_type_field: str = "trainee_content_type",
    object_id_field: str = "trainee_object_id",
) -> QuerySet:
    """إخفاء سجلات الوثائق الإدارية المرتبطة بمتكونين مشطوبين/مفصولين.

    لا نستعمل هذا في مقررات الفصل، لأنها الصفحة الوحيدة التي يجب أن ترى
    المفصولين والمشطوبين. يستعمل في الإعذارات، الاستدعاءات، والعقوبات.
    """
    if model_cls is None:
        return qs
    try:
        ct = ContentType.objects.get_for_model(model_cls)
        return qs.filter(
            **{
                content_type_field: ct,
                f"{object_id_field}__in": active_trainee_ids_for_program(model_cls, program),
            }
        )
    except Exception:
        return qs


def filter_records_by_split_program_for_active_trainees(
    qs: QuerySet,
    program: str,
    model_cls,
    *,
    program_field: str = "program",
    content_type_field: str = "trainee_content_type",
    object_id_field: str = "trainee_object_id",
) -> QuerySet:
    qs = filter_records_by_split_program(
        qs,
        program,
        program_field=program_field,
        content_type_field=content_type_field,
        object_id_field=object_id_field,
    )
    return filter_generic_records_to_active_trainees(
        qs,
        program,
        model_cls,
        content_type_field=content_type_field,
        object_id_field=object_id_field,
    )


def evening_training_type_for_program(program: str) -> Optional[str]:
    program = str(program or "").strip().lower()
    if program == "evening":
        return EVENING_TRAINING_TYPE_EVENING
    if program == "crossing":
        return EVENING_TRAINING_TYPE_CROSSING
    return None


def program_for_evening_training_type(training_type: str) -> Optional[str]:
    training_type = str(training_type or "").strip()
    if training_type == EVENING_TRAINING_TYPE_CROSSING:
        return "crossing"
    if training_type == EVENING_TRAINING_TYPE_EVENING:
        return "evening"
    return None


def is_evening_split_program(program: str) -> bool:
    return evening_training_type_for_program(program) is not None


def filter_evening_trainee_queryset_by_program(qs: QuerySet, program: str) -> QuerySet:
    """فلتر متكوني جدول مسائي_ومعابر حسب الزر الذي دخل منه المستخدم."""
    training_type = evening_training_type_for_program(program)
    if not training_type:
        return qs
    return qs.filter(نوع_التكوين=training_type)


def evening_trainee_ids_for_program(program: str):
    """QuerySet IDs لمتكوني المسائي/المعابر حسب البرنامج."""
    from .models import مسائي_ومعابر

    training_type = evening_training_type_for_program(program)
    if not training_type:
        return مسائي_ومعابر.objects.none().values_list("pk", flat=True)
    return مسائي_ومعابر.objects.filter(نوع_التكوين=training_type).values_list("pk", flat=True)


def evening_trainee_content_type():
    from .models import مسائي_ومعابر

    return ContentType.objects.get_for_model(مسائي_ومعابر)


def filter_generic_records_queryset_by_program(
    qs: QuerySet,
    program: str,
    *,
    content_type_field: str = "trainee_content_type",
    object_id_field: str = "trainee_object_id",
) -> QuerySet:
    """فلتر سجلات الوثائق المرتبطة بـ GenericForeignKey حسب نوع المسائي/المعابر.

    يستعمل في: الإعذارات، مقرر الفصل، العقوبات، الاستدعاءات.
    هذا يمنع ظهور سجل معابر داخل صفحة الدروس المسائية حتى لو كان حقل program قديمًا أو مختلطًا.
    """
    if not is_evening_split_program(program):
        return qs
    try:
        return qs.filter(
            **{
                content_type_field: evening_trainee_content_type(),
                f"{object_id_field}__in": evening_trainee_ids_for_program(program),
            }
        )
    except Exception:
        # لا نكسر الصفحة إذا كان QuerySet لا يملك هذه الحقول.
        return qs


def filter_records_by_split_program(
    qs: QuerySet,
    program: str,
    *,
    program_field: str = "program",
    content_type_field: str = "trainee_content_type",
    object_id_field: str = "trainee_object_id",
) -> QuerySet:
    """فلتر سجلات الوثائق حسب النمط مع دعم السجلات القديمة قبل فصل المعابر.

    إذا كانت الصفحة هي الدروس المسائية أو المعابر، نبحث في سجلات evening/crossing معًا،
    ثم نفلتر فعليًا حسب نوع المتكون المرتبط. هذا يمنع اختفاء السجلات القديمة
    التي كانت محفوظة كلها تحت program=evening قبل الفصل.
    """
    if is_evening_split_program(program):
        qs = qs.filter(**{f"{program_field}__in": list(EVENING_SPLIT_PROGRAMS)})
    else:
        qs = qs.filter(**{program_field: program})
    return filter_generic_records_queryset_by_program(
        qs,
        program,
        content_type_field=content_type_field,
        object_id_field=object_id_field,
    )


def trainee_matches_program(trainee, program: str) -> bool:
    training_type = evening_training_type_for_program(program)
    if not training_type:
        return True
    return str(getattr(trainee, "نوع_التكوين", "") or "").strip() == training_type
