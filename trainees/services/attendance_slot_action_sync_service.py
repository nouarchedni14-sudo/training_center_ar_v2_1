from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from trainees.attendance_slots_common import SLOT_COUNT_PER_DAY
from trainees.attendance_slots_models import AttendanceSlotCell
from trainees.models import AttendanceAction, AttendanceActionDeletion, SummonsRecord
from trainees.services.attendance_action_sync_service import (
    attendance_action_trainee_address,
    next_attendance_document_number,
)


# -----------------------------------------------------------------------------
# قواعد حساب إعذارات الغياب بالحصة
# -----------------------------------------------------------------------------
# القاعدة القديمة التي تبقى مفعلة:
# 3 أيام غياب كاملة = 3 × 4 حصص = 12 حصة => الإعذار الأول
FULL_ABSENT_DAYS_PER_EXCUSE = 3
SLOTS_PER_EXCUSE = FULL_ABSENT_DAYS_PER_EXCUSE * SLOT_COUNT_PER_DAY

# القاعدة الذكية المصححة:
# اليوم الذي فيه 3 حصص أو 4 حصص غياب يعتبر يوماً ثقيلاً/شبه كامل.
# لا نرفع المتكون إلى الإعذار الثاني أو الثالث بمجرد تتابع الأيام.
# كل 3 أيام ثقيلة = إعذار واحد:
#   3 أيام ثقيلة => الإعذار الأول
#   6 أيام ثقيلة => الإعذار الثاني
#   9 أيام ثقيلة => الإعذار الثالث
SMART_MIN_ABSENT_SLOTS_PER_DAY = max(3, SLOT_COUNT_PER_DAY - 1)
SMART_DAYS_PER_EXCUSE = 3
SMART_SLOTS_PER_EXCUSE = SMART_MIN_ABSENT_SLOTS_PER_DAY * SMART_DAYS_PER_EXCUSE
SMART_MAX_EXCUSE_RANK = 3

# استدعاء الغيابات المتذبذبة/المتكررة:
# 1) غيابات جزئية خفيفة: حصة أو حصتان في اليوم، وإذا وصل مجموعها إلى 6 حصص أو أكثر.
# 2) تكرار يوم شبه كامل بعد فاصل لا يقل عن 3 أيام، بشرط ألا يكون اليوم الدراسي التالي مباشرة.
INTERMITTENT_MIN_ABSENT_SLOTS = 6
REPEATED_HEAVY_MIN_CALENDAR_GAP_DAYS = 3
REPEATED_HEAVY_MIN_STUDY_GAP_DAYS = 3

ACTION_RANKS = {"excuse_1": 1, "excuse_2": 2, "excuse_3": 3}
ACTION_TYPES_BY_RANK = ["excuse_1", "excuse_2", "excuse_3"]
AUTO_ARCHIVE_MARK = "[أرشفة آلية مؤقتة من نظام الحصص]"
MANUAL_ARCHIVE_MARK = "[أرشفة يدوية]"


@dataclass
class SlotDayAbsence:
    entry_date: date
    study_index: int
    absent_slots: int
    absent_slot_numbers: list[int] = field(default_factory=list)

    @property
    def is_full_day(self) -> bool:
        return self.absent_slots >= SLOT_COUNT_PER_DAY

    @property
    def is_smart_excuse_day(self) -> bool:
        return self.absent_slots >= SMART_MIN_ABSENT_SLOTS_PER_DAY


