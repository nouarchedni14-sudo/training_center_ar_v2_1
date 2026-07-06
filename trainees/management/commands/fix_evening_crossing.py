# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter, defaultdict

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import IntegrityError, connection
from django.db.models import Q

from trainees.attendance_slots_models import AttendanceSlotCell, AttendanceSlotSheet
from trainees.evening_training_type import (
    EVENING_TRAINING_TYPE_CROSSING,
    EVENING_TRAINING_TYPE_EVENING,
    clamp_semester_for_evening_type,
    clean_crossing_specialty_label,
    detect_evening_training_type,
)
from trainees.models import (
    AttendanceAction,
    AttendanceActionDeletion,
    DismissalDecision,
    SanctionRecord,
    SummonsRecord,
    خليةغياب,
    كشفغياب,
    مسائي_ومعابر,
)
from trainees.program_split_utils import program_for_evening_training_type


SPLIT_PROGRAMS = {"evening", "crossing"}


class Command(BaseCommand):
    help = "تصنيف الدروس المسائية والمعابر، وتطبيق الفصل على الوثائق وجداول الغياب."

    def _program_from_training_type(self, value: str) -> str:
        return program_for_evening_training_type(value) or "evening"

    def _safe_update_field(self, model_cls, obj_id, field_name: str, value, counters, label: str) -> None:
        try:
            updated = model_cls.objects.filter(pk=obj_id).update(**{field_name: value})
            if updated:
                counters[label] += 1
        except IntegrityError:
            counters[f"{label}_skipped_unique"] += 1
        except Exception:
            counters[f"{label}_skipped_error"] += 1

    def _safe_update_fields(self, model_cls, obj_id, values: dict, counters, label: str) -> None:
        if not values:
            return
        try:
            updated = model_cls.objects.filter(pk=obj_id).update(**values)
            if updated:
                counters[label] += 1
        except IntegrityError:
            counters[f"{label}_skipped_unique"] += 1
        except Exception:
            counters[f"{label}_skipped_error"] += 1

    def _count_training_types(self, trainee_ids, trainee_type_by_id) -> Counter:
        c = Counter()
        for trainee_id in trainee_ids:
            training_type = trainee_type_by_id.get(int(trainee_id or 0))
            if training_type:
                c[training_type] += 1
        return c

    def _program_from_counter(self, c: Counter):
        crossing = c.get(EVENING_TRAINING_TYPE_CROSSING, 0)
        evening = c.get(EVENING_TRAINING_TYPE_EVENING, 0)
        if crossing and not evening:
            return "crossing"
        if evening and not crossing:
            return "evening"
        if crossing > evening:
            return "crossing"
        if evening > crossing:
            return "evening"
        return None

    def _infer_sheet_program(self, sheet, cell_model, trainee_type_by_id):
        specialty = str(getattr(sheet, "التخصص", "") or "").strip()
        if "معابر" in specialty or "معبر" in specialty:
            return "crossing"

        trainee_ids = list(
            cell_model.objects.filter(الكشف=sheet)
            .values_list("trainee_id", flat=True)
            .distinct()
        )
        if trainee_ids:
            return self._program_from_counter(self._count_training_types(trainee_ids, trainee_type_by_id))

        qs = مسائي_ومعابر.objects.all()
        if getattr(sheet, "الدفعة_id", None):
            qs = qs.filter(الدفعة_id=sheet.الدفعة_id)
        if specialty:
            clean_specialty = clean_crossing_specialty_label(specialty)
            qs = qs.filter(Q(التخصص=specialty) | Q(التخصص=clean_specialty))
        counts = Counter(qs.values_list("نوع_التكوين", flat=True))
        return self._program_from_counter(counts)

    def handle(self, *args, **options):
        table = مسائي_ومعابر._meta.db_table
        column = مسائي_ومعابر._meta.get_field("نوع_التكوين").column
        qn = connection.ops.quote_name

        self.stdout.write("[1/5] التأكد من عمود نوع التكوين...")
        with connection.cursor() as cur:
            cur.execute(f'ALTER TABLE {qn(table)} ADD COLUMN IF NOT EXISTS {qn(column)} varchar(20);')
            cur.execute(
                f'UPDATE {qn(table)} SET {qn(column)} = %s WHERE {qn(column)} IS NULL OR {qn(column)} = %s;',
                [EVENING_TRAINING_TYPE_EVENING, ""],
            )
            cur.execute(f'ALTER TABLE {qn(table)} ALTER COLUMN {qn(column)} SET DEFAULT %s;', [EVENING_TRAINING_TYPE_EVENING])
            cur.execute(f'ALTER TABLE {qn(table)} ALTER COLUMN {qn(column)} SET NOT NULL;')
            try:
                cur.execute(
                    f'CREATE INDEX IF NOT EXISTS {qn("trainees_مسائي_ومعابر_نوع_التكوين_fea0f3fd")} '
                    f'ON {qn(table)} ({qn(column)});'
                )
            except Exception:
                pass

        self.stdout.write("[2/5] تصنيف سجلات الدروس المسائية والمعابر...")
        total = evening = crossing = changed = 0
        updates = []
        update_fields = ["نوع_التكوين", "التخصص", "السداسي"]

        qs = مسائي_ومعابر.objects.all().only(
            "id", "نوع_التكوين", "التخصص", "النظام", "رمز_التخصص",
            "تاريخ_بداية_التكوين", "تاريخ_نهاية_التكوين", "السداسي",
        ).iterator(chunk_size=1000)

        for obj in qs:
            total += 1
            old_type = obj.نوع_التكوين
            old_specialty = obj.التخصص
            old_semester = obj.السداسي

            detected_type = detect_evening_training_type(obj, respect_explicit_evening=False)
            if detected_type == EVENING_TRAINING_TYPE_CROSSING:
                crossing += 1
                obj.التخصص = clean_crossing_specialty_label(obj.التخصص)
            else:
                evening += 1
                obj.التخصص = str(obj.التخصص or "").strip()

            obj.نوع_التكوين = detected_type
            obj.السداسي = clamp_semester_for_evening_type(obj.السداسي, detected_type)

            if old_type != obj.نوع_التكوين or old_specialty != obj.التخصص or old_semester != obj.السداسي:
                updates.append(obj)
                changed += 1

            if len(updates) >= 1000:
                مسائي_ومعابر.objects.bulk_update(updates, update_fields, batch_size=1000)
                updates = []

        if updates:
            مسائي_ومعابر.objects.bulk_update(updates, update_fields, batch_size=1000)

        self.stdout.write("[3/5] تطبيق الفصل على الوثائق الإدارية والإعذارات والاستدعاءات...")
        counters = defaultdict(int)
        trainee_type_by_id = dict(مسائي_ومعابر.objects.values_list("id", "نوع_التكوين"))
        evening_ct = ContentType.objects.get_for_model(مسائي_ومعابر)

        generic_models = [
            (AttendanceAction, "إعذارات/استدعاءات الغياب"),
            (AttendanceActionDeletion, "سجل حذف الإعذارات"),
            (DismissalDecision, "مقررات الفصل"),
            (SanctionRecord, "العقوبات"),
            (SummonsRecord, "الاستدعاءات"),
        ]
        for model_cls, label in generic_models:
            qs = model_cls.objects.filter(
                program__in=SPLIT_PROGRAMS,
                trainee_content_type=evening_ct,
            ).only("id", "program", "trainee_object_id").iterator(chunk_size=1000)
            for obj in qs:
                target_program = self._program_from_training_type(trainee_type_by_id.get(obj.trainee_object_id))
                if target_program and obj.program != target_program:
                    self._safe_update_field(model_cls, obj.pk, "program", target_program, counters, label)

        self.stdout.write("[4/5] تطبيق الفصل على جداول الغياب اليومية وجداول الغياب بالحصة...")
        sheet_specs = [
            (كشفغياب, خليةغياب, "الغياب اليومي"),
            (AttendanceSlotSheet, AttendanceSlotCell, "الغياب بالحصة"),
        ]
        for sheet_model, cell_model, label in sheet_specs:
            qs = sheet_model.objects.filter(البرنامج__in=SPLIT_PROGRAMS).only(
                "id", "البرنامج", "التخصص", "الدفعة_id"
            ).iterator(chunk_size=500)
            for sheet in qs:
                target_program = self._infer_sheet_program(sheet, cell_model, trainee_type_by_id)
                clean_specialty = clean_crossing_specialty_label(getattr(sheet, "التخصص", "") or "")
                values = {}
                if target_program and getattr(sheet, "البرنامج") != target_program:
                    values["البرنامج"] = target_program
                if clean_specialty != (getattr(sheet, "التخصص", "") or ""):
                    values["التخصص"] = clean_specialty
                self._safe_update_fields(sheet_model, sheet.pk, values, counters, label)

        self.stdout.write("[5/5] النتيجة النهائية:")
        self.stdout.write(f"إجمالي سجلات الدروس المسائية/المعابر المفحوصة: {total}")
        self.stdout.write(f"دروس مسائية: {evening}")
        self.stdout.write(f"معابر: {crossing}")
        self.stdout.write(f"سجلات متكونين تم تحديثها: {changed}")

        final_counts = Counter(مسائي_ومعابر.objects.values_list("نوع_التكوين", flat=True))
        for key in sorted(final_counts):
            self.stdout.write(f"{key}: {final_counts[key]}")

        if counters:
            self.stdout.write("تحديث الوثائق والجداول:")
            for key in sorted(counters):
                self.stdout.write(f"- {key}: {counters[key]}")

        self.stdout.write(self.style.SUCCESS("تم التصنيف والتطبيق على الوثائق والجداول بنجاح."))
