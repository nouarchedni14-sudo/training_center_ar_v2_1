from types import SimpleNamespace

from django.test import SimpleTestCase

from trainees.services.export_service import export_excel_response, export_pdf_response, pdf_text


class ExportServiceTests(SimpleTestCase):
    def test_export_excel_response_returns_xlsx(self):
        cols = [("اللقب", "اللقب"), ("الاسم", "الاسم")]
        rows = [SimpleNamespace(اللقب="بن علي", الاسم="أحمد")]

        response = export_excel_response("test", cols, rows, lambda obj, field: getattr(obj, field, ""))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", response["Content-Type"])
        self.assertIn('test.xlsx', response["Content-Disposition"])

    def test_export_pdf_response_returns_pdf(self):
        cols = [("الرقم_التعريفي", "المعرف"), ("اللقب", "اللقب"), ("الاسم", "الاسم")]
        rows = [SimpleNamespace(الرقم_التعريفي="1", اللقب="بن علي", الاسم="أحمد")]

        response = export_pdf_response("test", cols, rows, lambda obj, field: getattr(obj, field, ""))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('test.pdf', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_text_handles_none(self):
        self.assertEqual(pdf_text(None), "")
