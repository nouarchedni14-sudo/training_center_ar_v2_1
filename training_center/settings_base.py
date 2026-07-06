import os  # استيراد أدوات قراءة متغيرات البيئة من نظام التشغيل.
from pathlib import Path  # استيراد Path لتكوين المسارات بطريقة آمنة وواضحة.

ENV_FILE_PATH = os.getenv("ENV_FILE_PATH", "").strip()
BASE_DIR = Path(__file__).resolve().parent.parent  # هذا هو جذر المشروع الرئيسي.


def _first_existing(paths: list[Path]) -> Path | None:
    for candidate in paths:
        if candidate and candidate.exists():
            return candidate
    return None


def resolve_env_file_path() -> Path:
    if ENV_FILE_PATH:
        return Path(ENV_FILE_PATH)

    django_env = os.getenv("DJANGO_ENV", "").strip().lower()
    app_data_raw = os.getenv("APP_DATA_DIR", "").strip()
    app_data_dir = Path(app_data_raw) if app_data_raw else None

    candidates: list[Path] = []

    # عند أول إقلاع LAN قد لا يكون APP_DATA_DIR محمّلاً بعد من البيئة،
    # لذلك نجرب أيضًا المسار الافتراضي المعروف على ويندوز.
    default_lan_app_data_dir = Path("C:/TrainingCenterData") if django_env == "lan" else None

    if app_data_dir:
        candidates.append(app_data_dir / ".env")
        candidates.append(app_data_dir / ".env.lan")

    if default_lan_app_data_dir:
        candidates.append(default_lan_app_data_dir / ".env")
        candidates.append(default_lan_app_data_dir / ".env.lan")

    if django_env == "lan":
        candidates.append(BASE_DIR / ".env.lan")
    candidates.append(BASE_DIR / ".env")

    chosen = _first_existing(candidates)
    if chosen:
        return chosen

    fallback_dir = app_data_dir or default_lan_app_data_dir
    if fallback_dir:
        return fallback_dir / (".env.lan" if django_env == "lan" else ".env")
    return BASE_DIR / (".env.lan" if django_env == "lan" else ".env")


try:  # نحاول تحميل ملف .env المناسب حسب وضع التشغيل.
    from dotenv import load_dotenv  # استيراد الدالة المسؤولة عن قراءة ملف .env.
    load_dotenv(resolve_env_file_path(), override=True)  # تحميل ملف .env مع إعطائه أولوية على أي متغيرات قديمة.
except Exception:  # إذا لم تكن المكتبة مثبّتة فلا نوقف المشروع.
    pass  # نتجاهل الخطأ لأن Django يستطيع القراءة من متغيرات النظام مباشرة.


APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", "").strip()) if os.getenv("APP_DATA_DIR", "").strip() else None


def env_bool(name: str, default: bool = False) -> bool:
    """قراءة قيمة من متغيرات البيئة وتحويلها إلى True/False بشكل موحد."""
    value = os.getenv(name)  # قراءة النص الخام من متغيرات البيئة.
    if value is None:  # لو لم توجد القيمة نرجع الافتراضي.
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}  # تحويل الصيغ الشائعة إلى قيمة منطقية.


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key-change-me")  # المفتاح السري؛ يجب تغييره في الإنتاج.
DEBUG = env_bool("DJANGO_DEBUG", False)  # التفعيل الافتراضي هنا مغلق من أجل الأمان.

raw_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")  # قائمة المضيفين المسموحين مفصولة بفواصل.
ALLOWED_HOSTS = [host.strip() for host in raw_hosts.split(",") if host.strip()]  # تحويل النص إلى قائمة نظيفة.

