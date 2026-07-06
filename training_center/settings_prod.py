"""إعدادات الإنتاج الصارمة.

لا تُستخدم في تشغيل LAN العادي. استعمل settings_lan للمكاتب وsettings_central للخادم المركزي.
"""
import os

os.environ.setdefault("DJANGO_ENV", "prod")

from .settings_base import *  # noqa: F401,F403,E402

APP_MODE = os.getenv("APP_MODE", "prod").strip() or "prod"
DEBUG = env_bool("DJANGO_DEBUG", False)

if SECRET_KEY == "unsafe-dev-key-change-me":
    raise RuntimeError("وضع الإنتاج يتطلب DJANGO_SECRET_KEY حقيقيًا في ملف البيئة.")

if DB_ENGINE not in {"postgres", "postgresql"}:
    raise RuntimeError("وضع الإنتاج يتطلب DB_ENGINE=postgres أو DB_ENGINE=postgresql.")
