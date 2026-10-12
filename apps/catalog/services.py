"""سرویس‌های نوشتنی کاتالوگ."""

from django.db import transaction
from django.utils.text import slugify

from .models import FragranceNote, ProductNote
from .search import reindex_products


def get_or_create_note(store, name):
    name = name.strip()
    slug = slugify(name, allow_unicode=True)
    note, _ = FragranceNote.objects.get_or_create(store=store, slug=slug, defaults={"name": name})
    return note


@transaction.atomic
def set_product_notes(product, top=(), heart=(), base=()):
    """جایگزینی کامل هرم بویایی محصول با فهرست نام نت‌ها در هر لایه."""
    product.notes.all().delete()
    links = []
    for layer, names in ((ProductNote.Layer.TOP, top), (ProductNote.Layer.HEART, heart), (ProductNote.Layer.BASE, base)):
        for order, name in enumerate(n for n in names if n and n.strip()):
            links.append(ProductNote(product=product, note=get_or_create_note(product.store, name), layer=layer, order=order))
    ProductNote.objects.bulk_create(links)
    reindex_products([product.pk])  # bulk_create سیگنال post_save ندارد
    return links


def request_back_in_stock(variant, phone, user=None):
    """ثبت «موجود شد خبرم کن»؛ تکراری بودن درخواست باز همان شماره خطا نیست. خروجی: (درخواست، تازه؟)."""
    from django.db import IntegrityError, transaction

    from .models import BackInStockRequest

    existing = BackInStockRequest.objects.filter(variant=variant, phone=phone, notified_at__isnull=True).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            return BackInStockRequest.objects.create(variant=variant, phone=phone,
                                                     user=user if user and user.is_authenticated else None), True
    except IntegrityError:  # درخواست هم‌زمان
        return BackInStockRequest.objects.get(variant=variant, phone=phone, notified_at__isnull=True), False
