"""پوسته فعال در چرخه درخواست.

ThemeMiddleware (بعد از StoreMiddleware) تنظیمات ظاهر منتشرشده فروشگاه را پیدا می‌کند و کد پوسته را در یک
ContextVar قرار می‌دهد تا Template Loader بداند قالب‌ها را از کدام پوشه بخواند.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings

_active_theme = ContextVar("active_theme", default=None)


def default_theme_code():
    return getattr(settings, "DEFAULT_THEME", "luxury")


def get_active_theme_code():
    return _active_theme.get() or default_theme_code()


@contextmanager
def use_theme(code):
    token = _active_theme.set(code)
    try:
        yield code
    finally:
        _active_theme.reset(token)


def published_settings(store):
    from .models import ThemeSettings

    if store is None:
        return None
    return (
        ThemeSettings.objects.select_related("theme", "preset")
        .filter(store=store, status=ThemeSettings.Status.PUBLISHED, theme__is_available=True)
        .first()
    )


class ThemeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.theme_settings = published_settings(getattr(request, "store", None))
        code = request.theme_settings.theme.code if request.theme_settings else default_theme_code()
        with use_theme(code):
            return self.get_response(request)
