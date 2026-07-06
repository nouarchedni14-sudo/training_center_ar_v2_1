import os

ENV = os.getenv("DJANGO_ENV", "dev").strip().lower()

if ENV == "prod":
    from .settings_prod import *
elif ENV == "desktop":
    from .settings_desktop import *
elif ENV == "lan":
    from .settings_lan import *
else:
    from .settings_dev import *
