import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / 'services' / 'account_dashboard_service.py'
spec = importlib.util.spec_from_file_location('account_dashboard_service', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

build_access_ui = module.build_access_ui
build_account_context = module.build_account_context
build_dashboard_context = module.build_dashboard_context


class DummyPromotion:
    def __init__(self, name, year):
        self.اسم_الدفعة = name
        self.السنة = year


class DummyTrainee:
    def __init__(self, semester, promotion=None):
        self.السداسي = semester
        self.الدفعة = promotion


class AccountDashboardServiceTests(unittest.TestCase):
    def test_build_account_context_creates_permission_cards(self):
        summary = {
            'state': 'active',
            'state_label': 'نشط',
            'message': 'ok',
            'allowed_programs': ['الحضوري الأولي', 'التمهين'],
            'can_access_admin': True,
            'can_view_reports': False,
            'can_export_data': True,
            'allowed_weekdays': 'الأحد-الخميس',
            'daily_window': '08:00 - 16:00',
            'access_type': 'محدد',
        }
        context = build_account_context(object(), build_access_summary_func=lambda _u: summary)
        self.assertEqual(context['allowed_programs_verbose'], ['الحضوري الأولي', 'التمهين'])
        self.assertEqual(context['access_ui']['badge_class'], 'success')
        self.assertEqual(len(context['permission_cards']), 6)

    def test_build_dashboard_context_aggregates_cards_and_stats(self):
        current_rows = [
            DummyTrainee('الأول', DummyPromotion('A', 2025)),
            DummyTrainee('الأول', DummyPromotion('A', 2025)),
            DummyTrainee('الثاني', DummyPromotion('B', 2024)),
        ]
        graduate_rows = [DummyTrainee('الخامس', DummyPromotion('A', 2024))]

        def get_rows(_model, _code, graduates=False):
            return graduate_rows if graduates else current_rows

        context = build_dashboard_context(
            object(),
            program_specs=[('initial', 'الحضوري الأولي', object())],
            today='2026-04-06',
            allowed_programs=['initial'],
            admin_access=False,
            promotion_count=3,
            get_ordered_rows=get_rows,
            refresh_rows_live_semesters=lambda rows, _model: rows,
            build_access_summary_func=lambda _u: {
                'state': 'active', 'state_label': 'نشط', 'message': 'ok',
                'allowed_programs': ['الحضوري الأولي'], 'can_access_admin': False,
                'can_view_reports': True, 'can_export_data': True,
                'allowed_weekdays': 'كل الأيام', 'daily_window': '—', 'access_type': 'عادي',
            },
            reverse_func=lambda name, args=None: f'/{name}/',
        )

        self.assertEqual(context['cards'][0]['total_count'], 4)
        self.assertEqual(context['cards'][0]['current_count'], 3)
        self.assertEqual(context['cards'][0]['graduate_count'], 1)
        self.assertEqual(context['semester_stats'][0]['items'][0]['السداسي'], 'الأول')
        self.assertEqual(context['promotion_stats'][0]['items'][0]['الدفعة__اسم_الدفعة'], 'A')
        self.assertTrue(context['quick_links'])

    def test_build_access_ui_handles_expired(self):
        ui = build_access_ui({'state': 'expired'})
        self.assertEqual(ui['badge_class'], 'danger')
        self.assertIn('انتهت', ui['title'])


if __name__ == '__main__':
    unittest.main()
