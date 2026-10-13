from django.apps import AppConfig


class DiscountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.discounts"
    label = "discounts"
    verbose_name = "تخفیف‌ها"

    def ready(self):
        from . import views  # noqa: F401  گیرنده user_logged_in برای ثبت دوست دعوت‌شده
