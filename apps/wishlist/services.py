from .models import WishlistItem


def toggle(user, product):
    """افزودن/حذف محصول از علاقه‌مندی‌ها؛ خروجی: True اگر اکنون در فهرست است."""
    deleted, _ = WishlistItem.objects.filter(user=user, product=product).delete()
    if deleted:
        return False
    WishlistItem.objects.get_or_create(user=user, product=product)
    return True


def is_wishlisted(user, product):
    return user.is_authenticated and WishlistItem.objects.filter(user=user, product=product).exists()


def wishlist_products(user, store):
    from apps.catalog.selectors import listable_products

    return listable_products(store).filter(wishlisted_by__user=user).order_by("-wishlisted_by__created_at")
