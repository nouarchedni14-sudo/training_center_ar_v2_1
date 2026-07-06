import unittest
from pathlib import Path


class AttendanceActionManagementStructureTests(unittest.TestCase):
    def test_management_service_exists_and_exports_helpers(self):
        service_path = Path("trainees/services/attendance_action_management_service.py")
        self.assertTrue(service_path.exists())
        content = service_path.read_text(encoding="utf-8")
        for name in [
            "def attendance_actions_qs",
            "def attendance_action_base_query",
            "def register_attendance_action_deletion",
            "def clear_attendance_action_deletion",
            "def parse_bulk_action_date",
            "def selected_action_ids_from_request",
        ]:
            self.assertIn(name, content)

    def test_views_use_management_service_helpers(self):
        views_content = Path("trainees/views.py").read_text(encoding="utf-8")
        self.assertIn("from .services.attendance_action_management_service import", views_content)
        self.assertIn("attendance_actions_qs(", views_content)
        self.assertIn("attendance_action_base_query(", views_content)
        self.assertIn("register_attendance_action_deletion(", views_content)
        self.assertIn("clear_attendance_action_deletion(", views_content)


if __name__ == "__main__":
    unittest.main()
