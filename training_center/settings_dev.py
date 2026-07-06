"""إعدادات التطوير عند تشغيل manage.py بدون DJANGO_ENV.

هذا الملف يزيل خطأ settings_dev المفقود، ولا يغير تشغيل LAN أو الخادم المركزي.
"""
import os

os.environ.setdefault("DJANGO_ENV", "dev")

from .settings_base import *  # noqa: F401,F403,E402

APP_MODE = os.getenv("APP_MODE", "dev").strip() or "dev"
DEBUG = env_bool("DJANGO_DEBUG", True)
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "training_center_dev_sessionid")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "training_center_dev_csrftoken")
