from __future__ import annotations

from typing import Any


ATTENDANCE_POST_ACTIONS = {"save", "delete_saved"}
ATTENDANCE_STATS_POST_ACTIONS = {"save_stats", "delete_saved_stats", "delete_old_stats"}


def resolve_attendance_post_action(post_data: Any) -> str:
    action = str((post_data.get("post_action") or "save")).strip()
    return action if action in ATTENDANCE_POST_ACTIONS else "save"



def should_process_attendance_save(post_data: Any, *, action: str | None = None) -> bool:
    current_action = action or resolve_attendance_post_action(post_data)
    return current_action == "save" and any(str(key).startswith("status__") for key in post_data.keys())



def should_process_attendance_delete(post_data: Any, *, action: str | None = None) -> bool:
    current_action = action or resolve_attendance_post_action(post_data)
    return current_action == "delete_saved"



def build_preserved_query(source_data: Any, *, remove_status_fields: bool = False, remove_post_action: bool = False, remove_hide_table: bool = False, force_show_table: bool = False) -> str:
    params = source_data.copy()
    for key in ["csrfmiddlewaretoken", *([] if not remove_post_action else ["post_action"]), *([] if not remove_hide_table else ["hide_table"] )]:
        params.pop(key, None)
    if remove_status_fields:
        for key in list(params.keys()):
            if str(key).startswith("status__"):
                params.pop(key, None)
    if force_show_table:
        params["show_table"] = "1"
    return params.urlencode()



def parse_old_stats_cutoff(post_data: Any) -> tuple[int, int]:
    try:
        month = int(post_data.get("cutoff_month") or 0)
        year = int(post_data.get("cutoff_year") or 0)
    except (TypeError, ValueError):
        return 0, 0
    return month, year



def valid_old_stats_cutoff(month: int, year: int) -> bool:
    return month in range(1, 13) and year >= 2000
