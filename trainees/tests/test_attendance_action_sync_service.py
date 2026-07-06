import unittest
from unittest.mock import MagicMock, patch

from trainees.services.attendance_action_sync_service import attendance_due_action_types, attendance_action_trainee_address


class DummyTrainee:
    اللقب = "بن"
    الاسم = "علي"
    التخصص = "إعلام آلي"
    العنوان_بالعربية = "حي النور"
    العنوان_بالأجنبية = ""
    البلدية = "الأغواط"
    الولاية = "الأغواط"


class AttendanceActionSyncServiceTests(unittest.TestCase):
    def test_due_action_types_for_apprentice_thresholds(self):
        self.assertEqual(attendance_due_action_types("apprentice", 3), [])
        self.assertEqual(attendance_due_action_types("apprentice", 4), ["excuse_1"])
        self.assertEqual(attendance_due_action_types("apprentice", 8), ["excuse_1", "excuse_2"])
        self.assertEqual(attendance_due_action_types("apprentice", 12), ["excuse_1", "excuse_2", "excuse_3", "summon"])

    def test_trainee_address_builder(self):
        trainee = DummyTrainee()
        self.assertEqual(attendance_action_trainee_address(trainee), "حي النور - الأغواط - الأغواط")


if __name__ == "__main__":
    unittest.main()
