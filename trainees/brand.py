from pathlib import Path
from django.conf import settings

INSTITUTION_NAME = "المعهد الوطني المتخصص في التكوين المهني"
MINISTRY_NAME = "وزارة التكوين والتعليم المهنيين"


def project_asset_url(filename: str) -> str:
    path = Path(settings.BASE_DIR) / filename
    return f'/{filename}' if path.exists() else ''
