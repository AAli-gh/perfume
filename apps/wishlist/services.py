from .models import WishlistItem


def toggle(user, product):
    """افزودن/حذف محصول از علاقه‌مندی‌ها؛ خروجی: True اگر اکنون در فهرست است."""
    deleted, _ = WishlistItem.objects.filter(user=user, product=product).delete()
    if deleted:
        return False
    WishlistItem.objects.get_or_create(user=user, product=product, defaults={"price_seen": current_price(product)})
    return True


def current_price(product):
    """قیمت فعلی شیشه (کمترین، با حراج) — همان «از ...» کارت محصول."""
    from apps.catalog.models import Product

    return Product.objects.filter(pk=product.pk).with_stats().values_list("min_price", flat=True).first()


def set_price_alert(user, product, enabled):
    return WishlistItem.objects.filter(user=user, product=product).update(price_alert=enabled)


def is_wishlisted(user, product):
    return user.is_authenticated and WishlistItem.objects.filter(user=user, product=product).exists()


def wishlist_products(user, store):
    from apps.catalog.selectors import listable_products

    return listable_products(store).filter(wishlisted_by__user=user).order_by("-wishlisted_by__created_at")


def price_alerts(user):
    """{شناسه محصول: خبر کاهش قیمت روشن است؟} برای صفحه علاقه‌مندی‌ها."""
    return dict(WishlistItem.objects.filter(user=user).values_list("product_id", "price_alert"))
