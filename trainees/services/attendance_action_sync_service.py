from collections import Counter

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from trainees.models import AttendanceAction, AttendanceActionDeletion, خليةغياب


def attendance_action_threshold(program):
    return 4 if program == "apprentice" else 5


def attendance_due_action_types(program, absent_count):
    threshold = attendance_action_threshold(program)
    due = []
    if absent_count >= threshold:
        due.append("excuse_1")
    if absent_count >= threshold * 2:
        due.append("excuse_2")
    if absent_count >= threshold * 3:
        due.append("excuse_3")
        due.append("summon")
    return due


def attendance_action_trainee_address(trainee):
    street = (getattr(trainee, "العنوان_بالعربية", "") or getattr(trainee, "العنوان_بالأجنبية", "") or "").strip()
    municipality = (getattr(trainee, "البلدية", "") or "").strip()
    wilaya = (getattr(trainee, "الولاية", "") or "").strip()
    parts = [part for part in [street, municipality, wilaya] if part]
    return " - ".join(parts)


def next_attendance_document_number(year):
    year = int(year or timezone.now().year)
    last_numeric = 0
    for value in AttendanceAction.objects.filter(year=year).exclude(document_number="").values_list("document_number", flat=True):
        raw = (value or "").strip()
        if not raw:
            continue
        first_part = raw.split("/", 1)[0].strip()
        if first_part.isdigit():
            last_numeric = max(last_numeric, int(first_part))
    return f"{last_numeric + 1:04d}"


def build_monthly_action_payload(program, scope, attendance_queryset_builder):
    model_cls, trainee_qs = attendance_queryset_builder(program, scope)
    trainees = list(trainee_qs)
    trainee_ids = [obj.pk for obj in trainees]
    absent_counts = Counter()
    first_absence_dates = {}
    if trainee_ids:
        entries = خليةغياب.objects.filter(
            الكشف__البرنامج=program,
            الكشف__السنة=scope.get("year"),
            الكشف__الشهر=scope.get("month"),
            trainee_id__in=trainee_ids,
            الحالة="absent",
        )
        visible_dates = scope.get("visible_dates") or scope.get("allowed_dates") or []
        if visible_dates:
            entries = entries.filter(التاريخ__in=visible_dates)
        if scope.get("promotion_obj"):
            entries = entries.filter(الكشف__الدفعة=scope.get("promotion_obj"))
        if scope.get("specialty"):
            entries = entries.filter(الكشف__التخصص=scope.get("specialty"))
        entries = entries.order_by("trainee_id", "التاريخ", "رقم_الخانة", "pk")
        for trainee_id, entry_date in entries.values_list("trainee_id", "التاريخ"):
            absent_counts[trainee_id] += 1
            first_absence_dates.setdefault(trainee_id, entry_date)
    return {
        "scope": scope,
        "show_all_specialties": not bool(scope.get("specialty")),
        "stats_rows": [
            {
                "trainee": trainee,
                "absent_count": absent_counts.get(trainee.pk, 0),
                "absence_start_date": first_absence_dates.get(trainee.pk),
            }
            for trainee in trainees
        ],
    }


def _attendance_action_deletion_exists(program, scope, specialty, trainee_content_type, trainee, action_type):
    return AttendanceActionDeletion.objects.filter(
        source="daily",
        program=program,
        month=scope.get("month"),
        year=scope.get("year"),
        batch=scope.get("promotion_obj"),
        specialty=specialty,
        trainee_content_type=trainee_content_type,
        trainee_object_id=trainee.pk,
        action_type=action_type,
    ).exists()


