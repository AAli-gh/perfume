from django.conf import settings

from .models import Theme, ThemePreset, ThemeSettings


def ensure_store_theme(store):
    """هر فروشگاه دست‌کم یک تنظیمات ظاهر منتشرشده دارد (پوسته پیش‌فرض)."""
    existing = ThemeSettings.objects.filter(store=store, status=ThemeSettings.Status.PUBLISHED).first()
    if existing:
        return existing
    theme = Theme.objects.filter(code=settings.DEFAULT_THEME, is_available=True).first()
    if theme is None:
        return None
    preset = ThemePreset.objects.filter(theme=theme, is_default=True).first()
    return ThemeSettings.objects.create(store=store, status=ThemeSettings.Status.PUBLISHED, theme=theme, preset=preset)
