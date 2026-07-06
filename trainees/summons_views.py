from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import SummonsRecord, دفعة
from .forms import MODEL_BY_PROGRAM, DATE_INPUT_FORMATS
from .services.attendance_action_management_service import parse_bulk_action_date
from .permissions import require_program_permission
from .program_split_utils import (
    filter_records_by_split_program,
    filter_records_by_split_program_for_active_trainees,
)
from .views import (
    ATTENDANCE_PROGRAMS,
    _sanction_base_queryset,
    _valid_sanction_scope,
    _sanction_scope_label,
    _refresh_rows_live_semesters,
    _selected_int_ids,
    build_specialty_options,
    build_semester_options,
    extract_list_filters,
    log_activity,
)


def _valid_summons_type(value):
    value = (value or "").strip()
    valid = dict(SummonsRecord.SUMMONS_TYPE_CHOICES)
    return value if value in valid else "graduate_title"


def _summons_return_url(program, scope, query=""):
    base = reverse("summons_records", args=[program])
    query = (query or "").strip()
    if query:
        return f"{base}?{query}"
    return f"{base}?scope={scope}"


def _summons_records_for_trainees(program, scope, summons_type, model_cls, trainees):
    if not trainees:
        return {}
    ct = ContentType.objects.get_for_model(model_cls)
    ids = [obj.pk for obj in trainees]
    records = SummonsRecord.objects.filter(
        summons_scope=scope,
        summons_type=summons_type,
        trainee_content_type=ct,
        trainee_object_id__in=ids,
    )
    records = filter_records_by_split_program(records, program)
    return {obj.trainee_object_id: obj for obj in records}


def _ensure_summons_records(program, scope, summons_type, trainee_ids, user, *, touch_snapshot=True):
    ModelCls = MODEL_BY_PROGRAM.get(program)
    if not ModelCls:
        return []
    valid_qs = _sanction_base_queryset(program, scope).filter(pk__in=trainee_ids)
    trainees = list(valid_qs)
    if not trainees:
        return []
    ct = ContentType.objects.get_for_model(ModelCls)
    records = []
    with transaction.atomic():
        for trainee in trainees:
            record, created = SummonsRecord.objects.get_or_create(
                program=program,
                summons_scope=scope,
                summons_type=summons_type,
                trainee_content_type=ct,
                trainee_object_id=trainee.pk,
                defaults={
                    "trainee_name": getattr(trainee, "اللقب_والاسم", str(trainee) or ""),
                    "created_by": user,
                    "updated_by": user,
                    "issue_date": timezone.localdate(),
                },
            )
            if touch_snapshot or created:
                record.sync_snapshot_from_trainee(trainee)
            record.updated_by = user
            if created and not record.created_by_id:
                record.created_by = user
            record.save()
            records.append(record)
    records.sort(key=lambda obj: (obj.specialty or "", obj.trainee_name or "", obj.pk))
    return records


def _existing_summons_records_for_selected_trainees(program, scope, summons_type, trainee_ids):
    ModelCls = MODEL_BY_PROGRAM.get(program)
    if not ModelCls or not trainee_ids:
        return SummonsRecord.objects.none()
    ct = ContentType.objects.get_for_model(ModelCls)
    qs = SummonsRecord.objects.filter(
        summons_scope=scope,
        summons_type=summons_type,
        trainee_content_type=ct,
        trainee_object_id__in=trainee_ids,
    )
    return filter_records_by_split_program(qs, program)


def _date_to_text(value):
    if not value:
        return "............"
    try:
        return "\u200e" + value.strftime("%Y-%m-%d") + "\u200e"
    except Exception:
        return str(value)