# إعدادات المزامنة بين المكاتب.
# المرحلة 1: هوية المكتب والخادم المحلي.
# المرحلة 2: جداول صندوق الإرسال والاستقبال.
# المرحلة 3: تسجيل التغييرات المحلية تلقائيًا داخل SyncOutbox.
SYNC_MODE = os.getenv("SYNC_MODE", "local_office").strip() or "local_office"
OFFICE_ID = os.getenv("OFFICE_ID", "").strip()
OFFICE_CODE = os.getenv("OFFICE_CODE", "").strip()
OFFICE_ALIAS = os.getenv("OFFICE_ALIAS", "").strip()
OFFICE_NAME = os.getenv("OFFICE_NAME", "").strip()
OFFICE_DISPLAY_NAME = os.getenv("OFFICE_DISPLAY_NAME", OFFICE_NAME).strip()
WILAYA_CODE = os.getenv("WILAYA_CODE", "").strip()
COMMUNE_CODE = os.getenv("COMMUNE_CODE", "").strip()
INSTITUTION_TYPE = os.getenv("INSTITUTION_TYPE", os.getenv("ESTABLISHMENT_TYPE", "")).strip()
INSTITUTION_SERIAL = os.getenv("INSTITUTION_SERIAL", os.getenv("ESTABLISHMENT_NUMBER", "")).strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()
SYNC_TOKEN = os.getenv("SYNC_TOKEN", "").strip()
CENTRAL_URL = os.getenv("CENTRAL_URL", "").strip().rstrip("/")
# رابط عام اختياري للخادم المركزي عند نشره على الإنترنت أو خلف Reverse Proxy.
# مثال: https://updates.example.com
CENTRAL_PUBLIC_URL = (
    os.getenv("CENTRAL_PUBLIC_URL")
    or os.getenv("CENTRAL_PUBLIC_BASE_URL")
    or ""
).strip().rstrip("/")
CENTRAL_SYNC_ENABLED = env_bool("CENTRAL_SYNC_ENABLED", False)
SYNC_BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "100"))
SYNC_PULL_LIMIT = int(os.getenv("SYNC_PULL_LIMIT", "100"))
SYNC_CONFLICT_POLICY = os.getenv("SYNC_CONFLICT_POLICY", "last_write_wins").strip() or "last_write_wins"
SYNC_TRACKING_ENABLED = env_bool("SYNC_TRACKING_ENABLED", False)
SYNC_AUDIT_OUTBOX_ENABLED = env_bool("SYNC_AUDIT_OUTBOX_ENABLED", True)
OFFICE_PULL_TOKEN = os.getenv("OFFICE_PULL_TOKEN", SYNC_TOKEN).strip()
# أسماء النماذج التي نسجل تغييراتها في SyncOutbox، مفصولة بفواصل.
# عدّلها بعد تشغيل: python manage.py list_sync_candidate_models --settings=training_center.settings_lan
SYNC_TRACKED_MODELS = [
    item.strip()
    for item in os.getenv("SYNC_TRACKED_MODELS", "trainees.Specialty,trainees.Trainee").split(",")
    if item.strip()
]

# المرحلة 4: إعدادات الخادم المركزي وواجهات API.
CENTRAL_SYNC_API_ENABLED = env_bool("CENTRAL_SYNC_API_ENABLED", False)
# Phase 5 - local office sync worker settings
SYNC_WORKER_ENABLED = env_bool("SYNC_WORKER_ENABLED", False)
SYNC_WORKER_INTERVAL_SECONDS = int(os.getenv("SYNC_WORKER_INTERVAL_SECONDS", "300"))
SYNC_WORKER_HTTP_TIMEOUT = int(os.getenv("SYNC_WORKER_HTTP_TIMEOUT", "20"))
SYNC_WORKER_MAX_ATTEMPTS = int(os.getenv("SYNC_WORKER_MAX_ATTEMPTS", "10"))
SYNC_WORKER_PUSH_FAILED = env_bool("SYNC_WORKER_PUSH_FAILED", True)
# Phase 6 - apply received remote events and record conflicts
SYNC_APPLY_INBOX_ENABLED = env_bool("SYNC_APPLY_INBOX_ENABLED", True)
SYNC_APPLY_LIMIT = int(os.getenv("SYNC_APPLY_LIMIT", os.getenv("SYNC_PULL_LIMIT", "100")))

CENTRAL_AUTO_REGISTER_OFFICES = env_bool("CENTRAL_AUTO_REGISTER_OFFICES", False)
CENTRAL_LATEST_VERSION = os.getenv("CENTRAL_LATEST_VERSION", os.getenv("APP_VERSION", "1.0.0")).strip()
CENTRAL_UPDATE_DOWNLOAD_URL = os.getenv("CENTRAL_UPDATE_DOWNLOAD_URL", "").strip()
CENTRAL_UPDATE_NOTES = os.getenv("CENTRAL_UPDATE_NOTES", "").strip()
# Phase 8 - central update management
CENTRAL_DEFAULT_UPDATE_CHANNEL = os.getenv("CENTRAL_DEFAULT_UPDATE_CHANNEL", os.getenv("UPDATE_CHANNEL", "stable")).strip() or "stable"

UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", "stable").strip().lower() or "stable"  # قناة التحديث الحالية: stable أو beta.
UPDATE_SHA256_REQUIRED = env_bool("UPDATE_SHA256_REQUIRED", True)  # هل التحقق من sha256 إلزامي للتحديثات البعيدة؟
UPDATE_SIGNATURE_REQUIRED = env_bool("UPDATE_SIGNATURE_REQUIRED", False)  # هل التوقيع الإلزامي مفعل؟
UPDATE_SIGNING_KEY = os.getenv("UPDATE_SIGNING_KEY", "")  # مفتاح HMAC داخلي للتحقق من ملف latest.json.

INSTALLED_APPS = [  # التطبيقات المفعلة داخل Django.
    "django.contrib.admin",  # لوحة الإدارة الجاهزة من Django.
    "django.contrib.auth",  # نظام المستخدمين وكلمات المرور.
    "django.contrib.contenttypes",  # إدارة أنواع النماذج داخليًا.
    "django.contrib.sessions",  # دعم الجلسات للمستخدمين.
    "django.contrib.messages",  # نظام رسائل النجاح والخطأ.
    "django.contrib.staticfiles",  # خدمة الملفات الثابتة مثل CSS و JS.
    "django.forms",  # دعم مكونات النماذج.
    "trainees",  # تطبيق المتربصين/المستخدمين.
    "core",  # تطبيق الإعدادات والخدمات الأساسية.
    "sync_core.apps.SyncCoreConfig",  # المزامنة: الهوية + الجداول + تسجيل التغييرات المحلية.
]

MIDDLEWARE = [  # طبقات المعالجة التي تمر عليها كل طلبات الموقع.
    "django.middleware.security.SecurityMiddleware",  # يضيف طبقة حماية أساسية للرؤوس الأمنية والـ SSL.
    "django.contrib.sessions.middleware.SessionMiddleware",  # تمكين الجلسات.
    "django.middleware.locale.LocaleMiddleware",  # تفعيل اللغة/الترجمة حسب الإعدادات.
    "trainees.middleware.ForceArabicAdminMiddleware",  # إجبار واجهة الإدارة على العربية حسب منطق المشروع.
    "django.middleware.common.CommonMiddleware",  # تحسينات عامة للطلبات والروابط.
    "django.middleware.csrf.CsrfViewMiddleware",  # حماية نماذج POST من هجمات CSRF.
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # ربط المستخدم الحالي بكل طلب.
    "trainees.middleware.RequestAuditMiddleware",  # سجل شامل لكل شاشة وعملية على مستوى الطلب.
    "core.license_middleware.LicenseEnforcementMiddleware",  # منع الاستخدام عند انتهاء الترخيص مع السماح بصفحات النظام الأساسية.
    "django.contrib.messages.middleware.MessageMiddleware",  # إظهار رسائل للمستخدم داخل الصفحات.
    "core.middleware.SystemErrorLoggingMiddleware",  # تسجيل أخطاء النظام داخل السجلات.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # حماية الصفحات من التحميل داخل iframe خبيث.
]

ROOT_URLCONF = "training_center.urls"  # ملف المسارات الرئيسي.
WSGI_APPLICATION = "training_center.wsgi.application"  # نقطة تشغيل WSGI للإنتاج.
ASGI_APPLICATION = "training_center.asgi.application"  # نقطة تشغيل ASGI عند الحاجة.
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"  # جعل النماذج تستخدم قوالب المشروع.

