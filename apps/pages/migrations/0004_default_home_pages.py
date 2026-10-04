"""صفحه اصلی قبلی (ثابت در قالب) ← صفحه قابل مدیریت با همان ۷ بخش و همان متن‌ها، برای همه فروشگاه‌ها."""

from django.db import migrations


def forwards(apps, schema_editor):
    from apps.pages import sections
    from apps.pages.defaults import DEFAULT_HOME_SECTIONS

    Store = apps.get_model("core", "Store")
    Page = apps.get_model("pages", "Page")
    PageSection = apps.get_model("pages", "PageSection")
    for store in Store.objects.all():
        if Page.objects.filter(store=store, is_home=True).exists():
            continue
        page = Page.objects.create(store=store, title="صفحه اصلی", slug="home", is_home=True)
        for i, key in enumerate(DEFAULT_HOME_SECTIONS):
            PageSection.objects.create(page=page, type=key, order=i * 10, settings=sections.get(key).clean_settings({}))


def backwards(apps, schema_editor):
    apps.get_model("pages", "Page").objects.filter(is_home=True, slug="home").delete()


class Migration(migrations.Migration):
    dependencies = [("pages", "0003_page_builder")]
    operations = [migrations.RunPython(forwards, backwards)]
