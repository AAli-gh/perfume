"""انتقال اطلاعات پرداخت از فیلدهای Order به مدل Payment، و ساخت حساب درگاه از تنظیمات قبلی env."""

import os

from django.db import migrations


def forwards(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Payment = apps.get_model("payments", "Payment")
    GatewayAccount = apps.get_model("payments", "GatewayAccount")
    Store = apps.get_model("core", "Store")

    for order in Order.objects.exclude(payment_authority=""):
        gateway = "test" if order.payment_authority.startswith("FAKE") else "zarinpal"
        Payment.objects.get_or_create(
            gateway=gateway,
            authority=order.payment_authority,
            defaults={
                "order": order,
                "amount": order.total,
                "status": "succeeded" if order.paid_at else "pending",
                "ref_id": order.payment_ref_id,
                "verified_at": order.paid_at,
                "message": "منتقل‌شده از نسخه قبل",
            },
        )

    merchant = os.environ.get("ZARINPAL_MERCHANT_ID", "")
    store = Store.objects.filter(is_default=True).first()
    if merchant and store:
        GatewayAccount.objects.get_or_create(
            store=store, gateway="zarinpal",
            defaults={"title": "پرداخت آنلاین (زرین‌پال)", "merchant_id": merchant,
                      "sandbox": os.environ.get("ZARINPAL_SANDBOX", "True").lower() in ("1", "true", "yes")},
        )


def backwards(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Payment = apps.get_model("payments", "Payment")
    for p in Payment.objects.exclude(authority="").order_by("created_at"):
        Order.objects.filter(pk=p.order_id).update(payment_authority=p.authority, payment_ref_id=p.ref_id)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_initial"),
        ("orders", "0004_order_inventory_released_order_reserved_until_and_more"),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