TEMPLATES = [  # إعداد محرك القوالب.
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",  # استخدام محرك Django القياسي.
        "DIRS": [BASE_DIR / "templates"],  # مجلد القوالب العام في المشروع وله أولوية على قوالب التطبيقات.
        "APP_DIRS": True,  # السماح بقراءة مجلد templates داخل كل تطبيق.
        "OPTIONS": {
            "context_processors": [  # هذه الدوال تضيف بيانات عامة لكل القوالب.
                "django.template.context_processors.debug",  # يضيف معلومات Debug عند التفعيل.
                "django.template.context_processors.request",  # يمرر كائن الطلب إلى القوالب.
                "django.contrib.auth.context_processors.auth",  # يمرر المستخدم الحالي والصلاحيات.
                "django.contrib.messages.context_processors.messages",  # يمرر رسائل Django.
                "trainees.context_processors.ui_permissions",  # يضيف صلاحيات الواجهة من التطبيق.
                "core.context_processors.system_status",  # يضيف حالة النظام للقوالب.
                "core.context_processors.central_navigation",  # روابط لوحة المطور المركزية داخل واجهة المكتب المحلي.
            ]
        },
    }
]

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()  # نحدد نوع قاعدة البيانات من البيئة.
if DB_ENGINE in {"postgres", "postgresql"}:  # إذا طلبنا PostgreSQL نستخدم إعداداته.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",  # محرك PostgreSQL داخل Django.
            "NAME": os.getenv("POSTGRES_DB", "training_center"),  # اسم قاعدة البيانات.
            "USER": os.getenv("POSTGRES_USER", "postgres"),  # اسم المستخدم.
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),  # كلمة مرور قاعدة البيانات.
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),  # عنوان الخادم.
            "PORT": os.getenv("POSTGRES_PORT", "5432"),  # منفذ PostgreSQL الافتراضي.
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),  # إبقاء الاتصال مفتوحًا قليلًا لتحسين الأداء.
        }
    }
else:  # في غير ذلك نستعمل SQLite لتسهيل التطوير المحلي.
    sqlite_name = os.getenv("SQLITE_NAME", "db.sqlite3").strip() or "db.sqlite3"
    sqlite_path = Path(sqlite_name)
    if not sqlite_path.is_absolute():
        sqlite_path = (APP_DATA_DIR / sqlite_path) if APP_DATA_DIR else (BASE_DIR / sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",  # محرك SQLite.
            "NAME": sqlite_path,  # اسم ملف قاعدة البيانات المحلية.
        }
    }

AUTH_PASSWORD_VALIDATORS = [  # قواعد قوة كلمة المرور.
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},  # يمنع التشابه الكبير مع اسم المستخدم.
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},  # يفرض حدًا أدنى للطول.
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},  # يمنع الكلمات الشائعة.
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},  # يمنع كلمات المرور الرقمية فقط.
]

LANGUAGE_CODE = "ar"  # اللغة الافتراضية للتطبيق.
TIME_ZONE = "Africa/Algiers"  # المنطقة الزمنية الأساسية.
USE_I18N = True  # تفعيل الترجمة.
USE_TZ = True  # تخزين التواريخ بشكل واعٍ بالمنطقة الزمنية.
USE_L10N = False  # إبقاء تنسيقاتنا المحددة بدل التنسيق المحلي التلقائي.

LANGUAGES = [("ar", "العربية")]  # اللغات المدعومة فعليًا.
DATE_INPUT_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]  # الصيغ المسموح بها لإدخال التاريخ.
DATE_FORMAT = "Y-m-d"  # صيغة العرض الأساسية للتاريخ.
SHORT_DATE_FORMAT = "Y-m-d"  # الصيغة المختصرة للتاريخ.

STATIC_URL = "/static/"  # الرابط المنطقي المطلق للملفات الثابتة.
STATIC_ROOT = (APP_DATA_DIR / "staticfiles") if APP_DATA_DIR else (BASE_DIR / "staticfiles")  # مجلد تجميع static حسب وضع التشغيل.
STATICFILES_DIRS = []  # نتركها فارغة الآن لأن التطبيق يعتمد على static داخل التطبيقات.
MEDIA_URL = "/media/"  # الرابط المنطقي المطلق للملفات المرفوعة.
MEDIA_ROOT = (APP_DATA_DIR / "media") if APP_DATA_DIR else (BASE_DIR / "media")  # مكان حفظ الملفات المرفوعة.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"  # النوع الافتراضي للمعرفات الجديدة.

LOGIN_URL = "/accounts/login/"  # صفحة تسجيل الدخول الافتراضية.
LOGIN_REDIRECT_URL = "/"  # الوجهة بعد نجاح تسجيل الدخول.
LOGOUT_REDIRECT_URL = "/accounts/login/"  # الوجهة بعد تسجيل الخروج.

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")  # إصدار التطبيق المعروض داخليًا.
APP_MODE = os.getenv("APP_MODE", "lan_server").strip()  # نمط التشغيل: محلي/شبكة/سطح مكتب.
ALLOW_REMOTE_UPDATES = env_bool("ALLOW_REMOTE_UPDATES", False)  # هل التحديثات البعيدة مفعلة؟
DEVELOPER_SUPPORT_ENABLED = env_bool("DEVELOPER_SUPPORT_ENABLED", False)  # هل دعم المطور مفعل؟
UPDATE_SERVER_URL = os.getenv("UPDATE_SERVER_URL", "").strip()  # رابط خادم التحديث عند وجوده.
CENTRAL_TRAINEE_MANAGER_URL = os.getenv("CENTRAL_TRAINEE_MANAGER_URL", "http://127.0.0.1:8000/developer/login/").strip()  # رابط برنامج تسيير المتكوّنين من لوحة المطور المركزية.
CENTRAL_DASHBOARD_URL = os.getenv("CENTRAL_DASHBOARD_URL", "http://127.0.0.1:9000/central/").strip()  # رابط زر الرجوع إلى لوحة المطور المركزية داخل برنامج تسيير المتكوّنين.

