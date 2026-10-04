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


# ---------- پیش‌نویس و انتشار ----------
# استودیو همیشه نسخه «پیش‌نویس» را ویرایش می‌کند؛ فروشگاه نسخه «منتشرشده» را نشان می‌دهد
# (مگر در حالت پیش‌نمایش). فایل‌های لوگو/فاوآیکون بین دو نسخه مشترک‌اند و هرگز حذف نمی‌شوند.

COPY_FIELDS = ["theme", "preset", "overrides", "logo", "favicon", "header", "footer"]


def _copy(source, target):
    for field in COPY_FIELDS:
        value = getattr(source, field)
        setattr(target, field, dict(value) if isinstance(value, dict) else value)


def draft_settings(store, create=True):
    """نسخه پیش‌نویس ظاهر فروشگاه؛ در اولین ویرایش از روی نسخه منتشرشده ساخته می‌شود."""
    draft = ThemeSettings.objects.select_related("theme", "preset").filter(
        store=store, status=ThemeSettings.Status.DRAFT
    ).first()
    if draft or not create:
        return draft
    published = ensure_store_theme(store)
    if published is None:
        return None
    draft = ThemeSettings(store=store, status=ThemeSettings.Status.DRAFT)
    _copy(published, draft)
    draft.save()
    return draft


def publish_draft(store):
    """پیش‌نویس ← نسخه منتشرشده."""
    from django.utils import timezone

    draft = draft_settings(store, create=False)
    published = ensure_store_theme(store)
    if draft is None or published is None:
        return published
    _copy(draft, published)
    published.published_at = timezone.now()
    published.save()
    return published


def reset_draft(store):
    """کنار گذاشتن تغییرات: پیش‌نویس دوباره برابر نسخه منتشرشده می‌شود."""
    draft = draft_settings(store, create=False)
    published = ensure_store_theme(store)
    if draft is None or published is None:
        return draft
    _copy(published, draft)
    draft.save()
    return draft


# ---------- ویرایش ظاهر (سازنده پوسته) ----------

def editable_settings(store):
    """استودیو فقط پیش‌نویس را تغییر می‌دهد."""
    return draft_settings(store)


def preset_tokens(theme_settings):
    """توکن‌های پایه (پیش‌فرض ← پیش‌تنظیم) بدون شخصی‌سازی فروشگاه."""
    from . import tokens

    preset = theme_settings.preset
    return tokens.merge(tokens.validate(preset.tokens if preset else {}, partial=True))


def apply_preset(theme_settings, preset):
    """انتخاب پیش‌تنظیم؛ شخصی‌سازی رنگ‌ها و توکن‌های قبلی پاک می‌شود تا پیش‌تنظیم کامل دیده شود."""
    if preset.theme_id != theme_settings.theme_id:
        raise ValueError("preset belongs to another theme")
    theme_settings.preset, theme_settings.overrides = preset, {}
    theme_settings.save(update_fields=["preset", "overrides", "updated_at"])


def change_theme(theme_settings, theme):
    if not theme.is_available:
        raise ValueError("theme not available")
    theme_settings.theme = theme
    theme_settings.preset = ThemePreset.objects.filter(theme=theme, is_default=True).first()
    theme_settings.overrides = {}
    theme_settings.save(update_fields=["theme", "preset", "overrides", "updated_at"])


def save_tokens(theme_settings, values):
    """values: توکن‌های کامل یا جزئی ← فقط تفاوت با پیش‌تنظیم به‌عنوان شخصی‌سازی ذخیره می‌شود.

    گروه‌هایی که در values نیامده‌اند، شخصی‌سازی قبلی خود را حفظ می‌کنند.
    """
    from . import tokens

    clean = tokens.validate(values, partial=True)
    base = preset_tokens(theme_settings)
    overrides = {group: dict(vals) for group, vals in (theme_settings.overrides or {}).items()}
    for group, vals in clean.items():
        diff = overrides.get(group, {})
        for key, value in vals.items():
            if base[group].get(key) == value:
                diff.pop(key, None)
            else:
                diff[key] = value
        if diff:
            overrides[group] = diff
        else:
            overrides.pop(group, None)
    theme_settings.overrides = tokens.validate(overrides, partial=True)
    theme_settings.save(update_fields=["overrides", "updated_at"])


def reset_tokens(theme_settings, groups=None):
    overrides = dict(theme_settings.overrides or {})
    for group in groups or list(overrides):
        overrides.pop(group, None)
    theme_settings.overrides = overrides
    theme_settings.save(update_fields=["overrides", "updated_at"])


def save_chrome(theme_settings, part, values):
    """ذخیره بخشی از تنظیمات هدر/فوتر؛ فقط تفاوت با پیش‌فرض نگه داشته می‌شود."""
    from . import chrome

    current = chrome.clean(part, getattr(theme_settings, part) or {})
    merged = chrome.clean(part, {**current, **values})
    defaults = chrome.clean(part, {})
    setattr(theme_settings, part, {k: v for k, v in merged.items() if defaults.get(k) != v})
    theme_settings.save(update_fields=[part, "updated_at"])


def save_branding(theme_settings, *, logo=None, clear_logo=False, favicon=None, clear_favicon=False):
    # فایل قبلی حذف نمی‌شود: در فاز ۸ نسخه پیش‌نویس و منتشرشده می‌توانند فایل مشترک داشته باشند.
    for field, upload, clear in (("logo", logo, clear_logo), ("favicon", favicon, clear_favicon)):
        if upload:
            setattr(theme_settings, field, upload)
        elif clear:
            setattr(theme_settings, field, "")
    theme_settings.save()
