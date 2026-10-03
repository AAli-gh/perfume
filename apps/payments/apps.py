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

        # انتقال به درگاه پس از ارسال فرم تسویه حساب ← دامنه درگاه باید در CSP form-action مجاز باشد
        from apps.core.security import add_source

        from .gateways import get_gateway_class, registered_codes

        for code in registered_codes():
            add_source("form-action", *get_gateway_class(code).redirect_origins)
