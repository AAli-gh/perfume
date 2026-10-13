"""«خبرم کن وقتی قیمت پایین آمد» برای محصولات علاقه‌مندی‌ها.

مبنا قیمت شیشه (کمترین، با حراج) هنگام افزودن به علاقه‌مندی‌هاست. وقتی قیمت فعلی دست‌کم price_drop_percent
درصد از مبنا کمتر شود و محصول موجود باشد، یک پیامک/ایمیل می‌رود و مبنا همان قیمت جدید می‌شود؛ پس برای یک
کاهش فقط یک بار خبر داده می‌شود. اجرا: Celery beat (هر ساعت) یا python manage.py send_price_drop_alerts.
"""

from django.utils import timezone

from apps.catalog.models import Product
from apps.core.templatetags.majd import fa, toman
from apps.wishlist.models import WishlistItem

from . import events as E
from .models import NotificationLog
from .services import notify_event, settings_for


def due_alerts(store):
    """[(WishlistItem، قیمت فعلی)] برای کاهش‌هایی که هنوز خبر داده نشده‌اند."""
    conf = settings_for(store)
    if not conf.price_drop_enabled:
        return []
    items = list(WishlistItem.objects.filter(price_alert=True, product__store=store, product__is_active=True)
                 .select_related("user", "product"))
    if not items:
        return []
    in_stock = Product.objects.filter(pk__in={i.product_id for i in items}, variants__stock__gt=0).values("pk")
    prices = dict(Product.objects.filter(pk__in=in_stock).with_stats().values_list("pk", "min_price"))
    due = []
    for item in items:
        price = prices.get(item.product_id)
        if item.price_seen is None:  # علاقه‌مندی‌های پیش از این قابلیت: قیمت فعلی مبنا می‌شود، بدون پیام
            if price:
                WishlistItem.objects.filter(pk=item.pk).update(price_seen=price)
            continue
        if price and price * 100 <= item.price_seen * (100 - conf.price_drop_percent):
            due.append((item, price))
    return due


def send_alerts(store):
    sent = 0
    for item, price in due_alerts(store):
        user = item.user
        old = item.price_seen
        item.price_seen, item.price_alerted_at = price, timezone.now()  # یک کاهش، یک پیام (حتی اگر ارسال ناموفق شد)
        item.save(update_fields=["price_seen", "price_alerted_at"])
        if not (user.phone or user.has_real_email):
            continue
        context = {"name": user.first_name or "مشتری", "product": item.product.name, "old_price": toman(old),
                   "new_price": toman(price), "percent": fa(round((old - price) * 100 / old)),
                   "product_url": store.base_url + item.product.get_absolute_url()}
        logs = notify_event(store, E.PRICE_DROP, context, phone=user.phone or "",
                            email=user.email if user.has_real_email else "", audiences=(E.CUSTOMER,))
        sent += any(entry.status == NotificationLog.SENT for entry in logs)
    return sent