def summons_body_text(record):
    from_date = _date_to_text(record.from_date)
    contract_date = _date_to_text(record.contract_termination_date)
    council_date = _date_to_text(record.council_date)
    council_time = (record.council_time or "............").strip() or "............"
    lesson = (record.lesson_name or "............").strip() or "............"

    if record.summons_type == "contract_termination":
        return (
            f"لقد تم فسخ عقدكم منذ تاريخ: {contract_date} عند المستخدم، لذا نطلب منكم الالتحاق بالمعهد الوطني المتخصص في التكوين المهني "
            "تاج الدين حامد عبد الوهاب تيسمسيلت لتسوية وضعيتكم في أقرب الآجال وإلا فسوف تأخذ الإجراءات الإدارية الصارمة طبقًا للقانون لا سيما المادة رقم 27 ويتم فصلكم من تعداد المتكونين."
        )
    if record.summons_type == "employer_absence":
        return (
            "يؤسفني أن أدعوكم للالتحاق بالمعهد الوطني المتخصص في التكوين المهني الشهيد تاج الدين حامد عبد الوهاب تيسمسيلت "
            f"لتسوية وضعيتكم مع المستخدم وهذا راجع لعدم التحاقكم بالمستخدم منذ يوم: {from_date}."
        )
    if record.summons_type == "intermittent_absence":
        return (
            "إن إدارة المعهد الوطني المتخصص في التكوين المهني الشهيد تاج الدين حامد عبد الوهاب تيسمسيلت تدعوكم للالتحاق في أقرب الآجال "
            f"لمزاولة دروسكم النظرية قبل إحالتكم للمجلس التأديبي والشطب النهائي وهذا راجع لغياباتكم المتذبذبة منذ: {from_date}."
        )
    if record.summons_type == "specific_session_absence":
        return (
            "إن إدارة المعهد الوطني المتخصص في التكوين المهني تاج الدين حامد عبد الوهاب تيسمسيلت تدعوكم لحضور المجلس التأديبي "
            f"على الساعة التاسعة صباحًا يوم: {council_date}، وهذا راجع لعدم حضوركم حصة: {lesson} منذ: {from_date}."
        )
    if record.summons_type == "disciplinary_council":
        return (
            "يؤسفني أن أدعوكم للالتحاق بالمعهد الوطني المتخصص في التكوين المهني تاج الدين حامد عبد الوهاب تيسمسيلت "
            f"يوم: {council_date}، وهذا من أجل الحضور للمجلس التأديبي على الساعة: {council_time}."
        )
    if record.summons_type == "supervisor_absence":
        return (
            "إن إدارة المعهد الوطني المتخصص في التكوين المهني الشهيد تاج الدين حامد عبد الوهاب تيسمسيلت تدعوكم للالتحاق إلى المعهد في أقرب الآجال "
            "وهذا من أجل الغيابات المستمرة عند المؤطر وإلا سوف تأخذ الإجراءات الإدارية الصارمة وهي الفصل من التكوين."
        )
    return (
        "يؤسفني أن أدعوكم للالتحاق بالمعهد الوطني المتخصص في التكوين المهني الشهيد تاج الدين حامد عبد الوهاب تيسمسيلت "
        "في أقرب الآجال خلال هذا الأسبوع وهذا راجع لعدم استلامكم عنوان مذكرة التخرج."
    )


