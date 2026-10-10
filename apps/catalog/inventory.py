"""سرویس موجودی انبار.

همه تغییرات موجودی از این ماژول عبور می‌کنند تا:
- رزرو با قفل ردیف (select_for_update) انجام شود و موجودی منفی نشود؛
- هر تغییر در StockMovement ثبت شود (قابل حسابرسی؛ جمع تغییرات = موجودی).
"""

from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F

from . import events
from .models import ProductVariant, StockMovement


class OutOfStock(Exception):
    def __init__(self, names):
        self.names = names
        super().__init__("، ".join(names))


@dataclass(frozen=True)
class StockLine:
    variant_id: int
    quantity: int


def lock_variants(variant_ids):
    """قفل ردیف‌های حجم‌ها تا پایان تراکنش جاری؛ dict[id] = ProductVariant."""
    qs = ProductVariant.objects.select_for_update().select_related("product").filter(pk__in=list(variant_ids))
    return {v.pk: v for v in qs.order_by("pk")}  # ترتیب ثابت قفل‌ها از بن‌بست جلوگیری می‌کند


@transaction.atomic
def reserve(lines, reference, user=None):
    """کم کردن موجودی برای یک سفارش؛ اگر هر قلمی کافی نباشد هیچ تغییری اعمال نمی‌شود."""
    variants = lock_variants(line.variant_id for line in lines)
    short = [
        f"{variants[line.variant_id].product.name} ({variants[line.variant_id].size_ml} میل)"
        for line in lines
        if line.variant_id not in variants or variants[line.variant_id].stock < line.quantity
    ]
    if short:
        raise OutOfStock(short)
    for line in lines:
        _apply(line.variant_id, -line.quantity, StockMovement.Reason.RESERVED, reference, user)
    return variants


@transaction.atomic
def release(lines, reference, user=None, note=""):
    """برگرداندن موجودی رزروشده (لغو سفارش یا انقضای مهلت پرداخت)."""
    lock_variants(line.variant_id for line in lines)
    for line in lines:
        _apply(line.variant_id, line.quantity, StockMovement.Reason.RELEASED, reference, user, note)


@transaction.atomic
def set_stock(variant, new_stock, user=None, note="", reason=StockMovement.Reason.ADJUSTMENT):
    """تنظیم دستی موجودی (مثلاً از پنل مدیریت) همراه با ثبت اختلاف در دفتر موجودی."""
    current = ProductVariant.objects.select_for_update().get(pk=variant.pk).stock
    if new_stock != current:
        _apply(variant.pk, new_stock - current, reason, "", user, note)
    variant.stock = new_stock


def record_initial(variant, user=None):
    if variant.stock:
        StockMovement.objects.create(variant=variant, change=variant.stock, reason=StockMovement.Reason.INITIAL, created_by=user)


def _apply(variant_id, change, reason, reference, user=None, note=""):
    ProductVariant.objects.filter(pk=variant_id).update(stock=F("stock") + change)
    StockMovement.objects.create(
        variant_id=variant_id, change=change, reason=reason, reference=reference, created_by=user, note=note
    )
    _announce(variant_id, change)


def threshold_for(variant):
    if variant.low_stock_threshold is not None:
        return variant.low_stock_threshold
    try:
        return variant.product.store.config.low_stock_threshold
    except ObjectDoesNotExist:  # فروشگاه بدون تنظیمات (فقط در تست‌ها)
        return 3


def _announce(variant_id, change):
    """عبور از آستانه موجودی کم (رو به پایین) یا از صفر (رو به بالا) ← رویداد پس از commit."""
    variant = ProductVariant.objects.select_related("product__store").get(pk=variant_id)
    after, before = variant.stock, variant.stock - change
    if change < 0 and before > threshold_for(variant) >= after:
        transaction.on_commit(lambda: events.stock_low.send(sender=ProductVariant, variant_id=variant_id, stock=after))
    elif change > 0 and before <= 0 < after:
        transaction.on_commit(lambda: events.back_in_stock.send(sender=ProductVariant, variant_id=variant_id,
                                                                stock=after))
