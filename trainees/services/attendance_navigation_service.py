from __future__ import annotations

from typing import Iterable


def build_attendance_home_cards(allowed_programs: Iterable[str], attendance_programs: dict[str, dict[str, object]]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for code in allowed_programs:
        config = attendance_programs.get(code)
        if not config:
            continue
        cards.append({
            "code": code,
            "label": str(config.get("label") or code),
            "description": str(config.get("description") or ""),
        })
    return cards
