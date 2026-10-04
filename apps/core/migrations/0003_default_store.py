"""ساخت فروشگاه پیش‌فرض از روی تنظیمات قبلی (SITE_INFO و هزینه ارسال در settings/env)."""

from django.conf import settings
from django.db import migrations

DEFAULTS = {
    "name": "عطر مجد",
    "tagline": "خانه عطرهای لوکس و دست‌ساز",
    "phone": "۰۲۱-۱۲۳۴۵۶۷۸",
    "phone_link": "+982112345678",
    "email": "info@atremajd.ir",
    "address": "تهران، خیابان ولیعصر، پلاک ۱۲۳",
    "instagram": "#",
    "telegram": "#",
    "whatsapp": "#",
}


def create_default_store(apps, schema_editor):
    Store = apps.get_model("core", "Store")
    StoreSettings = apps.get_model("core", "StoreSettings")
    if Store.objects.filter(is_default=True).exists():
        return
    info = {**DEFAULTS, **getattr(settings, "SITE_INFO", {})}
    store = Store.objects.create(name=info["name"], code="default", is_default=True)
    StoreSettings.objects.create(
        store=store,
        tagline=info["tagline"],
        email=info["email"],
        phone=info["phone"],
        phone_link=info["phone_link"],
        address=info["address"],
        instagram_url="" if info["instagram"] == "#" else info["instagram"],
        telegram_url="" if info["telegram"] == "#" else info["telegram"],
        whatsapp_url="" if info["whatsapp"] == "#" else info["whatsapp"],
        shipping_cost=getattr(settings, "SHIPPING_COST", 150_000),
        free_shipping_over=getattr(settings, "FREE_SHIPPING_OVER", 0),
        bank_card_number="۶۰۳۷-۹۹۰۰-۰۰۰۰-۰۰۰۰",
        bank_card_holder="عطر مجد",
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0002_stores")]
    operations = [migrations.RunPython(create_default_store, migrations.RunPython.noop)]
