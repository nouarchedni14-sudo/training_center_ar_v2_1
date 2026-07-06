import os
import uuid
from datetime import date

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from openpyxl import Workbook

from trainees.excel_import import (
    _required_core_fields,
    _temp_path,
    _validate_row_dates,
    expected_columns_for_model,
    import_sheet,
)
from trainees.models import تمهين


class ExcelImportHelpersTests(SimpleTestCase):
    def test_validate_row_dates_rejects_invalid_order(self):
        data = {
            "تاريخ_بداية_التكوين": "2025-09-01",
            "تاريخ_نهاية_التكوين": "2025-06-01",
            "تاريخ_الميلاد": "2000-01-01",
            "_model_fields": list(تمهين._meta.fields),
        }
        errors = []

        ok = _validate_row_dates(data, 2, "طالب ", errors)

        self.assertFalse(ok)
        self.assertTrue(any("تاريخ نهاية التكوين أقدم من تاريخ بداية التكوين" in msg for msg in errors))

    def test_required_core_fields_detects_missing_values(self):
        missing = _required_core_fields(
            {
                "اللقب": "",
                "الاسم": "محمد",
                "التخصص": None,
                "رقم_التسجيل": "",
                "تاريخ_بداية_التكوين": None,
                "تاريخ_نهاية_التكوين": date(2026, 6, 30),
            }
        )

        self.assertEqual(
            missing,
            ["اللقب", "التخصص", "رقم التسجيل", "تاريخ بداية التكوين"],
        )


class ExcelImportIntegrationTests(TestCase):
    def _create_temp_workbook(self, rows):
        headers = [verbose for _, verbose in expected_columns_for_model(تمهين, include_assumed=False)]
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "البيانات"
        sheet.append(headers)
        for row_values in rows:
            sheet.append([row_values.get(header) for header in headers])

        temp_id = uuid.uuid4().hex
        path = _temp_path(temp_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        workbook.save(path)
        return temp_id

    def test_import_sheet_reports_duplicate_rows_inside_same_file(self):
        row = {
            "اللقب": "بن علي",
            "الاسم": "أحمد",
            "التخصص": "إعلام آلي",
            "رقم التسجيل": "0061 225R",
            "تاريخ بداية التكوين": "2025-09-01",
            "تاريخ نهاية التكوين": "2028-06-30",
            "تاريخ الميلاد": "2000-02-10",
        }
        temp_id = self._create_temp_workbook([row, row])

        created, errors = import_sheet(تمهين, temp_id, "البيانات")

        self.assertEqual(created, 1)
        self.assertTrue(any("مكرر داخل نفس الملف" in msg for msg in errors))
        self.assertEqual(تمهين.objects.count(), 1)

    def test_import_sheet_rejects_invalid_training_date_order(self):
        row = {
            "اللقب": "بن علي",
            "الاسم": "سارة",
            "التخصص": "إلكترونيك",
            "رقم التسجيل": "0061 125R",
            "تاريخ بداية التكوين": "2025-09-01",
            "تاريخ نهاية التكوين": "2025-01-01",
        }
        temp_id = self._create_temp_workbook([row])

        created, errors = import_sheet(تمهين, temp_id, "البيانات")

        self.assertEqual(created, 0)
        self.assertTrue(any("تاريخ نهاية التكوين أقدم من تاريخ بداية التكوين" in msg for msg in errors))
        self.assertEqual(تمهين.objects.count(), 0)