SECURE_BROWSER_XSS_FILTER = True  # تفعيل تلميح حماية XSS للمتصفحات القديمة.
SECURE_CONTENT_TYPE_NOSNIFF = True  # منع المتصفح من تخمين نوع الملف بطريقة غير آمنة.
X_FRAME_OPTIONS = "DENY"  # منع تضمين الصفحات داخل iframe خارجي.
REFERRER_POLICY = "same-origin"  # تقليل تسريب عنوان الصفحة المحيلة.
# عند تشغيل البرنامج خلف نطاق إنترنت/HTTPS عبر Nginx أو Cloudflare أو أي Reverse Proxy
# يجب تفعيل BEHIND_REVERSE_PROXY=1 حتى يفهم Django أن الطلب الأصلي كان HTTPS
# ويولّد روابط تنزيل التحديثات والمزامنة بالرابط العام الصحيح.
BEHIND_REVERSE_PROXY = env_bool("BEHIND_REVERSE_PROXY", False)
if BEHIND_REVERSE_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    USE_X_FORWARDED_PORT = True
SESSION_COOKIE_HTTPONLY = True  # منع JavaScript من قراءة كوكي الجلسة.
CSRF_COOKIE_HTTPONLY = True  # جعل كوكي CSRF غير متاحة لـ JavaScript.
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(60 * 60 * 8)))  # مدة الجلسة الافتراضية: 8 ساعات.
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", False)  # خيار إنهاء الجلسة عند إغلاق المتصفح.

LOG_DIR = (APP_DATA_DIR / "logs") if APP_DATA_DIR else (BASE_DIR / "logs")  # مجلد حفظ ملفات السجلات.
LOG_DIR.mkdir(parents=True, exist_ok=True)  # إنشاء مجلد السجلات تلقائيًا إن لم يكن موجودًا.

LOGGING = {  # إعداد السجلات ليسهل تتبع الأخطاء والعمليات.
    "version": 1,  # إصدار مخطط إعداد السجلات في Django/Python.
    "disable_existing_loggers": False,  # لا تعطل السجلات الافتراضية.
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",  # شكل السطر داخل ملف السجل.
            "style": "{",  # استعمال تنسيق الأقواس الحديثة.
        }
    },
    "handlers": {
        "file": {
            "class": "logging.FileHandler",  # حفظ السجلات في ملف.
            "filename": LOG_DIR / "application.log",  # اسم ملف السجل الرئيسي.
            "formatter": "verbose",  # استعمال التنسيق المفصل أعلاه.
            "encoding": "utf-8",  # دعم اللغة العربية داخل السجل.
        },
        "console": {
            "class": "logging.StreamHandler",  # إرسال السجلات أيضًا إلى الطرفية.
            "formatter": "verbose",  # نفس تنسيق السطر.
        },
    },
    "root": {
        "handlers": ["file", "console"],  # ربط السجلات الجذرية بكل من الملف والطرفية.
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),  # مستوى السجلات يمكن تغييره من البيئة.
    },
}

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")  # في البداية نرسل البريد إلى الطرفية للتجربة.
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@training-center.local")  # عنوان البريد الافتراضي للتنبيهات.

LICENSE_ENFORCEMENT_ENABLED = env_bool("LICENSE_ENFORCEMENT_ENABLED", True)  # تفعيل فرض التحقق من الترخيص على الواجهات الرئيسية.


# رفع الحد لتفادي خطأ TooManyFieldsSent عند العمليات الإدارية الكبيرة
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

DESKTOP_BOOTSTRAP_DEVELOPER = env_bool("DESKTOP_BOOTSTRAP_DEVELOPER", False)  # إنشاء حساب مطور تلقائي فقط عند الطلب الصريح.