@login_required
def summons_records(request, program):
    if program not in ATTENDANCE_PROGRAMS:
        raise Http404()
    require_program_permission(request, program, "view")
    scope = _valid_sanction_scope(request.GET.get("scope"))
    summons_type = _valid_summons_type(request.GET.get("summons_type"))
    ModelCls = MODEL_BY_PROGRAM.get(program)
    if not ModelCls:
        return HttpResponseBadRequest("نمط غير صالح")

    base_qs = _sanction_base_queryset(program, scope)
    qs = _sanction_base_queryset(program, scope, request=request)
    status_filter = (request.GET.get("status") or "").strip()

    # صفحة/زر استدعاءات الغيابات المتذبذبة لا يجب أن يعرض كل المتكونين.
    # هذا النوع يُنشأ آليًا من جدول الغياب بالحصة، لذلك نعرض فقط المتكونين
    # الذين لديهم استدعاء غيابات متذبذبة نشط، ولا نعرض من لا يحققون الشرط.
    show_existing_records_only = summons_type == "intermittent_absence"
    if show_existing_records_only:
        trainee_ct = ContentType.objects.get_for_model(ModelCls)
        existing_records_qs = SummonsRecord.objects.filter(
            summons_scope=scope,
            summons_type=summons_type,
            trainee_content_type=trainee_ct,
        )
        existing_records_qs = filter_records_by_split_program(existing_records_qs, program)
        if status_filter == "cancelled":
            existing_records_qs = existing_records_qs.filter(status="cancelled")
        else:
            existing_records_qs = existing_records_qs.exclude(status="cancelled")
            if status_filter:
                existing_records_qs = existing_records_qs.filter(status=status_filter)
        existing_trainee_ids = list(existing_records_qs.values_list("trainee_object_id", flat=True).distinct())
        qs = qs.filter(pk__in=existing_trainee_ids)

    paginator = Paginator(qs, 200)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    rows = list(page_obj.object_list)
    rows = _refresh_rows_live_semesters(rows, ModelCls)
    record_map = _summons_records_for_trainees(program, scope, summons_type, ModelCls, rows)
    for row in rows:
        row.summons_record = record_map.get(row.pk)

    if status_filter:
        rows = [r for r in rows if getattr(getattr(r, "summons_record", None), "status", "") == status_filter]
        page_obj.object_list = rows

    promotion_options = list(
        دفعة.objects.filter(
            id__in=base_qs.exclude(الدفعة_id__isnull=True).values_list("الدفعة_id", flat=True).distinct(),
            مفعلة=True,
        ).order_by("-السنة", "-رقم_الدورة").only("id", "اسم_الدفعة", "السنة")
    )
    specialty_options = build_specialty_options(
        base_qs.order_by().exclude(التخصص__isnull=True).exclude(التخصص="").values_list("التخصص", flat=True)
    )
    semester_options = build_semester_options(
        base_qs.order_by().exclude(السداسي__isnull=True).exclude(السداسي="").values_list("السداسي", flat=True)
    )
    year_options = list(
        base_qs.exclude(الدفعة__السنة__isnull=True).values_list("الدفعة__السنة", flat=True).distinct().order_by("-الدفعة__السنة")
    )
    current_query_dict = request.GET.copy()
    current_query_dict["scope"] = scope
    current_query_dict["summons_type"] = summons_type
    current_query = current_query_dict.urlencode()
    summary = {
        "total": len(rows),
        "missing": sum(1 for row in rows if not getattr(row, "summons_record", None)),
        "ready": sum(1 for row in rows if getattr(getattr(row, "summons_record", None), "status", "") == "ready"),
        "issued": sum(1 for row in rows if getattr(getattr(row, "summons_record", None), "status", "") == "issued"),
        "delivered": sum(1 for row in rows if getattr(getattr(row, "summons_record", None), "status", "") == "delivered"),
    }
    log_activity(request, "view", program=program, details=f"عرض الاستدعاءات - {_sanction_scope_label(scope)}")
    return render(request, "trainees/summons.html", {
        "title": f"الاستدعاءات - {ATTENDANCE_PROGRAMS[program]['label']}",
        "program": program,
        "program_label": ATTENDANCE_PROGRAMS[program]["label"],
        "scope": scope,
        "scope_label": _sanction_scope_label(scope),
        "rows": rows,
        "page_obj": page_obj,
        "summary": summary,
        "promotion_options": promotion_options,
        "specialty_options": specialty_options,
        "semester_options": semester_options,
        "year_options": year_options,
        "status_choices": SummonsRecord.STATUS_CHOICES,
        "summons_type_choices": SummonsRecord.SUMMONS_TYPE_CHOICES,
        "selected_status": status_filter,
        "selected_summons_type": summons_type,
        "selected_summons_type_label": dict(SummonsRecord.SUMMONS_TYPE_CHOICES).get(summons_type, summons_type),
        "show_existing_records_only": show_existing_records_only,
        "filters": extract_list_filters(request.GET),
        "current_query": current_query,
        "base_current_url": reverse("summons_records", args=[program]) + f"?scope=current&summons_type={summons_type}",
        "base_graduated_url": reverse("summons_records", args=[program]) + f"?scope=graduated&summons_type={summons_type}",
    })


