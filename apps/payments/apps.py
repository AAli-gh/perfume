from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    label = "payments"
    verbose_name = "پرداخت‌ها"

    def ready(self):
        from apps.orders.integration import register_online_payment_provider

        from . import gateways  # noqa: F401 — ثبت درگاه‌ها در registry
        from .services import online_payment_available

        register_online_payment_provider(online_payment_available)
