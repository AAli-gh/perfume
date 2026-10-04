from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "هسته"

    def ready(self):
        from . import checks, signals  # noqa: F401 — بررسی‌های deploy و ثبت رویدادهای ورود/خروج در AuditLog