@login_required
@require_POST
def summons_records_bulk(request, program):
    if program not in ATTENDANCE_PROGRAMS:
        return HttpResponseBadRequest("نمط غير صالح")
    action = (request.POST.get("bulk_action") or "").strip()
    scope = _valid_sanction_scope(request.POST.get("scope"))
    summons_type = _valid_summons_type(request.POST.get("summons_type"))
    return_query = (request.POST.get("return_query") or f"scope={scope}&summons_type={summons_type}").strip()
    trainee_ids = _selected_int_ids(request)
    if not trainee_ids:
        messages.error(request, "اختر متكونًا واحدًا على الأقل قبل تنفيذ العملية.")
        return redirect(_summons_return_url(program, scope, return_query))

    if action == "delete":
        require_program_permission(request, program, "delete")
        qs = _existing_summons_records_for_selected_trainees(program, scope, summons_type, trainee_ids)
        count = qs.count()
        qs.delete()
        messages.success(request, f"تم حذف {count} استدعاء/استدعاءات.")
        return redirect(_summons_return_url(program, scope, return_query))

    required_perm = "change" if action in {"create", "edit"} else "view"
    require_program_permission(request, program, required_perm)
    records = _ensure_summons_records(program, scope, summons_type, trainee_ids, request.user)
    if not records:
        messages.error(request, "لم يتم العثور على متكونين مطابقين للاختيار الحالي.")
        return redirect(_summons_return_url(program, scope, return_query))
    record_ids = [obj.pk for obj in records]
    query = urlencode([("ids", pk) for pk in record_ids] + [("return_query", return_query)], doseq=True)
    if action in {"create", "edit"}:
        return redirect(reverse("summons_records_bulk_edit", args=[program]) + "?" + query)
    if action == "print":
        return redirect(reverse("summons_records_preview", args=[program]) + "?" + query + "&print=1")
    return redirect(reverse("summons_records_preview", args=[program]) + "?" + query)


