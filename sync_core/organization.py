"""Official office identity and organization-unit helpers.

يعتمد المشروع رسميًا على الصيغة:
OFFICE_CODE = DZ + كود الولاية + كود البلدية + نوع المؤسسة + رقم المؤسسة
مثال: DZ38-03801-INSFP01
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


PROJECT_DATA_DIR = Path(__file__).resolve().parent / "data"
ALGERIA_CITIES_XLSX = PROJECT_DATA_DIR / "algeria_cities.xlsx"
ALGERIA_CITIES_CSV = PROJECT_DATA_DIR / "algeria_cities.csv"

ESTABLISHMENT_TYPES = {"INSFP", "CFPA", "ANNEXE", "DIRECTION", "OTHER"}


def normalize_wilaya_code(value: str | int | None) -> str:
    raw = str(value or "").strip()
    raw = re.sub(r"\D", "", raw)
    return raw.zfill(2)[-2:] if raw else ""


def normalize_commune_code(value: str | int | None) -> str:
    raw = str(value or "").strip()
    raw = re.sub(r"\D", "", raw)
    return raw.zfill(5)[-5:] if raw else ""


def normalize_establishment_number(value: str | int | None) -> str:
    raw = str(value or "01").strip()
    raw = re.sub(r"\D", "", raw) or "01"
    return raw.zfill(2)[-4:]


def normalize_establishment_type(value: str | None) -> str:
    raw = str(value or "").strip().upper().replace("-", "_")
    if raw in {"ANNEX", "ANNEXE"}:
        return "ANNEXE"
    return raw if raw in ESTABLISHMENT_TYPES else "OTHER"


def latin_alias(value: str | None, max_len: int = 3) -> str:
    raw = re.sub(r"[^A-Za-z0-9]+", " ", str(value or "").upper()).strip()
    if not raw:
        return "LOC"
    parts = raw.split()
    if len(parts) == 1:
        return parts[0][:max_len].ljust(min(max_len, len(parts[0])), "") or "LOC"
    # خذ أول حرف من كل كلمة، وإذا بقي قصيرًا أكمله من أول كلمة.
    alias = "".join(p[0] for p in parts if p)[:max_len]
    if len(alias) < max_len:
        alias = (alias + parts[0])[:max_len]
    return alias or "LOC"


def safe_ascii_identifier(value: str | None, lower: bool = True) -> str:
    raw = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "").strip())
    raw = re.sub(r"_+", "_", raw).strip("_") or "office"
    return raw.lower() if lower else raw


def build_office_code(wilaya_code: str, commune_code: str, establishment_type: str, establishment_number: str) -> str:
    wc = normalize_wilaya_code(wilaya_code)
    cc = normalize_commune_code(commune_code)
    et = normalize_establishment_type(establishment_type)
    num = normalize_establishment_number(establishment_number)
    if not wc or not cc:
        return ""
    return f"DZ{wc}-{cc}-{et}{num}"


def build_office_alias(wilaya_code: str, commune_name_latin: str, establishment_type: str, establishment_number: str) -> str:
    wc = normalize_wilaya_code(wilaya_code)
    alias = latin_alias(commune_name_latin, 3)
    et = normalize_establishment_type(establishment_type)
    num = normalize_establishment_number(establishment_number)
    return f"DZ{wc}-{alias}-{et}{num}" if wc else f"DZ-{alias}-{et}{num}"


def build_office_name(commune_name_latin: str, establishment_type: str, establishment_number: str) -> str:
    commune = safe_ascii_identifier(commune_name_latin, lower=False).replace("_", "") or "Office"
    et = normalize_establishment_type(establishment_type)
    num = normalize_establishment_number(establishment_number)
    return f"{commune}_{et}{num}"




def build_office_display_name(commune_name_ar: str | None, establishment_type: str, establishment_number: str) -> str:
    """Default Arabic display name for a newly created official office.

    This is only a safe automatic default. The developer can still edit it later
    when the institution receives an official martyr/name.
    """
    commune = str(commune_name_ar or "").strip() or "المؤسسة"
    et = normalize_establishment_type(establishment_type)
    num = normalize_establishment_number(establishment_number)
    if et == "INSFP":
        base = "المعهد الوطني المتخصص في التكوين المهني"
    elif et == "CFPA":
        base = "مركز التكوين المهني والتمهين"
    elif et == "ANNEXE":
        base = "ملحقة التكوين المهني"
    elif et == "DIRECTION":
        base = "مديرية التكوين والتعليم المهنيين"
    else:
        base = "مؤسسة التكوين المهني"
    suffix = f" - {commune}"
    if num and num != "01":
        suffix += f" {num}"
    return base + suffix


def build_office_id(office_code: str) -> str:
    return "office_" + safe_ascii_identifier(str(office_code or "").replace("DZ", "dz"), lower=True)


def build_server_id(office_code: str, suffix: str = "main") -> str:
    return "server_" + safe_ascii_identifier(str(office_code or "").replace("DZ", "dz"), lower=True) + f"_{safe_ascii_identifier(suffix or 'main')}"


def build_data_dir(office_code: str) -> str:
    safe = safe_ascii_identifier(str(office_code or "office").replace("-", "_"), lower=False)
    return rf"C:\TrainingCenterData_{safe}"


def build_database_name(office_code: str) -> str:
    safe = safe_ascii_identifier(str(office_code or "office").replace("-", "_"), lower=True)
    return f"training_center_{safe}"[:60].rstrip("_")


DEFAULT_INSFP_UNITS = [
    {"code": "DG", "name": "إدارة المدير العام", "type": "general", "parent": "", "order": 10},
    {"code": "DIRECTOR", "name": "مدير المؤسسة", "type": "position", "parent": "DG", "order": 11},
    {"code": "SD-INFO-GUIDANCE-DIGITAL-INTEGRATION", "name": "المديرية الفرعية للإعلام والتوجيه والرقمنة والإدماج المهني", "type": "subdirectorate", "parent": "", "order": 20},
    {"code": "SD-INFO-GUIDANCE-DIGITAL-INTEGRATION-DIRECTOR", "name": "مدير المديرية الفرعية", "type": "position", "parent": "SD-INFO-GUIDANCE-DIGITAL-INTEGRATION", "order": 21},
    {"code": "SERVICE-GUIDANCE", "name": "مصلحة التوجيه", "type": "service", "parent": "SD-INFO-GUIDANCE-DIGITAL-INTEGRATION", "order": 22},
    {"code": "SERVICE-GENERAL-CONTROL", "name": "مصلحة المراقبة العامة", "type": "service", "parent": "SD-INFO-GUIDANCE-DIGITAL-INTEGRATION", "order": 23},
    {"code": "SD-STUDIES-INTERNSHIPS", "name": "المديرية الفرعية للدراسات والتربصات", "type": "subdirectorate", "parent": "", "order": 30},
    {"code": "SD-STUDIES-INTERNSHIPS-DIRECTOR", "name": "مدير المديرية الفرعية", "type": "position", "parent": "SD-STUDIES-INTERNSHIPS", "order": 31},
    {"code": "SERVICE-TRAINING-FOLLOWUP", "name": "مصلحة التنظيم ومتابعة التكوين الحضوري والتربصات في الوسط المهني", "type": "service", "parent": "SD-STUDIES-INTERNSHIPS", "order": 32},
    {"code": "SERVICE-SECRETARIAT-STUDIES", "name": "مصلحة السكرتارية", "type": "service", "parent": "SD-STUDIES-INTERNSHIPS", "order": 33},
    {"code": "SERVICE-CERTIFICATES", "name": "مصلحة الشهادات", "type": "service", "parent": "SD-STUDIES-INTERNSHIPS", "order": 34},
    {"code": "SD-APPRENTICESHIP-CONTINUING", "name": "المديرية الفرعية للتمهين والتكوين المهني المتواصل", "type": "subdirectorate", "parent": "", "order": 40},
    {"code": "SD-APPRENTICESHIP-CONTINUING-DIRECTOR", "name": "مدير المديرية الفرعية", "type": "position", "parent": "SD-APPRENTICESHIP-CONTINUING", "order": 41},
    {"code": "SERVICE-APPRENTICESHIP", "name": "مصلحة التمهين", "type": "service", "parent": "SD-APPRENTICESHIP-CONTINUING", "order": 42},
    {"code": "SERVICE-SECRETARIAT-APPRENTICESHIP", "name": "مصلحة السكرتارية", "type": "service", "parent": "SD-APPRENTICESHIP-CONTINUING", "order": 43},
    {"code": "SERVICE-CONTINUING-PARTNERSHIP", "name": "مصلحة التكوين المهني المتواصل والشراكة", "type": "service", "parent": "SD-APPRENTICESHIP-CONTINUING", "order": 44},
]

DEFAULT_CFPA_UNITS = [
    {"code": "DG", "name": "إدارة المدير", "type": "general", "parent": "", "order": 10},
    {"code": "DIRECTOR", "name": "مدير المؤسسة", "type": "position", "parent": "DG", "order": 11},
    {"code": "SERVICE-GUIDANCE", "name": "مصلحة التوجيه", "type": "service", "parent": "", "order": 20},
    {"code": "SERVICE-GENERAL-CONTROL", "name": "مصلحة المراقبة العامة", "type": "service", "parent": "", "order": 30},
    {"code": "SERVICE-APPRENTICESHIP", "name": "مصلحة التمهين", "type": "service", "parent": "", "order": 40},
    {"code": "SERVICE-CERTIFICATES", "name": "مصلحة الشهادات", "type": "service", "parent": "", "order": 50},
]


def default_units_for_establishment(establishment_type: str) -> list[dict[str, object]]:
    et = normalize_establishment_type(establishment_type)
    if et == "INSFP":
        return list(DEFAULT_INSFP_UNITS)
    if et in {"CFPA", "ANNEXE"}:
        return list(DEFAULT_CFPA_UNITS)
    return list(DEFAULT_CFPA_UNITS)


def ensure_default_organization_units(office, *, force: bool = False) -> int:
    """Create missing default units for an office. Returns created/updated count."""
    from .models import OrganizationUnit

    if not office:
        return 0
    if OrganizationUnit.objects.filter(office=office).exists() and not force:
        return 0
    if force:
        OrganizationUnit.objects.filter(office=office).delete()

    by_code = {}
    count = 0
    for item in default_units_for_establishment(getattr(office, "establishment_type", "") or "CFPA"):
        parent = by_code.get(item.get("parent") or "")
        unit, created = OrganizationUnit.objects.update_or_create(
            office=office,
            unit_code=str(item["code"]),
            defaults={
                "name_ar": str(item["name"]),
                "unit_type": str(item.get("type") or "service"),
                "parent": parent,
                "order": int(item.get("order") or 0),
                "is_active": True,
            },
        )
        by_code[unit.unit_code] = unit
        count += 1 if created else 0
    return count
