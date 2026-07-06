import unittest
from pathlib import Path


class SavedAttendanceStatsServiceStructureTests(unittest.TestCase):
    def test_service_file_exists(self):
        path = Path(__file__).resolve().parents[1] / 'services' / 'saved_attendance_stats_service.py'
        self.assertTrue(path.exists())

    def test_views_delegate_archive_context_to_service(self):
        views_path = Path(__file__).resolve().parents[1] / 'views.py'
        content = views_path.read_text(encoding='utf-8')
        self.assertIn('from .services.saved_attendance_stats_service import build_saved_attendance_stats_archive_context', content)
        self.assertIn('return build_saved_attendance_stats_archive_context(', content)


if __name__ == '__main__':
    unittest.main()
