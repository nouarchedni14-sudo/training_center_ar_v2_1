from __future__ import annotations

from typing import Iterable

from trainees.models import خليةغياب

VALID_ATTENDANCE_STATUSES = {"present", "absent", "excused", "late"}


def normalize_attendance_status(raw_status: str) -> str:
    raw_status = (raw_status or "").strip()
    if not raw_status:
        return ""
    return raw_status if raw_status in VALID_ATTENDANCE_STATUSES else "present"


def existing_attendance_entries(program, sheet, trainee_ids: Iterable[int], column_dates):
    qs = خليةغياب.objects.filter(
        الكشف=sheet,
        trainee_id__in=list(trainee_ids),
        التاريخ__in=list(column_dates),
    )
    if program == "apprentice":
        return {
            (entry.trainee_id, entry.التاريخ.isoformat(), entry.رقم_الخانة): entry
            for entry in qs
        }
    return {
        (entry.trainee_id, entry.التاريخ.isoformat()): entry
        for entry in qs
    }


def delete_saved_attendance_entries(sheet, trainee_ids: Iterable[int], column_dates):
    deleted_count, _ = خليةغياب.objects.filter(
        الكشف=sheet,
        trainee_id__in=list(trainee_ids),
        التاريخ__in=list(column_dates),
    ).delete()
    return deleted_count


def build_attendance_changes(program, rows, post_data, sheet, user, existing_entries):
    to_create = []
    to_update = []
    to_delete_ids = []

    for row in rows:
        trainee = row["trainee"]
        for cell in row["cells"]:
            if program == "apprentice":
                for slot in cell.get("slots", []):
                    slot_no = int(slot.get("slot") or 1)
                    raw_status = (post_data.get(f"status__{trainee.pk}__{cell['iso']}__{slot_no}") or "").strip()
                    entry = existing_entries.get((trainee.pk, cell["iso"], slot_no))
                    _apply_attendance_change(
                        to_create=to_create,
                        to_update=to_update,
                        to_delete_ids=to_delete_ids,
                        sheet=sheet,
                        trainee=trainee,
                        cell=cell,
                        entry=entry,
                        raw_status=raw_status,
                        user=user,
                        slot_no=slot_no,
                    )
            else:
                raw_status = (post_data.get(f"status__{trainee.pk}__{cell['iso']}") or "").strip()
                entry = existing_entries.get((trainee.pk, cell["iso"]))
                _apply_attendance_change(
                    to_create=to_create,
                    to_update=to_update,
                    to_delete_ids=to_delete_ids,
                    sheet=sheet,
                    trainee=trainee,
                    cell=cell,
                    entry=entry,
                    raw_status=raw_status,
                    user=user,
                    slot_no=None,
                )

    return {
        "to_create": to_create,
        "to_update": to_update,
        "to_delete_ids": to_delete_ids,
        "saved": len(to_create) + len(to_update),
    }


def _apply_attendance_change(*, to_create, to_update, to_delete_ids, sheet, trainee, cell, entry, raw_status, user, slot_no):
    if raw_status == "":
        if entry is not None:
            to_delete_ids.append(entry.pk)
        return

    status = normalize_attendance_status(raw_status)
    note = ""

    if entry is None:
        kwargs = {
            "الكشف": sheet,
            "trainee_id": trainee.pk,
            "التاريخ": cell["date"],
            "الحالة": status,
            "ملاحظة": note,
            "recorded_by": user,
        }
        if slot_no is not None:
            kwargs["رقم_الخانة"] = slot_no
        to_create.append(خليةغياب(**kwargs))
        return

    if entry.الحالة != status or entry.ملاحظة != note or entry.recorded_by_id != user.id:
        entry.الحالة = status
        entry.ملاحظة = note
        entry.recorded_by = user
        to_update.append(entry)


def persist_attendance_changes(*, to_delete_ids, to_create, to_update):
    if to_delete_ids:
        خليةغياب.objects.filter(pk__in=to_delete_ids).delete()
    if to_create:
        خليةغياب.objects.bulk_create(to_create, batch_size=1000)
    if to_update:
        خليةغياب.objects.bulk_update(
            to_update,
            ["الحالة", "ملاحظة", "recorded_by", "updated_at"],
            batch_size=1000,
        )
