"""ثبت پوسته‌های روی دیسک و انتخاب پوسته پیش‌فرض (لاکچری / طلایی) برای فروشگاه‌های موجود."""

from django.conf import settings
from django.db import migrations


def forwards(apps, schema_editor):
    from apps.themes.registry import sync

    Theme = apps.get_model("themes", "Theme")
    ThemePreset = apps.get_model("themes", "ThemePreset")
    ThemeSettings = apps.get_model("themes", "ThemeSettings")
    Store = apps.get_model("core", "Store")

    sync(Theme, ThemePreset)
    theme = Theme.objects.filter(code=getattr(settings, "DEFAULT_THEME", "luxury")).first()
    if theme is None:
        return
    preset = ThemePreset.objects.filter(theme=theme, is_default=True).first()
    for store in Store.objects.all():
        ThemeSettings.objects.get_or_create(store=store, status="published", defaults={"theme": theme, "preset": preset})


class Migration(migrations.Migration):
    dependencies = [("themes", "0001_initial"), ("core", "0005_storesettings_currency_label_and_more")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
