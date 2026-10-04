"""بررسی‌های check --deploy مخصوص این پروژه."""

from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def cache_is_shared(app_configs, **kwargs):
    backend = settings.CACHES["default"]["BACKEND"]
    if "locmem" in backend.lower() or "dummy" in backend.lower():
        return [Warning(
            "cache اشتراکی (Redis) تنظیم نشده است؛ محدودیت تعداد درخواست و cache بین workerها مشترک نیست.",
            hint="REDIS_URL را تنظیم کنید.", id="majd.W001",
        )]
    return []
