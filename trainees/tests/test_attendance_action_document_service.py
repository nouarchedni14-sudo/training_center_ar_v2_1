from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from trainees.services.attendance_action_document_service import (
    action_date_display,
    attendance_action_document_context,
    attendance_action_download_name,
    build_attendance_action_pdf_response,
    build_attendance_action_word_response,
)


class DummyAction(SimpleNamespace):
    def get_action_type_display(self):
        return getattr(self, "action_type_display", "إعذار")


@override_settings(BASE_DIR="/tmp/proj")
class AttendanceActionDocumentServiceTests(SimpleTestCase):
    def make_action(self, **overrides):
        data = {
            "document_heading": "إعذار أول",
            "document_title": "إعذار",
            "trainee_name": "محمد/أحمد",
            "trainee_specialty": "إعلام آلي",
            "trainee_address": "الجزائر",
            "document_number": "0001",
            "year": 2026,
            "action_type": "excuse_1",
            "action_type_display": "إعذار أول",
            "absence_start_date": date(2026, 4, 1),
            "send_date": date(2026, 4, 6),
        }
        data.update(overrides)
        return DummyAction(**data)

    def test_action_date_display(self):
        self.assertEqual(action_date_display(date(2026, 4, 6)), "2026-04-06")
        self.assertIn(".", action_date_display(None))

    def test_download_name_is_sanitized(self):
        action = self.make_action()
        filename = attendance_action_download_name(action, "pdf")
        self.assertTrue(filename.endswith(".pdf"))
        self.assertNotIn("/", filename)
        self.assertIn("إعذار أول", filename)

    def test_context_contains_expected_keys(self):
        action = self.make_action()
        context = attendance_action_document_context(action, preview_query="month=4")
        self.assertEqual(context["action_obj"], action)
        self.assertEqual(context["document_title_display"], "إعذار أول")
        self.assertEqual(context["preview_query"], "month=4")

    def test_build_word_response(self):
        action = self.make_action()
        response = build_attendance_action_word_response(action)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/msword", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])

    def test_build_pdf_response(self):
        action = self.make_action(action_type="summon", action_type_display="استدعاء")
        response = build_attendance_action_pdf_response(action)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
