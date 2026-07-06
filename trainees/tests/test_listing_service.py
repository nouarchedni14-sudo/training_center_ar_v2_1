import ast
from pathlib import Path
import unittest


class ListingServiceStructureTests(unittest.TestCase):
    def setUp(self):
        self.service_path = Path(__file__).resolve().parents[1] / "services" / "listing_service.py"
        self.views_path = Path(__file__).resolve().parents[1] / "views.py"
        self.service_source = self.service_path.read_text(encoding="utf-8")
        self.views_source = self.views_path.read_text(encoding="utf-8")
        self.service_tree = ast.parse(self.service_source)

    def test_service_file_exists_and_defines_expected_functions(self):
        function_names = {node.name for node in self.service_tree.body if isinstance(node, ast.FunctionDef)}
        expected = {
            "normalize_text",
            "unique_clean_values",
            "extract_list_filters",
            "apply_advanced_filters",
            "build_semester_options",
            "build_specialty_options",
            "build_query_string_without_page",
            "build_program_title",
            "can_export_for_user",
        }
        self.assertTrue(expected.issubset(function_names))

    def test_views_uses_listing_service_helpers(self):
        self.assertIn("from .services.listing_service import (", self.views_source)
        self.assertIn("build_program_title(program, PROGRAM_TITLES, graduates=graduates)", self.views_source)
        self.assertIn("filters = extract_list_filters(request.GET)", self.views_source)
        self.assertIn("build_query_string_without_page(request.GET)", self.views_source)
        self.assertIn("can_export_for_user(request.user)", self.views_source)

    def test_listing_service_keeps_semester_rank_constant(self):
        self.assertIn('SEMESTER_RANK = {"الأول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4, "الخامس": 5}', self.service_source)


if __name__ == "__main__":
    unittest.main()
