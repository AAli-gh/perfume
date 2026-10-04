"""ابزارهای مشترک migration برای جابه‌جایی مدل بین اپ‌ها بدون تغییر جدول."""

from django.db import migrations


def move_content_type(old_app, new_app, model):
    """ContentType مدل را به اپ جدید منتقل می‌کند تا مجوزها و تاریخچه Admin حفظ شوند."""

    def move(apps, source, target):
        ContentType = apps.get_model("contenttypes", "ContentType")
        if not ContentType.objects.filter(app_label=source, model=model).exists():
            return
        # ممکن است post_migrate قبلاً یک ContentType تازه (و خالی) برای مقصد ساخته باشد؛
        # نسخه قدیمی را نگه می‌داریم چون مجوزها و تاریخچه Admin به آن اشاره می‌کنند.
        ContentType.objects.filter(app_label=target, model=model).delete()
        ContentType.objects.filter(app_label=source, model=model).update(app_label=target)

    return migrations.RunPython(
        lambda apps, schema_editor: move(apps, old_app, new_app),
        lambda apps, schema_editor: move(apps, new_app, old_app),
    )


def assign_default_store(app_label, *model_names):
    """رکوردهای موجود را به فروشگاه پیش‌فرض نسبت می‌دهد (قبل از اجباری شدن فیلد store)."""

    def forwards(apps, schema_editor):
        Store = apps.get_model("core", "Store")
        store = Store.objects.filter(is_default=True).first()
        if store is None:
            store = Store.objects.create(name="فروشگاه", code="default", is_default=True)
        for name in model_names:
            apps.get_model(app_label, name).objects.filter(store__isnull=True).update(store=store)

    return migrations.RunPython(forwards, migrations.RunPython.noop)
