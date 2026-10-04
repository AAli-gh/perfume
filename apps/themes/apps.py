from django.apps import AppConfig


class ThemesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.themes"
    label = "themes"
    verbose_name = "ظاهر و پوسته‌ها"

    def ready(self):
        from . import signals  # noqa: F401

