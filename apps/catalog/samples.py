"""دکانت (نمونه) و باکس تست.

- دکانت: حجم کوچک یک عطر (ProductVariant.is_decant)؛ هم جدا فروخته می‌شود و هم داخل باکس تست.
- باکس تست: محصولی از نوع SAMPLE_BOX با sample_count؛ حجم ردیف قیمت باکس = حجم هر نمونه. مشتری دقیقاً
  sample_count عطر متفاوت را انتخاب می‌کند و از موجودی دکانت همان عطرها کم می‌شود.
"""

from .models import ProductVariant
from .profile import Kind


class PickError(ValueError):
    pass


def sample_choices(store, size_ml):
    """دکانت‌های موجود با حجم نمونه باکس، برای انتخاب در صفحه باکس تست."""
    return list(
        ProductVariant.objects.filter(
            is_decant=True, size_ml=size_ml, stock__gt=0, product__store=store, product__is_active=True,
            product__kind=Kind.PERFUME,
        ).select_related("product", "product__brand").order_by("product__name")
    )


def validate_picks(box_variant, pick_ids, quantity=1):
    """دکانت‌های انتخاب‌شده برای یک باکس تست، یا PickError با پیام فارسی."""
    product = box_variant.product
    if not product.is_sample_box:
        raise PickError("این محصول باکس تست نیست.")
    try:
        ids = [int(i) for i in pick_ids]
    except (TypeError, ValueError):
        raise PickError("انتخاب نمونه‌ها نامعتبر است.") from None
    if len(ids) != product.sample_count or len(set(ids)) != len(ids):
        raise PickError(f"دقیقاً {product.sample_count} عطر متفاوت انتخاب کنید.")
    picks = {v.pk: v for v in ProductVariant.objects.filter(
        pk__in=ids, is_decant=True, size_ml=box_variant.size_ml, product__store_id=product.store_id,
        product__is_active=True, product__kind=Kind.PERFUME,
    ).select_related("product")}
    if len(picks) != len(ids):
        raise PickError("بعضی از نمونه‌های انتخاب‌شده دیگر در دسترس نیستند.")
    if len({v.product_id for v in picks.values()}) != len(ids):
        raise PickError("از هر عطر فقط یک نمونه انتخاب کنید.")
    short = [v.product.name for v in picks.values() if v.stock < quantity]
    if short:
        raise PickError(f"نمونه «{short[0]}» به این تعداد موجود نیست.")
    return [picks[i] for i in ids]
