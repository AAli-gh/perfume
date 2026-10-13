"""سلیقه رایحه کاربر از خریدها، علاقه‌مندی‌ها و عطرهای اخیراً دیده‌شده."""

from django.db.models import Q

from apps.catalog import recommend
from apps.catalog.history import recently_viewed_ids
from apps.orders.models import Order, OrderItem

PURCHASE_WEIGHT = 1.0
WISHLIST_WEIGHT = 0.6
VIEW_WEIGHT = 0.25


def purchased_counts(user, store):
    """{product_id: تعداد خریدشده} از سفارش‌های واقعی (لغو نشده و پرداخت‌شده یا غیرآنلاین)."""
    if not user.is_authenticated:
        return {}
    sold = ~Q(order__status=Order.Status.CANCELLED) & (
        Q(order__paid_at__isnull=False) | ~Q(order__payment_method=Order.PaymentMethod.ONLINE))
    counts = {}
    rows = (OrderItem.objects.filter(sold, order__user=user, order__store=store, variant__isnull=False)
            .values_list("variant__product_id", "quantity"))
    for product_id, quantity in rows:
        counts[product_id] = counts.get(product_id, 0) + quantity
    return counts


def has_purchased(user, product):
    """مشتری این محصول را خریده و سفارشش تحویل شده؟ (نشان «خریدار تأییدشده» نظرها؛ REVIEWS_PURCHASE_CHECK)"""
    if user is None or not user.is_authenticated:
        return False
    return OrderItem.objects.filter(order__user=user, order__store_id=product.store_id,
                                    order__status=Order.Status.DELIVERED, variant__product=product).exists()


def build_taste(request, pool=None):
    """(Taste, منابع)؛ اگر بازدیدکننده هیچ سابقه‌ای نداشته باشد، بدون کوئری محصولات برمی‌گردد."""
    store, user = request.store, request.user
    purchases = purchased_counts(user, store)
    wishlist = (list(user.wishlist.filter(product__store=store).values_list("product_id", flat=True))
                if user.is_authenticated else [])
    views = recently_viewed_ids(request)
    taste = recommend.Taste()
    sources = {"purchases": 0, "wishlist": 0, "views": 0}
    if not (purchases or wishlist or views):
        return taste, sources, []

    pool = list(pool if pool is not None else recommend.candidates(store))
    by_id = {p.pk: p for p in pool}
    for product_id, quantity in purchases.items():
        if product_id in by_id:
            taste.add(by_id[product_id], PURCHASE_WEIGHT * min(quantity, 3))
            taste.seen.add(product_id)
            sources["purchases"] += 1
    for product_id in wishlist:
        if product_id in by_id:
            taste.add(by_id[product_id], WISHLIST_WEIGHT)
            taste.seen.add(product_id)
            sources["wishlist"] += 1
    for rank, product_id in enumerate(views):
        if product_id in by_id:
            taste.add(by_id[product_id], VIEW_WEIGHT / (1 + rank * 0.3))
            sources["views"] += 1
    return taste, sources, pool


def recommendations_for(request, limit=8):
    taste, sources, pool = build_taste(request)
    if taste.is_empty:
        return [], taste, sources
    return recommend.recommend(request.store, taste, limit=limit, pool=pool), taste, sources
