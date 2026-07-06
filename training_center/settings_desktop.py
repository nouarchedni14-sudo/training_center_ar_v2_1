"""إعدادات نسخة سطح المكتب المحلية.

تستخدم الإعدادات الأساسية وقاعدة SQLite ما لم يتم تمرير متغيرات بيئة أخرى.
"""
import os

os.environ.setdefault("DJANGO_ENV", "desktop")

from .settings_base import *  # noqa: F401,F403,E402

APP_MODE = os.getenv("APP_MODE", "desktop").strip() or "desktop"
DEBUG = env_bool("DJANGO_DEBUG", False)
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "training_center_desktop_sessionid")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "training_center_desktop_csrftoken")
