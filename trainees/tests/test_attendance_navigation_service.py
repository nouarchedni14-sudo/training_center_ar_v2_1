import ast
from pathlib import Path
import unittest


class AttendanceNavigationServiceTests(unittest.TestCase):
    def setUp(self):
        self.service_path = Path(__file__).resolve().parents[1] / "services" / "attendance_navigation_service.py"
        self.views_path = Path(__file__).resolve().parents[1] / "views.py"
        self.service_source = self.service_path.read_text(encoding="utf-8")
        self.views_source = self.views_path.read_text(encoding="utf-8")
        self.service_tree = ast.parse(self.service_source)

    def test_service_file_exists_and_defines_expected_function(self):
        function_names = {node.name for node in self.service_tree.body if isinstance(node, ast.FunctionDef)}
        self.assertIn("build_attendance_home_cards", function_names)

    def test_views_restores_attendance_home_and_uses_service(self):
        self.assertIn("def attendance_home(request):", self.views_source)
        self.assertIn("build_attendance_home_cards(allowed_programs, ATTENDANCE_PROGRAMS)", self.views_source)
        self.assertIn('return render(request, "trainees/attendance_home.html"', self.views_source)

    def test_service_builds_card_payload_shape(self):
        namespace = {}
        exec(self.service_source, namespace)
        cards = namespace["build_attendance_home_cards"](["initial", "missing"], {
            "initial": {"label": "الحضوري الأولي", "description": "وصف"},
        })
        self.assertEqual(cards, [{"code": "initial", "label": "الحضوري الأولي", "description": "وصف"}])


if __name__ == "__main__":
    unittest.main()
