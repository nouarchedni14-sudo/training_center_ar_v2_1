import unittest
from types import SimpleNamespace

from trainees.services.attendance_export_service import AttendanceExportService


class AttendanceExportServiceTests(unittest.TestCase):
    def _build_service(self):
        def group_items_by_specialty(rows, accessor):
            groups = {}
            for row in rows:
                groups.setdefault(accessor(row), []).append(row)
            return list(groups.items())

        def apply_official_header(ws, total_columns, program, scope, specialty_label="", semester_label=""):
            ws.cell(row=1, column=1, value=f"{program}:{specialty_label}:{semester_label}")

        return AttendanceExportService(
            status_label_map=lambda program: {"present": "ح", "absent": "غ", "late": "ت"},
            group_items_by_specialty=group_items_by_specialty,
            safe_sheet_title=lambda value, fallback="ورقة": (value or fallback)[:31],
            attendance_rows_semester_label=lambda rows: "س1",
            apply_official_header=apply_official_header,
            register_pdf_font=lambda: "Helvetica",
            pdf_text=lambda value: str(value),
            pdf_row=lambda values: [str(v) for v in values],
            attendance_template_title=lambda program, specialty: f"عنوان {program} {specialty}".strip(),
            attendance_scope_subtitle=lambda scope, specialty_label="", semester_label="": f"{scope['month']}/{scope['year']} {specialty_label} {semester_label}".strip(),
            export_header_lines=["رأس 1", "رأس 2", "رأس 3"],
        )

    def _sample_payload(self):
        trainee1 = SimpleNamespace(اللقب="أحمد", الاسم="علي", التخصص="إعلام آلي")
        trainee2 = SimpleNamespace(اللقب="خالد", الاسم="يوسف", التخصص="كهرباء")
        return {
            "rows": [
                {"index": 1, "trainee": trainee1, "cells": [{"status": "present"}, {"status": "absent"}]},
                {"index": 2, "trainee": trainee2, "cells": [{"status": "late"}, {"status": "present"}]},
            ],
            "scope": {"month": 4, "year": 2026, "specialty": ""},
            "slot_count": 1,
            "columns": [
                {"weekday_label": "الإثنين", "day_num": 7},
                {"weekday_label": "الأربعاء", "day_num": 9},
            ],
            "show_all_specialties": True,
        }

    def test_build_workbook_creates_sheet_per_specialty(self):
        service = self._build_service()
        wb = service.build_workbook("initial", self._sample_payload())

        self.assertEqual(len(wb.sheetnames), 2)
        self.assertIn("إعلام آلي", wb.sheetnames)
        self.assertIn("كهرباء", wb.sheetnames)
        ws = wb["إعلام آلي"]
        self.assertEqual(ws["A1"].value, "initial:إعلام آلي:س1")
        self.assertEqual(ws["A12"].value, "01")
        self.assertEqual(ws["B12"].value, "أحمد علي")
        self.assertEqual(ws["D12"].value, "ح")
        self.assertEqual(ws["E12"].value, "غ")

    def test_build_pdf_bytes_returns_pdf_content(self):
        service = self._build_service()
        pdf_bytes = service.build_pdf_bytes("initial", self._sample_payload())

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 500)


if __name__ == "__main__":
    unittest.main()
