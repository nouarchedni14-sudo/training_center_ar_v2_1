from .attendance_slots_common import attendance_slots_export, attendance_slots_program, attendance_slots_stats, attendance_slots_sync_actions


def apprentice_slots(request):
    return attendance_slots_program(request, "apprentice")


def apprentice_slots_stats(request):
    return attendance_slots_stats(request, "apprentice")


def apprentice_slots_export(request, fmt):
    return attendance_slots_export(request, "apprentice", fmt)

def apprentice_slots_sync_actions(request):
    return attendance_slots_sync_actions(request, "apprentice")
