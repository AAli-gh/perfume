"""یادآوری سبد رهاشده: یک پیامک به مشتری واردشده‌ای که سبدش را پر کرده ولی سفارش نداده است.

هر سبد فقط یک بار یادآوری می‌گیرد؛ اگر مشتری دوباره سبد را تغییر دهد، یادآوری بعدی مجاز می‌شود.
سبدهای قدیمی‌تر از MAX_AGE یادآوری نمی‌گیرند. اجرا: Celery beat (هر ۳۰ دقیقه) یا دستور
python manage.py send_cart_reminders (مثلاً در Scheduled task میزبان).
"""

from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.cart.models import SavedCart
from apps.catalog.models import ProductVariant
from apps.core.templatetags.majd import fa, toman
from apps.orders.models import Order

from . import events as E
from .models import NotificationLog
from .services import notify_event, settings_for

MAX_AGE = timedelta(days=3)


def due_carts(store, now=None):
    now = now or timezone.now()
    conf = settings_for(store)
    if not conf.cart_reminder_enabled:
        return SavedCart.objects.none()
    ordered_since = Order.objects.filter(store=store, user=OuterRef("user"), created_at__gte=OuterRef("updated_at"))
    return (SavedCart.objects.for_store(store)
            .filter(reminded_at__isnull=True, updated_at__lte=now - timedelta(hours=conf.cart_reminder_hours),
                    updated_at__gte=now - MAX_AGE)
            .exclude(items={}).exclude(user__phone="")
            .exclude(Exists(ordered_since))
            .select_related("user"))


def cart_summary(saved):
    variants = {str(v.pk): v for v in ProductVariant.objects.filter(pk__in=list(saved.items), product__is_active=True)
                .select_related("product")}
    lines = [(variants[k], int(q)) for k, q in saved.items.items() if k in variants and variants[k].stock > 0]
    if not lines:
        return None
    first = lines[0][0].product.name
    count = sum(q for _, q in lines)
    items = f"«{first}»" + (f" و {fa(count - lines[0][1])} کالای دیگر" if count > lines[0][1] else "")
    return {"items": items, "total": toman(sum(v.current_price * q for v, q in lines))}


def send_reminders(store, now=None):
    sent = 0
    for saved in due_carts(store, now):
        summary = cart_summary(saved)
        saved.reminded_at = timezone.now()
        saved.save(update_fields=["reminded_at"])  # updated_at همان می‌ماند (auto_now فقط در save کامل)
        if summary is None:
            continue
        context = {"name": saved.user.first_name or "مشتری", "cart_url": store.base_url + "/cart/", **summary}
        logs = notify_event(store, E.CART_REMINDER, context, phone=saved.user.phone, audiences=(E.CUSTOMER,))
        sent += any(entry.status == NotificationLog.SENT for entry in logs)
    return sent
