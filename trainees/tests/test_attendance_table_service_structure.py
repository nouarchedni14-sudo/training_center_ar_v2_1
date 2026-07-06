import ast
from pathlib import Path
import unittest


class AttendanceTableServiceStructureTests(unittest.TestCase):
    def test_views_imports_attendance_table_service(self):
        source = Path(__file__).resolve().parents[1] / "views.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported = False
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "services.attendance_table_service" and node.level == 1:
                names = {alias.name for alias in node.names}
                self.assertIn("build_attendance_changes", names)
                self.assertIn("delete_saved_attendance_entries", names)
                self.assertIn("existing_attendance_entries", names)
                self.assertIn("persist_attendance_changes", names)
                imported = True
                break
        self.assertTrue(imported)

    def test_service_exposes_expected_functions(self):
        source = Path(__file__).resolve().parents[1] / "services" / "attendance_table_service.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertTrue({
            "normalize_attendance_status",
            "existing_attendance_entries",
            "delete_saved_attendance_entries",
            "build_attendance_changes",
            "persist_attendance_changes",
        }.issubset(function_names))


if __name__ == "__main__":
    unittest.main()
