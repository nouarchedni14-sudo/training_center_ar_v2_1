from pathlib import Path
import unittest


class SavedAttendanceStatsExportServiceStructureTests(unittest.TestCase):
    def test_service_file_exists_and_exposes_export_builders(self):
        path = Path(__file__).resolve().parents[1] / 'services' / 'saved_attendance_stats_export_service.py'
        content = path.read_text(encoding='utf-8')
        self.assertIn('def build_saved_attendance_stats_excel_response(', content)
        self.assertIn('def build_saved_attendance_stats_pdf_response(', content)
        self.assertIn('def _write_saved_attendance_stats_excel_sheet(', content)

    def test_views_delegate_saved_stats_exports_to_service(self):
        views_path = Path(__file__).resolve().parents[1] / 'views.py'
        content = views_path.read_text(encoding='utf-8')
        self.assertIn('from .services.saved_attendance_stats_export_service import (', content)
        self.assertIn('return build_saved_attendance_stats_excel_response(', content)
        self.assertIn('return build_saved_attendance_stats_pdf_response(', content)


if __name__ == '__main__':
    unittest.main()
