from .attendance_slots_common import attendance_slots_export, attendance_slots_program, attendance_slots_stats, attendance_slots_sync_actions


def evening_slots(request):
    return attendance_slots_program(request, "evening")


def evening_slots_stats(request):
    return attendance_slots_stats(request, "evening")


def evening_slots_export(request, fmt):
    return attendance_slots_export(request, "evening", fmt)

def evening_slots_sync_actions(request):
    return attendance_slots_sync_actions(request, "evening")
