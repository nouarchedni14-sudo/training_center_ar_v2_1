# Generated to create/number dismissal decisions for existing removed trainees.
from datetime import date
import re

from django.db import migrations


PROGRAM_MODELS = [
    ("initial", "حضوري_أولي"),
    ("apprentice", "تمهين"),
    ("evening", "مسائي_ومعابر"),
]

REMOVED_WORDS = (
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


def _is_removed(value):
    text = str(value or "").strip()
    if not text:
        return False
    return any(word in text for word in REMOVED_WORDS)


def _scope_for_trainee(row):
    end_date = getattr(row, "تاريخ_نهاية_التكوين", None)
    if end_date and end_date <= date.today():
        return "graduated"
    return "current"


def _full_name(row):
    last = str(getattr(row, "اللقب", "") or "").strip()
    first = str(getattr(row, "الاسم", "") or "").strip()
    return " ".join([p for p in (last, first) if p]).strip() or str(row.pk)


def _birth_place(row):
    town = str(getattr(row, "البلدية", "") or "").strip()
    state = str(getattr(row, "الولاية", "") or "").strip()
    return " / ".join([p for p in (town, state) if p]).strip()


def _next_decision_number(DismissalDecision, target_year):
    qs = DismissalDecision.objects.filter(
        decision_date__year=target_year
    ) | DismissalDecision.objects.filter(
        disciplinary_record_date__year=target_year
    ) | DismissalDecision.objects.filter(
        dismissal_start_date__year=target_year
    )
    max_num = 0
    max_width = 0
    for raw in qs.values_list("decision_number", flat=True):
        text = str(raw or "").strip()
        if not text:
            continue
        match = re.fullmatch(r"0*(\d+)", text)
        if not match:
            continue
        num = int(match.group(1))
        if num > max_num:
            max_num = num
            max_width = len(text) if text.startswith("0") else 0
    next_num = max_num + 1
    return str(next_num).zfill(max_width) if max_width > 1 else str(next_num)


def _snapshot_defaults(row, program, scope, ct, record_number, removal_date, decision_number):
    return {
        "program": program,
        "decision_scope": scope,
        "trainee_content_type": ct,
        "trainee_object_id": row.pk,
        "trainee_name": _full_name(row),
        "birth_date": getattr(row, "تاريخ_الميلاد", None),
        "birth_place": _birth_place(row),
        "registration_number": str(getattr(row, "رقم_التسجيل", "") or "").strip(),
        "specialty": str(getattr(row, "التخصص", "") or "").strip(),
        "training_start_date": getattr(row, "تاريخ_بداية_التكوين", None),
        "training_end_date": getattr(row, "تاريخ_نهاية_التكوين", None),
        "group_code": str(getattr(row, "رمز_التخصص", "") or "").strip(),
        "semester": str(getattr(row, "السداسي", "") or "").strip(),
        "removal_date": removal_date,
        "removal_number": record_number,
        "decision_number": decision_number,
        "disciplinary_record_number": record_number,
        "disciplinary_record_date": removal_date,
        "dismissal_start_date": removal_date,
        "decision_date": removal_date,
    }


def backfill_dismissal_decisions(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    DismissalDecision = apps.get_model("trainees", "DismissalDecision")

    for program, model_name in PROGRAM_MODELS:
        TraineeModel = apps.get_model("trainees", model_name)
        ct, _ = ContentType.objects.get_or_create(
            app_label="trainees",
            model=TraineeModel._meta.model_name,
        )
        for row in TraineeModel.objects.all().iterator():
            if not _is_removed(getattr(row, "الحالة", "")):
                continue
            record_number = str(getattr(row, "رقم_الشطب", "") or "").strip()
            removal_date = getattr(row, "تاريخ_الشطب", None)
            if not record_number or not removal_date:
                continue

            scope = _scope_for_trainee(row)
            base_qs = DismissalDecision.objects.filter(
                program=program,
                trainee_content_type=ct,
                trainee_object_id=row.pk,
            )
            same_active = base_qs.filter(
                is_archived=False,
                disciplinary_record_number=record_number,
                disciplinary_record_date=removal_date,
            ).order_by("-id").first()

            # أي مقرر نشط لا يطابق تاريخ/رقم المحضر الحالي يصبح أرشيفًا، ولا نحذفه.
            for old in base_qs.filter(is_archived=False).exclude(pk=getattr(same_active, "pk", None)):
                old.is_archived = True
                old.save(update_fields=["is_archived", "updated_at"])

            decision = same_active
            if decision is None:
                decision = base_qs.filter(
                    is_archived=True,
                    disciplinary_record_number=record_number,
                    disciplinary_record_date=removal_date,
                ).order_by("-id").first()
                if decision is not None:
                    decision.is_archived = False
                    decision.archived_at = None

            imported_number = str(getattr(row, "رقم_مقرر_الفصل", "") or "").strip()
            decision_number = imported_number
            if decision is not None and str(decision.decision_number or "").strip():
                decision_number = str(decision.decision_number or "").strip()
            if not decision_number:
                decision_number = _next_decision_number(DismissalDecision, removal_date.year)

            defaults = _snapshot_defaults(row, program, scope, ct, record_number, removal_date, decision_number)
            if decision is None:
                decision = DismissalDecision(**defaults)
            else:
                for field, value in defaults.items():
                    setattr(decision, field, value)
                decision.is_archived = False
                decision.archived_at = None
            if decision.status == "draft" and decision.decision_number and decision.disciplinary_record_number and decision.disciplinary_record_date:
                decision.status = "ready"
            decision.save()

            if hasattr(row, "رقم_مقرر_الفصل") and decision_number != imported_number:
                TraineeModel.objects.filter(pk=row.pk).update(رقم_مقرر_الفصل=decision_number)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("trainees", "0051_dismissaldecision_archive"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(backfill_dismissal_decisions, noop_reverse),
    ]
