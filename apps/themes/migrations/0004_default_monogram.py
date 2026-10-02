"""favicon قبلی حرف «م» (مجد) را نشان می‌داد؛ برای فروشگاه پیش‌فرض حفظ می‌شود (بقیه: حرف اول نام فروشگاه)."""

from django.db import migrations


def forwards(apps, schema_editor):
    ThemeSettings = apps.get_model("themes", "ThemeSettings")
    for s in ThemeSettings.objects.filter(store__is_default=True):
        if not (s.header or {}).get("monogram"):
            s.header = {**(s.header or {}), "monogram": "م"}
            s.save(update_fields=["header"])


class Migration(migrations.Migration):
    dependencies = [("themes", "0003_alter_themesettings_store")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
