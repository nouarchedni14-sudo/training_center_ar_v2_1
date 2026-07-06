import importlib.util
import pathlib
import unittest
from urllib.parse import parse_qsl, urlencode

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / 'services' / 'attendance_view_state_service.py'
spec = importlib.util.spec_from_file_location('attendance_view_state_service', MODULE_PATH)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class FakeQueryDict(dict):
    def copy(self):
        return FakeQueryDict(self)

    def urlencode(self):
        return urlencode(list(self.items()), doseq=True)


class AttendanceViewStateServiceTests(unittest.TestCase):
    def _q(self, query: str) -> FakeQueryDict:
        return FakeQueryDict(parse_qsl(query, keep_blank_values=True))

    def test_resolve_attendance_post_action_defaults_to_save(self):
        self.assertEqual(service.resolve_attendance_post_action(self._q("")), "save")
        self.assertEqual(service.resolve_attendance_post_action(self._q("post_action=unknown")), "save")
        self.assertEqual(service.resolve_attendance_post_action(self._q("post_action=delete_saved")), "delete_saved")

    def test_should_process_save_detects_status_cells(self):
        post = self._q("post_action=save&status__1__2026-04-01=p")
        self.assertTrue(service.should_process_attendance_save(post))
        self.assertFalse(service.should_process_attendance_delete(post))

    def test_should_process_delete(self):
        post = self._q("post_action=delete_saved")
        self.assertTrue(service.should_process_attendance_delete(post))
        self.assertFalse(service.should_process_attendance_save(post))

    def test_build_preserved_query_removes_status_and_tokens(self):
        post = self._q("csrfmiddlewaretoken=abc&post_action=save&month=4&status__1__2026-04-01=a")
        query = service.build_preserved_query(post, remove_status_fields=True, remove_post_action=True)
        self.assertIn("month=4", query)
        self.assertNotIn("csrfmiddlewaretoken", query)
        self.assertNotIn("post_action", query)
        self.assertNotIn("status__", query)

    def test_build_preserved_query_can_force_show_table(self):
        get_data = self._q("month=4&hide_table=1")
        query = service.build_preserved_query(get_data, remove_hide_table=True, force_show_table=True)
        self.assertIn("month=4", query)
        self.assertIn("show_table=1", query)
        self.assertNotIn("hide_table", query)

    def test_parse_old_stats_cutoff(self):
        month, year = service.parse_old_stats_cutoff(self._q("cutoff_month=3&cutoff_year=2026"))
        self.assertEqual((month, year), (3, 2026))
        month, year = service.parse_old_stats_cutoff(self._q("cutoff_month=x&cutoff_year=y"))
        self.assertEqual((month, year), (0, 0))

    def test_valid_old_stats_cutoff(self):
        self.assertTrue(service.valid_old_stats_cutoff(4, 2026))
        self.assertFalse(service.valid_old_stats_cutoff(0, 2026))
        self.assertFalse(service.valid_old_stats_cutoff(4, 1999))


if __name__ == "__main__":
    unittest.main()
