from collections import Counter


def build_attendance_stats_payload(payload, program):
    columns = payload["columns"]
    rows = payload["rows"]

    stats_rows = []
    totals_counter = Counter()

    for row in rows:
        counter = Counter()
        total_recorded = 0
        for cell in row.get("cells", []):
            if program == "apprentice":
                for slot in cell.get("slots", []):
                    status = (slot.get("status") or "").strip()
                    if not status:
                        continue
                    counter[status] += 1
                    total_recorded += 1
            else:
                status = (cell.get("status") or "").strip()
                if not status:
                    continue
                counter[status] += 1
                total_recorded += 1

        absence_rate = round((counter["absent"] / total_recorded) * 100, 2) if total_recorded else 0
        stats_rows.append({
            "index": row["index"],
            "trainee": row["trainee"],
            "present_count": counter["present"],
            "absent_count": counter["absent"],
            "excused_count": counter["excused"],
            "late_count": counter["late"],
            "total_recorded": total_recorded,
            "absence_rate": absence_rate,
        })
        totals_counter.update(counter)
        totals_counter["total_recorded"] += total_recorded

    stats_rows.sort(
        key=lambda item: (
            -item["absence_rate"],
            -item["absent_count"],
            getattr(item["trainee"], "التخصص", "") or "",
            getattr(item["trainee"], "اللقب", "") or "",
            getattr(item["trainee"], "الاسم", "") or "",
        )
    )
    for index, row in enumerate(stats_rows, start=1):
        row["display_index"] = index

    trainee_count = len(stats_rows)
    average_absence_rate = round(sum(item["absence_rate"] for item in stats_rows) / trainee_count, 2) if trainee_count else 0

    payload = dict(payload)
    payload.update({
        "stats_rows": stats_rows,
        "stats_totals": {
            "present_count": totals_counter["present"],
            "absent_count": totals_counter["absent"],
            "excused_count": totals_counter["excused"],
            "late_count": totals_counter["late"],
            "total_recorded": totals_counter["total_recorded"],
        },
        "average_absence_rate": average_absence_rate,
        "trainee_count": trainee_count,
        "displayed_days_count": len(columns),
    })
    return payload


def attendance_stats_scope_filters(program, scope):
    return {
        "program": program,
        "year": scope["year"],
        "month": scope["month"],
        "batch": scope.get("promotion_obj"),
        "specialty": (scope.get("specialty") or ""),
    }


def attendance_saved_stats_program_options(user, allowed_program_codes, attendance_programs):
    return [
        {"code": code, "label": attendance_programs[code]["label"]}
        for code in allowed_program_codes
        if code in attendance_programs
    ]