@dataclass
class SlotAbsenceSummary:
    trainee: object
    full_absent_days: int = 0
    full_absent_slots: int = 0

    # partial_absent_* تبقى للتوافق مع القراءة القديمة: أي يوم أقل من 4 حصص.
    partial_absent_days: int = 0
    partial_absent_slots: int = 0

    # light_partial_absent_* هي التي تدخل في استدعاء الغيابات المتذبذبة العادية:
    # حصة أو حصتان فقط في اليوم، حتى لا نخلطها مع قاعدة 3 حصص = إعذار.
    light_partial_absent_days: int = 0
    light_partial_absent_slots: int = 0

    smart_excuse_days: int = 0
    smart_excuse_slots: int = 0
    max_smart_consecutive_days: int = 0
    repeated_heavy_gap_count: int = 0

    first_absence_date: date | None = None
    first_full_absence_date: date | None = None
    first_partial_absence_date: date | None = None
    first_light_partial_absence_date: date | None = None
    first_smart_absence_date: date | None = None
    first_repeated_heavy_gap_date: date | None = None

    day_absences: list[SlotDayAbsence] = field(default_factory=list)

    @property
    def total_absent_slots(self) -> int:
        return self.full_absent_slots + self.partial_absent_slots

    @property
    def smart_due_rank(self) -> int:
        # القاعدة المصححة: لا نعتبر كل يوم ثقيل إعذاراً مستقلاً.
        # 3 أيام ثقيلة = الإعذار الأول، 6 أيام = الثاني، 9 أيام = الثالث.
        return min(int(self.smart_excuse_days or 0) // SMART_DAYS_PER_EXCUSE, SMART_MAX_EXCUSE_RANK)

    @property
    def full_due_rank(self) -> int:
        return min(int(self.full_absent_days or 0) // FULL_ABSENT_DAYS_PER_EXCUSE, SMART_MAX_EXCUSE_RANK)

    @property
    def due_rank(self) -> int:
        return max(self.smart_due_rank, self.full_due_rank)

    @property
    def has_repeated_heavy_gap(self) -> bool:
        return bool(self.repeated_heavy_gap_count)


def _action_types_for_rank(rank: int) -> list[str]:
    rank = max(0, min(int(rank or 0), SMART_MAX_EXCUSE_RANK))
    return ACTION_TYPES_BY_RANK[:rank]


def _action_type_for_full_days(full_absent_days: int) -> list[str]:
    """توافق مع الاسم القديم: يرجع الإعذارات حسب الأيام الكاملة فقط."""
    rank = min(int(full_absent_days or 0) // FULL_ABSENT_DAYS_PER_EXCUSE, SMART_MAX_EXCUSE_RANK)
    return _action_types_for_rank(rank)


def _action_types_for_summary(summary: SlotAbsenceSummary) -> list[str]:
    """يرجع الإعذارات المستحقة حسب القاعدتين: القديمة والذكية."""
    return _action_types_for_rank(summary.due_rank)


def _safe_trainee_name(trainee) -> str:
    full = (getattr(trainee, "اللقب_والاسم", "") or "").strip()
    if full:
        return full
    return f"{getattr(trainee, 'اللقب', '')} {getattr(trainee, 'الاسم', '')}".strip() or str(trainee)


def _auto_note_filter(qs):
    """نحصر التحديث/الأرشفة في السجلات التي أنشأها نظام الحصص الجديد فقط."""
    return qs.filter(notes__icontains="جدول الغياب بالحصة")


def _append_note_marker(notes: str, marker: str) -> str:
    notes = (notes or "").strip()
    if marker in notes:
        return notes
    return (notes + "\n" + marker).strip() if notes else marker


def _remove_note_marker(notes: str, marker: str) -> str:
    lines = [line.strip() for line in (notes or "").splitlines() if line.strip() and line.strip() != marker]
    return "\n".join(lines).strip()


def _is_manual_archived(obj) -> bool:
    return MANUAL_ARCHIVE_MARK in (obj.notes or "")


def _is_auto_archived(obj) -> bool:
    return AUTO_ARCHIVE_MARK in (obj.notes or "")


def _archive_auto_excuses(scope_qs, user) -> int:
    archived = 0
    for obj in _auto_note_filter(scope_qs).filter(is_archived=False):
        obj.is_archived = True
        obj.archived_at = timezone.now()
        obj.notes = _append_note_marker(obj.notes, AUTO_ARCHIVE_MARK)
        obj.updated_by = user if getattr(user, "is_authenticated", False) else obj.updated_by
        obj.save(update_fields=["is_archived", "archived_at", "notes", "updated_by", "updated_at"])
        archived += 1
    return archived


def _cancel_auto_intermittent_summons(program: str, trainee_ct, trainee_pk: int, user) -> int:
    updated = 0
    qs = SummonsRecord.objects.filter(
        program=program,
        summons_scope="current",
        summons_type="intermittent_absence",
        trainee_content_type=trainee_ct,
        trainee_object_id=trainee_pk,
        notes__icontains="جدول الغياب بالحصة",
    ).exclude(status__in=["cancelled", "issued", "delivered"])
    for obj in qs:
        obj.status = "cancelled"
        obj.updated_by = user if getattr(user, "is_authenticated", False) else obj.updated_by
        obj.notes = (obj.notes or "").strip() + "\nتم إلغاء هذا الاستدعاء آليًا لأن الغيابات لم تعد تحقق شرط التسجيل."
        obj.save(update_fields=["status", "notes", "updated_by", "updated_at"])
        updated += 1
    return updated


def _mark_smart_sequences(summary: SlotAbsenceSummary) -> None:
    """حساب أطول تسلسل للمراقبة فقط، وحساب التكرار بعد فاصل.

    مهم: أطول تسلسل لا يحدد رقم الإعذار. رقم الإعذار يحدد بعدد الأيام
    الثقيلة: كل 3 أيام ثقيلة = مرحلة واحدة فقط.
    """
    heavy_days = [item for item in summary.day_absences if item.is_smart_excuse_day]
    if not heavy_days:
        return

    current_streak = 0
    previous: SlotDayAbsence | None = None

    for item in heavy_days:
        if previous is None:
            current_streak = 1
        elif item.study_index == previous.study_index + 1:
            # اليوم الدراسي التالي مباشرة. نحسبه كتسلسل للمراقبة فقط،
            # ولا يعني هذا أن الإعذار يرتفع مباشرة من الأول إلى الثاني/الثالث.
            current_streak += 1
        else:
            # ليس اليوم الدراسي التالي مباشرة. إذا عاد بعد فاصل 3 أيام أو أكثر
            # نعتبرها غيابات متكررة/متذبذبة لا إعذاراً ثانياً مباشراً.
            calendar_gap = (item.entry_date - previous.entry_date).days
            study_gap = max(item.study_index - previous.study_index - 1, 0)
            if calendar_gap >= REPEATED_HEAVY_MIN_CALENDAR_GAP_DAYS or study_gap >= REPEATED_HEAVY_MIN_STUDY_GAP_DAYS:
                summary.repeated_heavy_gap_count += 1
                if summary.first_repeated_heavy_gap_date is None:
                    summary.first_repeated_heavy_gap_date = summary.first_smart_absence_date or previous.entry_date
            current_streak = 1

        summary.max_smart_consecutive_days = max(summary.max_smart_consecutive_days, current_streak)
        previous = item


def _build_absence_summaries(payload: dict) -> list[SlotAbsenceSummary]:
    sheet = payload.get("sheet")
    rows = payload.get("rows") or []
    columns = payload.get("columns") or []
    if not sheet or not rows or not columns:
        return []

    trainees_by_id = {row["trainee"].pk: row["trainee"] for row in rows}
    ordered_dates = [col["date"] for col in sorted(columns, key=lambda c: c["date"])]
    date_order = {entry_date: index for index, entry_date in enumerate(ordered_dates)}
    trainee_ids = list(trainees_by_id.keys())

    absent_by_trainee_day: dict[int, dict[date, list[int]]] = defaultdict(lambda: defaultdict(list))
    entries = AttendanceSlotCell.objects.filter(
        الكشف=sheet,
        trainee_id__in=trainee_ids,
        التاريخ__in=ordered_dates,
        الحالة="absent",
    ).values_list("trainee_id", "التاريخ", "رقم_الحصة")

    for trainee_id, entry_date, slot_no in entries:
        try:
            absent_by_trainee_day[int(trainee_id)][entry_date].append(int(slot_no or 0))
        except (TypeError, ValueError):
            absent_by_trainee_day[int(trainee_id)][entry_date].append(0)

    summaries: list[SlotAbsenceSummary] = []
    for trainee_id, trainee in trainees_by_id.items():
        summary = SlotAbsenceSummary(trainee=trainee)
        for entry_date in sorted(absent_by_trainee_day.get(trainee_id, {}).keys()):
            slot_numbers = sorted({int(v) for v in absent_by_trainee_day[trainee_id][entry_date] if int(v or 0) > 0})
            absent_slots = len(slot_numbers)
            if absent_slots <= 0:
                continue

            if summary.first_absence_date is None:
                summary.first_absence_date = entry_date

            day_item = SlotDayAbsence(
                entry_date=entry_date,
                study_index=date_order.get(entry_date, 0),
                absent_slots=absent_slots,
                absent_slot_numbers=slot_numbers,
            )
            summary.day_absences.append(day_item)

            if day_item.is_full_day:
                summary.full_absent_days += 1
                summary.full_absent_slots += SLOT_COUNT_PER_DAY
                if summary.first_full_absence_date is None:
                    summary.first_full_absence_date = entry_date
            else:
                summary.partial_absent_days += 1
                summary.partial_absent_slots += absent_slots
                if summary.first_partial_absence_date is None:
                    summary.first_partial_absence_date = entry_date

            if day_item.is_smart_excuse_day:
                summary.smart_excuse_days += 1
                summary.smart_excuse_slots += absent_slots
                if summary.first_smart_absence_date is None:
                    summary.first_smart_absence_date = entry_date
            else:
                # هنا نحسب فقط حصة أو حصتين في اليوم للاستدعاء المتذبذب العادي.
                summary.light_partial_absent_days += 1
                summary.light_partial_absent_slots += absent_slots
                if summary.first_light_partial_absence_date is None:
                    summary.first_light_partial_absence_date = entry_date

        _mark_smart_sequences(summary)
        summaries.append(summary)
    return summaries


def _slot_action_deletion_exists(program: str, scope: dict, batch, specialty: str, trainee_ct, trainee_pk: int, action_type: str) -> bool:
    return AttendanceActionDeletion.objects.filter(
        source="slots",
        program=program,
        month=scope.get("month"),
        year=scope.get("year"),
        batch=batch,
        specialty=specialty,
        trainee_content_type=trainee_ct,
        trainee_object_id=trainee_pk,
        action_type=action_type,
    ).exists()


def _clear_slot_action_deletions_for_trainee(program: str, scope: dict, batch, specialty: str, trainee_ct, trainee_pk: int) -> int:
    """
    يحذف آثار الحذف القديمة فقط عندما لا تبقى أي غيابات مستحقة للمتكون.

    الفكرة:
    - إذا حذف المستخدم الإعذار مباشرة أو حذفه من الأرشيف والغيابات مازالت موجودة،
      يجب ألا تعيد المزامنة إنشاءه في نفس اللحظة. لذلك نحترم سجل الحذف.
    - إذا مسح المستخدم الغيابات من الجدول ثم حفظ، فهذا يعني بداية تجربة جديدة.
      عندها نحذف سجل الحذف حتى يمكن إنشاء الإعذار من جديد عند إعادة إدخال الغيابات.
    """
    deleted, _ = AttendanceActionDeletion.objects.filter(
        source="slots",
        program=program,
        month=scope.get("month"),
        year=scope.get("year"),
        batch=batch,
        specialty=specialty,
        trainee_content_type=trainee_ct,
        trainee_object_id=trainee_pk,
    ).delete()
    return deleted


def _excuse_trigger_for_action(summary: SlotAbsenceSummary, action_type: str) -> tuple[int, int]:
    """يرجع (عدد الغيابات المحتسبة، العتبة المعتمدة) لكل إعذار."""
    rank = ACTION_RANKS.get(action_type, 0)
    if rank <= summary.smart_due_rank:
        # نعرض العدد الحقيقي للحصص الثقيلة المحتسبة، مع ضمان ألا يقل عن عتبة المرحلة.
        counted_slots = max(summary.smart_excuse_slots, SMART_SLOTS_PER_EXCUSE * rank)
        return counted_slots, SMART_SLOTS_PER_EXCUSE
    counted_slots = max(summary.full_absent_slots, SLOTS_PER_EXCUSE * rank)
    return counted_slots, SLOTS_PER_EXCUSE


def _excuse_absence_start_date(summary: SlotAbsenceSummary) -> date | None:
    if summary.smart_due_rank:
        return summary.first_smart_absence_date or summary.first_absence_date
    return summary.first_full_absence_date or summary.first_absence_date


def _action_rank_label(rank: int) -> str:
    return {1: "الأول", 2: "الثاني", 3: "الثالث"}.get(int(rank or 0), str(rank or ""))


def _reason_for_action(summary: SlotAbsenceSummary, action_type: str) -> str:
    rank = ACTION_RANKS.get(action_type, 0)
    if not rank:
        return "إجراء آلي من جدول الغياب بالحصة."

    heavy_days_threshold = SMART_DAYS_PER_EXCUSE * rank
    full_days_threshold = FULL_ABSENT_DAYS_PER_EXCUSE * rank

    if summary.full_due_rank >= rank and summary.full_absent_days >= full_days_threshold:
        return (
            f"الإعذار {_action_rank_label(rank)} بسبب بلوغ {full_days_threshold} أيام غياب كاملة "
            f"({SLOT_COUNT_PER_DAY} حصص في كل يوم)."
        )
    if summary.smart_due_rank >= rank:
        return (
            f"الإعذار {_action_rank_label(rank)} بسبب بلوغ {heavy_days_threshold} أيام غياب ثقيلة "
            f"({SMART_MIN_ABSENT_SLOTS_PER_DAY} حصص أو أكثر في كل يوم)."
        )
    return f"الإعذار {_action_rank_label(rank)} حسب مجموع الغيابات المسجلة بالحصة."


def _format_day_slot_numbers(item: SlotDayAbsence) -> str:
    if not item.absent_slot_numbers:
        return "غير محددة"
    return "، ".join(f"ح{slot_no}" for slot_no in item.absent_slot_numbers)


def _format_absence_day_details(summary: SlotAbsenceSummary) -> list[str]:
    lines: list[str] = []
    for item in summary.day_absences:
        if item.is_full_day:
            kind = "يوم كامل"
        elif item.is_smart_excuse_day:
            kind = "يوم ثقيل"
        else:
            kind = "غياب جزئي"
        lines.append(
            f"- {item.entry_date.strftime('%Y-%m-%d')}: {item.absent_slots} حصة/حصص غياب "
            f"({ _format_day_slot_numbers(item) }) - {kind}"
        )
    return lines


def _excuse_note(summary: SlotAbsenceSummary, action_type: str = "") -> str:
    parts = [
        "تسجيل آلي من جدول الغياب بالحصة.",
        f"سبب الإنشاء: {_reason_for_action(summary, action_type)}",
        f"القاعدة المعتمدة: كل {SMART_DAYS_PER_EXCUSE} أيام يكون في كل يوم منها {SMART_MIN_ABSENT_SLOTS_PER_DAY} حصص غياب أو أكثر = إعذار واحد فقط.",
        f"ملخص الغيابات الثقيلة: {summary.smart_excuse_days} يوم/أيام = {summary.smart_excuse_slots} حصة.",
        f"ملخص الأيام الكاملة: {summary.full_absent_days} يوم/أيام = {summary.full_absent_slots} حصة.",
        f"الغيابات الجزئية الخفيفة: {summary.light_partial_absent_days} يوم/أيام = {summary.light_partial_absent_slots} حصة.",
        f"أطول تسلسل متتابع للمراقبة فقط: {summary.max_smart_consecutive_days} يوم/أيام.",
        "تفاصيل الغيابات المحتسبة:",
    ]
    detail_lines = _format_absence_day_details(summary)
    if detail_lines:
        parts.extend(detail_lines)
    else:
        parts.append("- لا توجد تفاصيل غياب محفوظة لهذا النطاق.")
    if summary.has_repeated_heavy_gap:
        parts.append("ملاحظة: يوجد تكرار لغياب شبه كامل بعد فاصل؛ يعالج أيضًا ضمن استدعاء الغيابات المتكررة.")
    return "\n".join(parts)


def _sync_excuses_for_summary(program: str, scope: dict, batch, specialty: str, trainee_ct, summary: SlotAbsenceSummary, user) -> tuple[int, int, int]:
    created = updated = archived = 0
    trainee = summary.trainee
    scope_qs = AttendanceAction.objects.filter(
        source="slots",
        program=program,
        month=scope.get("month"),
        year=scope.get("year"),
        batch=batch,
        specialty=specialty,
        trainee_content_type=trainee_ct,
        trainee_object_id=trainee.pk,
    )

    due_action_types = _action_types_for_summary(summary)
    if not due_action_types:
        archived += _archive_auto_excuses(scope_qs, user)
        # عند حذف/مسح الغيابات وحفظ الجدول لا تبقى أي إعذارات مستحقة.
        # هنا نمسح سجل الحذف حتى إذا أعاد المستخدم إدخال الغيابات لاحقًا
        # يبدأ النظام تجربة جديدة وينشئ الإعذارات من جديد.
        _clear_slot_action_deletions_for_trainee(
            program, scope, batch, specialty, trainee_ct, trainee.pk
        )
        return created, updated, archived

    due_set = set(due_action_types)

    for action_type in due_action_types:
        # مهم جدًا:
        # إذا حذف المستخدم الإعذار مباشرة أو حذفه من الأرشيف والغيابات مازالت موجودة،
        # لا نعيد إنشاءه تلقائيًا عند فتح الصفحة أو عند المزامنة.
        # أما إذا مسح الغيابات ثم حفظ، فالدالة أعلاه تمسح سجل الحذف،
        # وبالتالي يمكن إنشاء الإعذار من جديد عند إعادة التجربة.
        if _slot_action_deletion_exists(
            program, scope, batch, specialty, trainee_ct, trainee.pk, action_type
        ):
            continue

        trigger_count, threshold_value = _excuse_trigger_for_action(summary, action_type)
        defaults = {
            "trainee_name": _safe_trainee_name(trainee),
            "trainee_specialty": getattr(trainee, "التخصص", "") or "",
            "trainee_address": attendance_action_trainee_address(trainee),
            "trigger_count": trigger_count,
            "threshold_value": threshold_value,
            "absence_start_date": _excuse_absence_start_date(summary),
            "document_number": next_attendance_document_number(scope.get("year")),
            "notes": _excuse_note(summary, action_type),
            "created_by": user if getattr(user, "is_authenticated", False) else None,
            "updated_by": user if getattr(user, "is_authenticated", False) else None,
        }
        obj, was_created = AttendanceAction.objects.get_or_create(
            source="slots",
            program=program,
            month=scope.get("month"),
            year=scope.get("year"),
            batch=batch,
            specialty=specialty,
            trainee_content_type=trainee_ct,
            trainee_object_id=trainee.pk,
            action_type=action_type,
            defaults=defaults,
        )
        if was_created:
            created += 1
            continue

        dirty_fields: list[str] = []
        was_manual_archived = obj.is_archived and _is_manual_archived(obj)
        notes_value = _append_note_marker(defaults["notes"], MANUAL_ARCHIVE_MARK) if was_manual_archived else defaults["notes"]
        updates = {
            "trigger_count": defaults["trigger_count"],
            "threshold_value": defaults["threshold_value"],
            "trainee_name": defaults["trainee_name"],
            "trainee_specialty": defaults["trainee_specialty"],
            "trainee_address": defaults["trainee_address"],
            "absence_start_date": defaults["absence_start_date"] or obj.absence_start_date,
            "notes": notes_value,
        }
        for field_name, value in updates.items():
            if value is not None and getattr(obj, field_name) != value:
                setattr(obj, field_name, value)
                dirty_fields.append(field_name)
        if not obj.document_number:
            obj.document_number = next_attendance_document_number(obj.year)
            dirty_fields.append("document_number")
        # إذا كان السجل مؤرشفًا آليًا فقط بسبب حذف/نقصان الغيابات،
        # ثم عادت الغيابات وأصبحت مستحقة من جديد، نعيده إلى الجدول النشط تلقائيًا.
        # أما الأرشفة اليدوية فتظل مخفية إلى أن يضغط المستخدم زر استرجاع.
        if obj.is_archived and not was_manual_archived:
            obj.is_archived = False
            obj.archived_at = None
            obj.notes = _remove_note_marker(obj.notes, AUTO_ARCHIVE_MARK)
            dirty_fields += ["is_archived", "archived_at", "notes"]

        if dirty_fields:
            obj.updated_by = user if getattr(user, "is_authenticated", False) else obj.updated_by
            dirty_fields += ["updated_by", "updated_at"]
            obj.save(update_fields=sorted(set(dirty_fields)))
            updated += 1

    # السلوك الجديد المطلوب:
    # عند استحقاق الإعذار الثاني أو الثالث تبقى الإعذارات السابقة ظاهرة في الجدول
    # ولا تختفي إلا إذا أرشفها المستخدم يدوياً.
    # لذلك نؤرشف آلياً فقط المراحل التي لم تعد مستحقة إطلاقاً، ولا نؤرشف المراحل الأقل.
    for old_obj in _auto_note_filter(scope_qs):
        should_archive = old_obj.action_type not in due_set

        if should_archive and not old_obj.is_archived:
            old_obj.is_archived = True
            old_obj.archived_at = timezone.now()
            old_obj.notes = _append_note_marker(old_obj.notes, AUTO_ARCHIVE_MARK)
            old_obj.updated_by = user if getattr(user, "is_authenticated", False) else old_obj.updated_by
            old_obj.save(update_fields=["is_archived", "archived_at", "notes", "updated_by", "updated_at"])
            archived += 1

    return created, updated, archived


def _summons_reasons(summary: SlotAbsenceSummary) -> list[str]:
    reasons: list[str] = []
    if summary.light_partial_absent_slots >= INTERMITTENT_MIN_ABSENT_SLOTS:
        reasons.append(
            f"غيابات جزئية خفيفة = {summary.light_partial_absent_slots} حصة موزعة على {summary.light_partial_absent_days} يوم/أيام"
        )
    if summary.has_repeated_heavy_gap:
        reasons.append(
            f"تكرار غياب شبه كامل بعد فاصل: {summary.repeated_heavy_gap_count} مرة/مرات"
        )
    return reasons


def _summons_from_date(summary: SlotAbsenceSummary) -> date | None:
    if summary.light_partial_absent_slots >= INTERMITTENT_MIN_ABSENT_SLOTS:
        return summary.first_light_partial_absence_date or summary.first_partial_absence_date or summary.first_absence_date
    if summary.has_repeated_heavy_gap:
        return summary.first_repeated_heavy_gap_date or summary.first_smart_absence_date or summary.first_absence_date
    return summary.first_absence_date


def _sync_intermittent_summons_for_summary(program: str, specialty: str, trainee_ct, summary: SlotAbsenceSummary, user) -> tuple[int, int]:
    trainee = summary.trainee
    reasons = _summons_reasons(summary)

    # إذا لم تعد الغيابات تحقق شرط الاستدعاء، نلغي فقط الاستدعاءات التي أنشأها نظام الحصص آليًا.
    if not reasons:
        return 0, _cancel_auto_intermittent_summons(program, trainee_ct, trainee.pk, user)

    defaults = {
        "trainee_name": _safe_trainee_name(trainee),
        "registration_number": getattr(trainee, "رقم_التسجيل", "") or "",
        "address": getattr(trainee, "العنوان_بالعربية", "") or getattr(trainee, "ولاية_الإقامة_بالعربية", "") or "",
        "specialty": getattr(trainee, "التخصص", "") or specialty or "",
        "group_code": getattr(trainee, "رمز_التخصص", "") or "",
        "semester": getattr(trainee, "السداسي", "") or "",
        "issue_date": timezone.localdate(),
        "from_date": _summons_from_date(summary),
        "notes": "تسجيل آلي من جدول الغياب بالحصة: " + "؛ ".join(reasons) + ".",
        "created_by": user if getattr(user, "is_authenticated", False) else None,
        "updated_by": user if getattr(user, "is_authenticated", False) else None,
    }
    obj, was_created = SummonsRecord.objects.get_or_create(
        program=program,
        summons_scope="current",
        summons_type="intermittent_absence",
        trainee_content_type=trainee_ct,
        trainee_object_id=trainee.pk,
        defaults=defaults,
    )
    if was_created:
        return 1, 0

    dirty_fields: list[str] = []
    if obj.status == "cancelled":
        obj.status = "draft"
        dirty_fields.append("status")
    for field_name in ["trainee_name", "registration_number", "address", "specialty", "group_code", "semester", "from_date", "notes"]:
        value = defaults[field_name]
        if value and getattr(obj, field_name) != value:
            setattr(obj, field_name, value)
            dirty_fields.append(field_name)
    if not obj.issue_date:
        obj.issue_date = timezone.localdate()
        dirty_fields.append("issue_date")
    if dirty_fields:
        obj.updated_by = user if getattr(user, "is_authenticated", False) else obj.updated_by
        dirty_fields += ["updated_by", "updated_at"]
        obj.save(update_fields=sorted(set(dirty_fields)))
        return 0, 1
    return 0, 0


def sync_slot_attendance_actions(program: str, payload: dict, user) -> dict:
    """Create/update excuses and intermittent-absence summons from the 4-slot table.

    القاعدة النهائية المصححة:
    - 4 حصص في نفس اليوم = يوم غياب كامل.
    - 3 حصص أو أكثر في نفس اليوم = يوم غياب ثقيل/شبه كامل.
    - كل 3 أيام ثقيلة فقط = الإعذار الأول، ولا يتم القفز إلى الثالث مباشرة.
    - كل 6 أيام ثقيلة = الإعذار الثاني.
    - كل 9 أيام ثقيلة = الإعذار الثالث.
    - إذا عاد لنفس السلوك بعد فاصل 3 أيام أو أكثر، يسجل أيضاً ضمن استدعاء الغيابات المتكررة/المتذبذبة عند الحاجة.
    - حصة أو حصتان في اليوم تدخل في الغيابات الجزئية، وإذا بلغ مجموعها 6 حصص أو أكثر يسجل استدعاء الغيابات المتذبذبة.
    - القاعدة القديمة للأيام الكاملة تبقى مفعلة ومندمجة مع القاعدة الجديدة: كل 3 أيام كاملة = إعذار.
    - إذا حُذف الإعذار مباشرة أو من الأرشيف والغيابات مازالت موجودة، لا يعاد إنشاؤه فوراً.
    - إذا مُسحت الغيابات ثم حُفظ الجدول ثم أُعيدت التجربة، تعود الإعذارات الآلية للظهور من جديد.
    """
    sheet = payload.get("sheet")
    scope = payload.get("scope") or {}
    if not sheet:
        return {
            "created_excuses": 0,
            "updated_excuses": 0,
            "archived_excuses": 0,
            "created_summons": 0,
            "updated_summons": 0,
            "checked": 0,
        }

    batch = scope.get("promotion") or getattr(sheet, "الدفعة", None)
    specialty = (getattr(sheet, "التخصص", "") or scope.get("specialty") or "").strip()
    summaries = _build_absence_summaries(payload)

    totals = {
        "created_excuses": 0,
        "updated_excuses": 0,
        "archived_excuses": 0,
        "created_summons": 0,
        "updated_summons": 0,
        "checked": len(summaries),
    }

    with transaction.atomic():
        for summary in summaries:
            trainee = summary.trainee
            trainee_ct = ContentType.objects.get_for_model(trainee.__class__)
            c, u, a = _sync_excuses_for_summary(program, scope, batch, specialty, trainee_ct, summary, user)
            totals["created_excuses"] += c
            totals["updated_excuses"] += u
            totals["archived_excuses"] += a
            sc, su = _sync_intermittent_summons_for_summary(program, specialty, trainee_ct, summary, user)
            totals["created_summons"] += sc
            totals["updated_summons"] += su
    return totals
