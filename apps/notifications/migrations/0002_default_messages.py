"""تنظیمات اطلاع‌رسانی و پیام‌های پیش‌فرض برای فروشگاه‌های موجود (تا مدیر قبل از اولین سفارش آن‌ها را ببیند)."""

from django.db import migrations

from apps.notifications.events import DEFAULT_RULES


def create_defaults(apps, schema_editor):
    Store = apps.get_model("core", "Store")
    NotificationSettings = apps.get_model("notifications", "NotificationSettings")
    NotificationRule = apps.get_model("notifications", "NotificationRule")
    for store in Store.objects.all():
        NotificationSettings.objects.get_or_create(store=store)
        NotificationRule.objects.bulk_create(
            [NotificationRule(store=store, event=r.event, channel=r.channel, audience=r.audience,
                              is_active=r.is_active, text=r.text, subject=r.subject) for r in DEFAULT_RULES],
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [("notifications", "0001_initial"), ("core", "0008_image_upload_validators")]
    operations = [migrations.RunPython(create_defaults, migrations.RunPython.noop)]
