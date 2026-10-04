from django.apps import AppConfig


class ShippingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.shipping"
    label = "shipping"
    verbose_name = "ارسال"

    def ready(self):
        from . import carriers  # noqa: F401 — ثبت شرکت‌های حمل در registry
