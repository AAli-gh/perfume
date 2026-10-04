from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "اطلاع‌رسانی (پیامک و ایمیل)"

    def ready(self):
        from . import receivers, signals, sms  # noqa: F401 — رویدادهای سفارش، فروشگاه جدید، ارائه‌دهندگان پیامک
