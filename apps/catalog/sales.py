"""حراج زمان‌دار: قیمت حراج روی خود حجم‌ها (قبل و بعد تخفیف در سایت نمایش داده می‌شود).

ساختن حراج گروهی، قیمت حراج هر حجم را از قیمت اصلی آن و درصد تخفیف (با گرد کردن) حساب می‌کند. حراج در زمان
شروع خودبه‌خود فعال و در زمان پایان خودبه‌خود غیرفعال می‌شود (قیمت فعلی در هر درخواست از روی زمان حساب می‌شود؛
کار زمان‌بندی‌شده‌ای لازم نیست).
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .bulk import PriceRule
from .models import ProductVariant, SaleCampaign
from .smart_search import invalidate_vocab


def sale_price_for(price, percent, rounding=0):
    rule = PriceRule("percent", -Decimal(percent), rounding)
    new = rule.apply(price)
    return new if new < price else None


@transaction.atomic
def create_campaign(store, variants, *, name, percent, starts_at=None, ends_at=None, rounding=0, user=None):
    """خروجی: (حراج، تعداد حجم‌ها، تعداد حجم‌هایی که حراج قبلی‌شان جایگزین شد)."""
    campaign = SaleCampaign.objects.create(store=store, name=name[:100], percent=percent, starts_at=starts_at,
                                           ends_at=ends_at, created_by=user if user and user.is_authenticated else None)
    applied = replaced = 0
    for variant in variants.select_for_update():
        sale = sale_price_for(variant.price, percent, rounding)
        if sale is None:
            continue
        if variant.sale_price is not None and (variant.sale_ends_at is None or variant.sale_ends_at > timezone.now()):
            replaced += 1
        ProductVariant.objects.filter(pk=variant.pk).update(
            sale_price=sale, sale_starts_at=starts_at, sale_ends_at=ends_at, sale_campaign=campaign)
        applied += 1
    transaction.on_commit(lambda: invalidate_vocab(store.pk))
    return campaign, applied, replaced


@transaction.atomic
def end_campaign(campaign):
    """پایان فوری حراج: قیمت حراج حجم‌های همین حراج پاک می‌شود."""
    count = ProductVariant.objects.filter(sale_campaign=campaign).update(
        sale_price=None, sale_starts_at=None, sale_ends_at=None, sale_campaign=None)
    campaign.ended_at = timezone.now()
    campaign.save(update_fields=["ended_at"])
    transaction.on_commit(lambda: invalidate_vocab(campaign.store_id))
    return count
