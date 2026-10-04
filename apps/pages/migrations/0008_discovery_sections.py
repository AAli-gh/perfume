"""بخش‌های «پیشنهاد برای شما» و «عطر مناسب من» به صفحه اصلی فروشگاه‌های موجود، بعد از «پرفروش‌ترین‌ها».

هم نسخه منتشرشده و هم پیش‌نویس باز (اگر باشد) به‌روز می‌شوند تا انتشار بعدی آن‌ها را حذف نکند.
تنظیمات خالی ذخیره می‌شود؛ مقادیر پیش‌فرض هنگام نمایش از فرم همان بخش پر می‌شوند.
"""

from django.db import migrations

NEW = ("for_you", "finder_cta")


def add_sections(apps, schema_editor):
    Page = apps.get_model("pages", "Page")
    PageSection = apps.get_model("pages", "PageSection")
    for page in Page.objects.filter(is_home=True):
        for status in ("published", "draft"):
            rows = list(PageSection.objects.filter(page=page, status=status).order_by("order", "id"))
            if not rows or any(r.type in NEW for r in rows):
                continue
            anchor = next((i for i, r in enumerate(rows) if r.type == "best_sellers"), len(rows) - 1)
            insert = [PageSection(page=page, status=status, type=key, settings={}) for key in NEW]
            ordered = rows[:anchor + 1] + insert + rows[anchor + 1:]
            for position, row in enumerate(ordered):
                row.order = position * 10
            PageSection.objects.bulk_create(insert)
            for position, row in enumerate(ordered):
                PageSection.objects.filter(pk=row.pk).update(order=position * 10)


def remove_sections(apps, schema_editor):
    apps.get_model("pages", "PageSection").objects.filter(type__in=NEW, page__is_home=True).delete()


class Migration(migrations.Migration):
    dependencies = [("pages", "0007_image_upload_validators")]
    operations = [migrations.RunPython(add_sections, remove_sections)]
