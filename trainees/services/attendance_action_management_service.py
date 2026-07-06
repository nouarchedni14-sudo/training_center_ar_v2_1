from datetime import date, datetime
import re
from urllib.parse import urlencode

from django.db.models import Case, When, Value, IntegerField

from trainees.models import AttendanceAction, AttendanceActionDeletion
from trainees.program_split_utils import (
    filter_generic_records_to_active_trainees,
    filter_records_by_split_program,
)


def selected_action_ids_from_request(request):
    ids = []
    for value in request.GET.getlist("ids") + request.POST.getlist("ids"):
        for part in str(value).split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
    return list(dict.fromkeys(ids))


def parse_bulk_action_date(raw_value, date_input_formats):
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return None
    for fmt in date_input_formats:
        try:
            if fmt == "%Y-%m-%d" and re.match(r"^\d{4}-\d{2}-\d{2}$", raw_value):
                return date.fromisoformat(raw_value)
            return datetime.strptime(raw_value, fmt).date()
        except Exception:
            continue
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except Exception:
        return None


def attendance_action_source(action) -> str:
    return (getattr(action, "source", "daily") or "daily").strip() or "daily"


def attendance_action_base_query(action):
    specialty = (action.specialty or action.trainee_specialty or "").strip()
    params = []
    if attendance_action_source(action) == "slots":
        params.append(("source", "slots"))
    params += [
        ("month", action.month),
        ("year", action.year),
        ("archive_state", "archived" if action.is_archived else "active"),
    ]
    if action.batch_id:
        params.append(("promotion", action.batch_id))
    if specialty:
        params.append(("specialty", specialty))
    params.append(("action_type", action.action_type))
    if action.status:
        params.append(("status", action.status))
    return urlencode(params)


def summarize_attendance_actions(actions):
    rows = list(actions)
    return {
        "total": len(rows),
        "pending": sum(1 for item in rows if item.status == "pending"),
        "ready": sum(1 for item in rows if item.status == "ready"),
        "issued": sum(1 for item in rows if item.status == "issued"),
        "delivered": sum(1 for item in rows if item.status == "delivered"),
    }


def attendance_actions_qs(program, scope, action_type="", status="", archive_state="active", source="daily"):
    qs = AttendanceAction.objects.filter(
        source=(source or "daily"),
        month=scope.get("month"),
        year=scope.get("year"),
    )

    if scope.get("promotion_obj"):
        qs = qs.filter(batch=scope.get("promotion_obj"))
    if scope.get("specialty"):
        specialty = (scope.get("specialty") or "").strip()
        qs = qs.filter(specialty=specialty)

    if action_type:
        qs = qs.filter(action_type=action_type)
    if status:
        qs = qs.filter(status=status)
    if archive_state == "archived":
        qs = qs.filter(is_archived=True)
    elif archive_state == "active":
        qs = qs.filter(is_archived=False)

    action_rank_order = Case(
        When(action_type="excuse_1", then=Value(1)),
        When(action_type="excuse_2", then=Value(2)),
        When(action_type="excuse_3", then=Value(3)),
        When(action_type="summon", then=Value(4)),
        default=Value(99),
        output_field=IntegerField(),
    )
    status_rank_order = Case(
        When(status="pending", then=Value(1)),
        When(status="ready", then=Value(2)),
        When(status="issued", then=Value(3)),
        When(status="delivered", then=Value(4)),
        When(status="cancelled", then=Value(5)),
        default=Value(99),
        output_field=IntegerField(),
    )
    qs = filter_records_by_split_program(qs, program)
    if archive_state != "archived":
        try:
            from trainees.forms import MODEL_BY_PROGRAM
            qs = filter_generic_records_to_active_trainees(qs, program, MODEL_BY_PROGRAM.get(program))
        except Exception:
            pass

    return qs.annotate(
        _action_rank_order=action_rank_order,
        _status_rank_order=status_rank_order,
    ).select_related("batch", "created_by", "updated_by").order_by(
        "is_archived",
        "trainee_name",
        "_action_rank_order",
        "_status_rank_order",
        "pk",
    )


def register_attendance_action_deletion(action, user=None):
    AttendanceActionDeletion.objects.update_or_create(
        source=attendance_action_source(action),
        program=action.program,
        month=action.month,
        year=action.year,
        batch=action.batch,
        specialty=(action.specialty or "").strip(),
        trainee_content_type=action.trainee_content_type,
        trainee_object_id=action.trainee_object_id,
        action_type=action.action_type,
        defaults={
            "deleted_by": user if getattr(user, "is_authenticated", False) else None,
        },
    )


def clear_attendance_action_deletion(action):
    AttendanceActionDeletion.objects.filter(
        source=attendance_action_source(action),
        program=action.program,
        month=action.month,
        year=action.year,
        batch=action.batch,
        specialty=(action.specialty or "").strip(),
        trainee_content_type=action.trainee_content_type,
        trainee_object_id=action.trainee_object_id,
        action_type=action.action_type,
    ).delete()
