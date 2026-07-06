from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from trainees.models import دفعة


class PromotionModelTests(TestCase):
    def test_save_normalizes_promotion_name_and_semester_dates(self):
        promotion = دفعة.objects.create(
            اسم_الدفعة="اسم غير معتمد",
            رقم_الدورة=1,
            السنة=2026,
            تاريخ_الدخول_الرسمي=date(2026, 2, 1),
        )

        self.assertEqual(promotion.اسم_الدفعة, "فيفري")
        self.assertEqual(promotion.بداية_السداسي_1, date(2026, 2, 1))
        self.assertIsNotNone(promotion.بداية_السداسي_5)

    def test_clean_rejects_mismatched_name_for_session(self):
        promotion = دفعة(
            اسم_الدفعة="سبتمبر",
            رقم_الدورة=1,
            السنة=2026,
            تاريخ_الدخول_الرسمي=date(2026, 2, 1),
        )

        with self.assertRaises(ValidationError):
            promotion.clean()

    def test_unique_session_and_year_constraint_blocks_duplicates(self):
        دفعة.objects.create(
            اسم_الدفعة="فيفري",
            رقم_الدورة=1,
            السنة=2026,
            تاريخ_الدخول_الرسمي=date(2026, 2, 1),
        )

        with self.assertRaises(ValidationError):
            دفعة.objects.create(
                اسم_الدفعة="فيفري",
                رقم_الدورة=1,
                السنة=2026,
                تاريخ_الدخول_الرسمي=date(2026, 2, 5),
            )
