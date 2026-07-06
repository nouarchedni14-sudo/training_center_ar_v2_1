from __future__ import annotations

import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sync_core.models import Commune, Wilaya
from sync_core.organization import ALGERIA_CITIES_CSV, ALGERIA_CITIES_XLSX, normalize_commune_code, normalize_wilaya_code


_HEADERS = [
    "row_number",
    "commune_name_latin",
    "commune_name_ar",
    "commune_code",
    "wilaya_code",
    "wilaya_name_latin",
    "wilaya_name_ar",
]


def _xlsx_rows(path: Path):
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}

    def col_row(ref: str) -> tuple[int, int]:
        m = re.match(r"([A-Z]+)(\d+)", ref or "")
        if not m:
            return 0, 0
        col = 0
        for ch in m.group(1):
            col = col * 26 + ord(ch) - 64
        return col, int(m.group(2))

    with zipfile.ZipFile(path) as zf:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                texts = []
                for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"):
                    texts.append(t.text or "")
                strings.append("".join(texts))
        sheet_path = "xl/worksheets/sheet1.xml"
        root = ET.fromstring(zf.read(sheet_path))
        for row in root.findall(".//m:row", ns):
            values = {}
            for c in row.findall("m:c", ns):
                col, _ = col_row(c.attrib.get("r", ""))
                if not col:
                    continue
                typ = c.attrib.get("t")
                v = c.find("m:v", ns)
                value = v.text if v is not None else ""
                if typ == "s" and value != "":
                    value = strings[int(value)]
                values[col] = str(value or "").strip()
            if values:
                yield [values.get(i, "") for i in range(1, 8)]


def _iter_city_rows(path: Path):
    if not path.exists():
        raise CommandError(f"الملف غير موجود: {path}")
    if path.suffix.lower() == ".xlsx":
        first = True
        for row in _xlsx_rows(path):
            if first:
                first = False
                continue
            yield dict(zip(_HEADERS, row))
        return
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield row


class Command(BaseCommand):
    help = "استيراد الولايات والبلديات من ملف Algeria Cities المرفق داخل المشروع."

    def add_arguments(self, parser):
        parser.add_argument("--path", default="", help="مسار CSV أو XLSX. الافتراضي sync_core/data/algeria_cities.csv")
        parser.add_argument("--xlsx", action="store_true", help="استعمال ملف Excel المرفق بدل CSV.")
        parser.add_argument("--clear", action="store_true", help="حذف البلديات والولايات قبل الاستيراد. لا تستعمله بعد ربط مكاتب بها.")
        parser.add_argument("--quiet", action="store_true", help="تقليل المخرجات.")

    def handle(self, *args, **options):
        path = Path(options["path"] or (ALGERIA_CITIES_XLSX if options["xlsx"] else ALGERIA_CITIES_CSV))
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists() and not options["path"]:
            # fallback إلى xlsx إذا لم يوجد csv.
            path = ALGERIA_CITIES_XLSX

        created_w = updated_w = created_c = updated_c = 0
        with transaction.atomic():
            if options["clear"]:
                Commune.objects.all().delete()
                Wilaya.objects.all().delete()

            for row in _iter_city_rows(path):
                wilaya_code = normalize_wilaya_code(row.get("wilaya_code"))
                commune_code = normalize_commune_code(row.get("commune_code"))
                if not wilaya_code or not commune_code:
                    continue
                wilaya, w_created = Wilaya.objects.update_or_create(
                    code=wilaya_code,
                    defaults={
                        "name_ar": (row.get("wilaya_name_ar") or "").strip(),
                        "name_latin": (row.get("wilaya_name_latin") or "").strip(),
                        "is_active": True,
                    },
                )
                if w_created:
                    created_w += 1
                else:
                    updated_w += 1
                _, c_created = Commune.objects.update_or_create(
                    code=commune_code,
                    defaults={
                        "wilaya": wilaya,
                        "name_ar": (row.get("commune_name_ar") or "").strip(),
                        "name_latin": (row.get("commune_name_latin") or "").strip(),
                        "is_active": True,
                    },
                )
                if c_created:
                    created_c += 1
                else:
                    updated_c += 1

        if not options["quiet"]:
            self.stdout.write(self.style.SUCCESS("تم استيراد Algeria Cities بنجاح."))
            self.stdout.write(f"الملف: {path}")
            self.stdout.write(f"الولايات: جديد {created_w} / تحديث {updated_w}")
            self.stdout.write(f"البلديات: جديد {created_c} / تحديث {updated_c}")
