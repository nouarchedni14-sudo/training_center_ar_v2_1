import os
import tempfile
from datetime import date

from django.test import SimpleTestCase, override_settings
from openpyxl import Workbook

from trainees.excel_import import expected_columns_for_model, preview_sheet
from trainees.models import تمهين


class ExcelImportPreviewTests(SimpleTestCase):
    def _write_workbook(self, base_dir, headers, rows, temp_id="preview_case"):
        tmp_dir = os.path.join(base_dir, "tmp_imports")
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, f"{temp_id}.xlsx")

        wb = Workbook()
        ws = wb.active
        ws.title = "بيانات"
        ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(path)
        return temp_id

    def test_preview_sheet_counts_duplicates_and_invalid_dates(self):
        headers = [verbose for _, verbose in expected_columns_for_model(تمهين, include_assumed=True)]
        row_ok = {
            "الرقم التعريفي": "A1",
            "اللقب": "بن صالح",
            "الاسم": "أحمد",
            "تاريخ الميلاد": "2000-01-10",
            "التخصص": "إعلام آلي",
            "رقم التسجيل": "2024/01",
            "تاريخ بداية التكوين": "2024-02-01",
            "تاريخ نهاية التكوين": "2025-02-01",
        }
        row_duplicate = {
            "الرقم التعريفي": "A2",
            "اللقب": "بن صالح",
            "الاسم": "أحمد",
            "تاريخ الميلاد": "2000-01-10",
            "التخصص": "إعلام آلي",
            "رقم التسجيل": "2024/01",
            "تاريخ بداية التكوين": "2024-02-01",
            "تاريخ نهاية التكوين": "2025-02-01",
        }
        row_bad_dates = {
            "الرقم التعريفي": "A3",
            "اللقب": "قاسمي",
            "الاسم": "ليلى",
            "تاريخ الميلاد": "not-a-date",
            "التخصص": "محاسبة",
            "رقم التسجيل": "2024/02",
            "تاريخ بداية التكوين": "2025-05-01",
            "تاريخ نهاية التكوين": "2024-01-01",
        }

        rows = []
        for mapping in (row_ok, row_duplicate, row_bad_dates):
            rows.append([mapping.get(header, "") for header in headers])

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_id = self._write_workbook(tmpdir, headers, rows)
            with override_settings(BASE_DIR=tmpdir):
                preview = preview_sheet(تمهين, temp_id, "بيانات")

        self.assertTrue(preview["ok"])
        self.assertEqual(preview["total_rows"], 3)
        self.assertEqual(preview["valid_rows"], 1)
        self.assertEqual(preview["invalid_rows"], 2)
        self.assertEqual(preview["duplicate_rows"], 1)
        self.assertGreaterEqual(preview["error_count"], 3)
        joined = "\n".join(preview["errors"])
        self.assertIn("مكرر داخل نفس ملف Excel", joined)
        self.assertIn("تاريخ الميلاد غير صالح", joined)
        self.assertIn("تاريخ نهاية التكوين أقدم من تاريخ بداية التكوين", joined)

    def test_preview_sheet_detects_header_mismatch(self):
        bad_headers = ["الاسم", "اللقب", "حقل غير معروف"]
        rows = [["أحمد", "بن صالح", "قيمة"]]

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_id = self._write_workbook(tmpdir, bad_headers, rows, temp_id="bad_headers")
            with override_settings(BASE_DIR=tmpdir):
                preview = preview_sheet(تمهين, temp_id, "بيانات")

        self.assertFalse(preview["ok"])
        self.assertIn("HEADER_MISMATCH", preview["errors"])
        self.assertTrue(preview["missing"])
