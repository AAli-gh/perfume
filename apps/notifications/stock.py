"""پیام‌های موجودی: هشدار موجودی کم به مدیران و «موجود شد خبرم کن» به مشتریان."""

from django.utils import timezone

from apps.catalog.models import BackInStockRequest, ProductVariant

from . import events as E
from .models import NotificationLog
from .services import notify_event


def variant_context(variant):
    product = variant.product
    size = "باکس هدیه" if product.is_gift_box else f"{variant.size_ml} میل"
    return {"product": product.name, "size": size, "stock": variant.stock,
            "product_url": product.store.base_url + product.get_absolute_url()}


def alert_low_stock(variant_id):
    variant = ProductVariant.objects.select_related("product__store").filter(pk=variant_id).first()
    if variant is None:
        return 0
    logs = notify_event(variant.product.store, E.LOW_STOCK, variant_context(variant), audiences=(E.STAFF,))
    return sum(entry.status == NotificationLog.SENT for entry in logs)


def notify_back_in_stock(variant_id):
    """هر درخواست باز یک پیامک؛ درخواست فقط با ارسال موفق بسته می‌شود (ناموفق‌ها دفعه بعد دوباره)."""
    variant = ProductVariant.objects.select_related("product__store").filter(pk=variant_id).first()
    if variant is None or variant.stock <= 0:
        return 0
    context = variant_context(variant)
    sent = 0
    for request in BackInStockRequest.objects.filter(variant=variant, notified_at__isnull=True):
        logs = notify_event(variant.product.store, E.BACK_IN_STOCK, context, phone=request.phone,
                            audiences=(E.CUSTOMER,))
        if any(entry.status == NotificationLog.SENT for entry in logs):
            request.notified_at = timezone.now()
            request.save(update_fields=["notified_at"])
            sent += 1
    return sent
