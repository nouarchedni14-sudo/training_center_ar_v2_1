# -*- coding: utf-8 -*-
"""صفحات غيابات المعابر بالحصة."""
from __future__ import annotations

from .attendance_slots_common import attendance_slots_export, attendance_slots_program, attendance_slots_stats, attendance_slots_sync_actions


def crossing_slots(request):
    return attendance_slots_program(request, "crossing")


def crossing_slots_stats(request):
    return attendance_slots_stats(request, "crossing")


def crossing_slots_export(request, fmt):
    return attendance_slots_export(request, "crossing", fmt)


def crossing_slots_sync_actions(request):
    return attendance_slots_sync_actions(request, "crossing")
