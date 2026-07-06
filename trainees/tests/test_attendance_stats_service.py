from types import SimpleNamespace
from unittest import TestCase

from trainees.services.attendance_stats_service import (
    attendance_saved_stats_program_options,
    attendance_stats_scope_filters,
    build_attendance_stats_payload,
)


class AttendanceStatsServiceTests(TestCase):
    def test_build_attendance_stats_payload_for_standard_program(self):
        trainee_a = SimpleNamespace(اللقب="أحمد", الاسم="علي", التخصص="إعلام")
        trainee_b = SimpleNamespace(اللقب="بلقاسم", الاسم="سارة", التخصص="محاسبة")
        payload = {
            "columns": [1, 2, 3],
            "rows": [
                {
                    "index": 1,
                    "trainee": trainee_a,
                    "cells": [
                        {"status": "absent"},
                        {"status": "present"},
                        {"status": "late"},
                    ],
                },
                {
                    "index": 2,
                    "trainee": trainee_b,
                    "cells": [
                        {"status": "present"},
                        {"status": "present"},
                        {"status": "excused"},
                    ],
                },
            ],
            "slot_count": 1,
        }

        result = build_attendance_stats_payload(payload, "initial")

        self.assertEqual(result["trainee_count"], 2)
        self.assertEqual(result["displayed_days_count"], 3)
        self.assertEqual(result["stats_rows"][0]["trainee"], trainee_a)
        self.assertEqual(result["stats_rows"][0]["absent_count"], 1)
        self.assertEqual(result["stats_totals"]["present_count"], 3)
        self.assertEqual(result["stats_totals"]["late_count"], 1)

    def test_build_attendance_stats_payload_for_apprentice_slots(self):
        trainee = SimpleNamespace(اللقب="نور", الاسم="الدين", التخصص="كهرباء")
        payload = {
            "columns": [1, 2],
            "rows": [
                {
                    "index": 1,
                    "trainee": trainee,
                    "cells": [
                        {"slots": [{"status": "present"}, {"status": "absent"}]},
                        {"slots": [{"status": "excused"}, {"status": "late"}]},
                    ],
                }
            ],
            "slot_count": 2,
        }

        result = build_attendance_stats_payload(payload, "apprentice")

        row = result["stats_rows"][0]
        self.assertEqual(row["total_recorded"], 4)
        self.assertEqual(row["present_count"], 1)
        self.assertEqual(row["absent_count"], 1)
        self.assertEqual(row["excused_count"], 1)
        self.assertEqual(row["late_count"], 1)
        self.assertEqual(row["absence_rate"], 25.0)

    def test_scope_filters(self):
        scope = {"year": 2026, "month": 4, "promotion_obj": 99, "specialty": "إعلام"}
        self.assertEqual(
            attendance_stats_scope_filters("initial", scope),
            {"program": "initial", "year": 2026, "month": 4, "batch": 99, "specialty": "إعلام"},
        )

    def test_saved_program_options(self):
        options = attendance_saved_stats_program_options(
            user=None,
            allowed_program_codes=["initial", "evening"],
            attendance_programs={
                "initial": {"label": "حضوري أولي"},
                "apprentice": {"label": "تمهين"},
                "evening": {"label": "مسائي"},
            },
        )
        self.assertEqual(options, [
            {"code": "initial", "label": "حضوري أولي"},
            {"code": "evening", "label": "مسائي"},
        ])