def sync_attendance_actions(program, payload, user):
    scope = payload.get("scope") or {}
    batch = scope.get("promotion_obj")
    specialty = (scope.get("specialty") or "") if not payload.get("show_all_specialties") else ""
    threshold = attendance_action_threshold(program)
    created = 0
    updated = 0
    archived = 0

    with transaction.atomic():
        for row in payload.get("stats_rows") or []:
            trainee = row["trainee"]
            absent_count = int(row.get("absent_count") or 0)
            absence_start_date = row.get("absence_start_date")
            due_action_types = attendance_due_action_types(program, absent_count)
            trainee_content_type = ContentType.objects.get_for_model(trainee.__class__)
            scope_qs = AttendanceAction.objects.filter(
                source="daily",
                program=program,
                month=scope.get("month"),
                year=scope.get("year"),
                batch=batch,
                specialty=specialty,
                trainee_content_type=trainee_content_type,
                trainee_object_id=trainee.pk,
            )
            latest_due_rank = 0
            if due_action_types:
                latest_due_rank = AttendanceAction(action_type=due_action_types[-1]).action_rank
                for action_type in due_action_types:
                    if _attendance_action_deletion_exists(program, scope, specialty, trainee_content_type, trainee, action_type):
                        continue

                    defaults = {
                        "trainee_name": f"{getattr(trainee, 'اللقب', '')} {getattr(trainee, 'الاسم', '')}".strip(),
                        "trainee_specialty": getattr(trainee, "التخصص", "") or "",
                        "trainee_address": attendance_action_trainee_address(trainee),
                        "trigger_count": absent_count,
                        "threshold_value": threshold,
                        "absence_start_date": absence_start_date,
                        "document_number": next_attendance_document_number(scope.get("year")),
                        "created_by": user if getattr(user, "is_authenticated", False) else None,
                        "updated_by": user if getattr(user, "is_authenticated", False) else None,
                    }
                    obj, was_created = AttendanceAction.objects.get_or_create(
                        source="daily",
                        program=program,
                        month=scope.get("month"),
                        year=scope.get("year"),
                        batch=batch,
                        specialty=specialty,
                        trainee_content_type=trainee_content_type,
                        trainee_object_id=trainee.pk,
                        action_type=action_type,
                        defaults=defaults,
                    )
                    if was_created:
                        created += 1
                    else:
                        dirty = False
                        if absent_count > (obj.trigger_count or 0):
                            obj.trigger_count = absent_count
                            dirty = True
                        fresh_name = defaults["trainee_name"]
                        fresh_specialty = defaults["trainee_specialty"]
                        fresh_address = defaults["trainee_address"]
                        if fresh_name and obj.trainee_name != fresh_name:
                            obj.trainee_name = fresh_name
                            dirty = True
                        if fresh_specialty and obj.trainee_specialty != fresh_specialty:
                            obj.trainee_specialty = fresh_specialty
                            dirty = True
                        if fresh_address and obj.trainee_address != fresh_address:
                            obj.trainee_address = fresh_address
                            dirty = True
                        if absence_start_date and obj.absence_start_date != absence_start_date:
                            obj.absence_start_date = absence_start_date
                            dirty = True

                        if obj.is_archived and obj.archived_at:
                            should_be_archived = True
                        else:
                            should_be_archived = obj.action_rank < latest_due_rank if latest_due_rank else False

                        if obj.is_archived != should_be_archived:
                            obj.is_archived = should_be_archived
                            obj.archived_at = timezone.now() if should_be_archived else None
                            dirty = True

                        if not obj.document_number:
                            obj.document_number = next_attendance_document_number(obj.year)
                            dirty = True

                        if dirty:
                            obj.updated_by = user if getattr(user, "is_authenticated", False) else obj.updated_by
                            obj.save(update_fields=[
                                "trigger_count",
                                "trainee_name",
                                "trainee_specialty",
                                "trainee_address",
                                "absence_start_date",
                                "document_number",
                                "is_archived",
                                "archived_at",
                                "updated_by",
                                "updated_at",
                            ])
                            updated += 1

                if latest_due_rank:
                    for old_obj in scope_qs.exclude(action_type=due_action_types[-1]):
                        if old_obj.is_archived and old_obj.archived_at:
                            continue

                        should_archive = old_obj.action_rank < latest_due_rank
                        if old_obj.is_archived != should_archive:
                            old_obj.is_archived = should_archive
                            old_obj.archived_at = timezone.now() if should_archive else None
                            old_obj.updated_by = user if getattr(user, "is_authenticated", False) else old_obj.updated_by
                            old_obj.save(update_fields=["is_archived", "archived_at", "updated_by", "updated_at"])
                            archived += 1

                    latest_obj = scope_qs.filter(action_type=due_action_types[-1]).first()
                    if latest_obj and latest_obj.is_archived and not latest_obj.archived_at:
                        latest_obj.is_archived = False
                        latest_obj.archived_at = None
                        latest_obj.updated_by = user if getattr(user, "is_authenticated", False) else latest_obj.updated_by
                        latest_obj.save(update_fields=["is_archived", "archived_at", "updated_by", "updated_at"])
                        updated += 1

    return {"created": created, "updated": updated, "archived": archived}
