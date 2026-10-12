from django.apps import AppConfig


class CartConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cart"
    label = "cart"
    verbose_name = "سبد"

    def ready(self):
        from . import signals  # noqa: F401 — بازگرداندن سبد ذخیره‌شده پس از ورود
