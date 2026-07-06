from django.test import SimpleTestCase

from trainees.excel_import import build_import_issue, summarize_import_issues, group_import_issues


class ExcelImportReportingTests(SimpleTestCase):
    def test_build_import_issue_formats_row_prefix(self):
        issue = build_import_issue(
            "invalid_date",
            "تاريخ بداية التكوين غير صالح",
            row_index=7,
            row_identity="محمد علي — رقم التسجيل: 1234",
        )
        self.assertEqual(issue["category"], "invalid_date")
        self.assertIn("السطر 7", issue["message"])
        self.assertIn("محمد علي", issue["message"])

    def test_summarize_import_issues_counts_by_category(self):
        issues = [
            build_import_issue("invalid_date", "خطأ 1", row_index=2),
            build_import_issue("invalid_date", "خطأ 2", row_index=3),
            build_import_issue("duplicate_in_file", "مكرر", row_index=4),
        ]
        summary = summarize_import_issues(issues)
        self.assertEqual(summary[0]["category"], "invalid_date")
        self.assertEqual(summary[0]["count"], 2)
        self.assertEqual(summary[1]["category"], "duplicate_in_file")
        self.assertEqual(summary[1]["count"], 1)

    def test_group_import_issues_returns_bucketed_items(self):
        issues = [
            build_import_issue("missing_required", "ناقص الاسم", row_index=5),
            build_import_issue("missing_required", "ناقص اللقب", row_index=6),
            build_import_issue("duplicate_existing", "موجود مسبقا", row_index=8),
        ]
        groups = group_import_issues(issues)
        self.assertEqual(groups[0]["category"], "missing_required")
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(len(groups[0]["items"]), 2)
        self.assertEqual(groups[1]["category"], "duplicate_existing")