@login_required
def summons_records_bulk_edit(request, program):
    if program not in ATTENDANCE_PROGRAMS:
        return HttpResponseBadRequest("نمط غير صالح")
    require_program_permission(request, program, "change")
    if request.method == "POST":
        record_ids = _selected_int_ids(request)
        return_query = (request.POST.get("return_query") or "").strip()
    else:
        record_ids = _selected_int_ids(request)
        return_query = (request.GET.get("return_query") or "").strip()
    records_qs = filter_records_by_split_program_for_active_trainees(
        SummonsRecord.objects.filter(pk__in=record_ids),
        program,
        MODEL_BY_PROGRAM.get(program),
    )
    records = list(records_qs.order_by("specialty", "trainee_name", "pk"))
    if not records:
        messages.error(request, "لم يتم العثور على الاستدعاءات المحددة.")
        return redirect(reverse("summons_records", args=[program]))

    if request.method == "POST":
        updated_count = 0
        with transaction.atomic():
            for obj in records:
                prefix = f"row_{obj.pk}_"
                obj.document_number = (request.POST.get(prefix + "document_number") or "").strip()
                obj.address = (request.POST.get(prefix + "address") or "").strip()
                obj.group_code = (request.POST.get(prefix + "group_code") or "").strip()
                obj.semester = (request.POST.get(prefix + "semester") or "").strip()
                obj.council_time = (request.POST.get(prefix + "council_time") or "").strip()
                obj.lesson_name = (request.POST.get(prefix + "lesson_name") or "").strip()
                obj.notes = (request.POST.get(prefix + "notes") or "").strip()
                # لا نغيّر نوع الاستدعاء من صفحة التحرير.
                # النوع يُختار مرة واحدة من الصفحة الأولى فقط، حتى لا يرجع خطأً إلى النوع الافتراضي.
                status = (request.POST.get(prefix + "status") or "draft").strip()
                if status in dict(SummonsRecord.STATUS_CHOICES):
                    obj.status = status
                for field in ("issue_date", "from_date", "contract_termination_date", "council_date"):
                    raw = request.POST.get(prefix + field)
                    parsed = parse_bulk_action_date(raw, DATE_INPUT_FORMATS)
                    if raw and parsed is None:
                        messages.error(request, f"تاريخ غير صالح في استدعاء: {obj.trainee_name}")
                        return redirect(request.path + "?" + urlencode([("ids", pk) for pk in record_ids] + ([("return_query", return_query)] if return_query else []), doseq=True))
                    setattr(obj, field, parsed)
                obj.updated_by = request.user
                obj.full_clean()
                obj.save()
                updated_count += 1
        messages.success(request, f"تم حفظ {updated_count} استدعاء/استدعاءات بنجاح.")
        if return_query:
            return redirect(reverse("summons_records", args=[program]) + "?" + return_query)
        first = records[0]
        return redirect(reverse("summons_records", args=[program]) + f"?scope={first.summons_scope}&summons_type={first.summons_type}")

    query_string = urlencode([("ids", obj.pk) for obj in records] + ([("return_query", return_query)] if return_query else []), doseq=True)
    return render(request, "trainees/summons_bulk_form.html", {
        "title": f"تحرير الاستدعاءات - {ATTENDANCE_PROGRAMS[program]['label']}",
        "program": program,
        "program_label": ATTENDANCE_PROGRAMS[program]["label"],
        "records": records,
        "return_query": return_query,
        "query_string": query_string,
        "status_choices": SummonsRecord.STATUS_CHOICES,
        "summons_type_choices": SummonsRecord.SUMMONS_TYPE_CHOICES,
        "back_url": reverse("summons_records", args=[program]) + ("?" + return_query if return_query else f"?scope={records[0].summons_scope}&summons_type={records[0].summons_type}"),
    })


@login_required
def summons_records_preview(request, program):
    if program not in ATTENDANCE_PROGRAMS:
        raise Http404()
    require_program_permission(request, program, "view")
    record_ids = _selected_int_ids(request)
    records_qs = filter_records_by_split_program_for_active_trainees(
        SummonsRecord.objects.filter(pk__in=record_ids),
        program,
        MODEL_BY_PROGRAM.get(program),
    )
    records = list(records_qs.order_by("specialty", "trainee_name", "pk"))
    if not records:
        messages.error(request, "لا توجد استدعاءات للمعاينة.")
        return redirect(reverse("summons_records", args=[program]))
    return_query = (request.GET.get("return_query") or "").strip()
    auto_print = (request.GET.get("print") or "") == "1"
    if auto_print:
        SummonsRecord.objects.filter(pk__in=[obj.pk for obj in records]).update(status="issued", updated_by=request.user)
        for obj in records:
            obj.status = "issued"
    for obj in records:
        obj.body_text = summons_body_text(obj)
    log_activity(request, "view", program=program, details=f"معاينة الاستدعاءات ({len(records)})")
    return render(request, "trainees/summons_preview.html", {
        "title": f"معاينة الاستدعاءات - {ATTENDANCE_PROGRAMS[program]['label']}",
        "program": program,
        "program_label": ATTENDANCE_PROGRAMS[program]["label"],
        "records": records,
        "return_query": return_query,
        "auto_print": auto_print,
    })
