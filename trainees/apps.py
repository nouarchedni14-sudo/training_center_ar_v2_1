from django.apps import AppConfig


class TraineesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "trainees"
    verbose_name = "تسيير تعداد المتكوّنين"

    def ready(self):
        from . import signals  # noqa: F401
