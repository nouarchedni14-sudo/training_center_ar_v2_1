from .attendance_slots_common import attendance_slots_export, attendance_slots_program, attendance_slots_stats, attendance_slots_sync_actions


def initial_slots(request):
    return attendance_slots_program(request, "initial")


def initial_slots_stats(request):
    return attendance_slots_stats(request, "initial")


def initial_slots_export(request, fmt):
    return attendance_slots_export(request, "initial", fmt)

def initial_slots_sync_actions(request):
    return attendance_slots_sync_actions(request, "initial")
