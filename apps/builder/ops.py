"""داده‌های پیشخوان عملیات استودیو: کارهای امروز مدیر فروشگاه (فقط خواندنی).

- سفارش‌هایی که اقدام لازم دارند: کارت به کارتِ منتظر تأیید، آماده‌سازی، ارسال
- کالاهای رو به اتمام (موجودی ≤ آستانه حجم یا آستانه پیش‌فرض فروشگاه)
- نظرهای منتظر تأیید و پیام‌های خوانده‌نشده
- فروش امروز در برابر دیروز (کل روز و «تا همین ساعت»)
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.db.models import Count, F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.catalog.models import BackInStockRequest, ProductVariant
from apps.orders.models import Order, ReturnRequest
from apps.orders.reports import change, sales_filter
from apps.pages.models import ContactMessage
from apps.reviews.models import Review

S, P = Order.Status, Order.PaymentMethod


def awaiting_card(store):
    """کارت به کارتِ ثبت‌شده که هنوز «پرداخت شده» نشده: واریز را بررسی و تأیید کنید."""
    return Order.objects.for_store(store).filter(status=S.PENDING, payment_method=P.CARD)


def to_prepare(store):
    """پرداخت‌شده‌ها و پرداخت در محل‌های جدید: باید آماده‌سازی شوند."""
    return Order.objects.for_store(store).filter(Q(status=S.PAID) | Q(status=S.PENDING, payment_method=P.COD))


def to_ship(store):
    return Order.objects.for_store(store).filter(status=S.PROCESSING)


def needs_action(store):
    return Order.objects.for_store(store).filter(
        Q(status__in=[S.PAID, S.PROCESSING]) | Q(status=S.PENDING, payment_method__in=[P.CARD, P.COD])
    )


def low_stock(store):
    """حجم‌های محصولات فعال با موجودی ≤ آستانه؛ کم‌موجودترین اول، همراه با تعداد «خبرم کن»های باز."""
    default = getattr(getattr(store, "config", None), "low_stock_threshold", 3)
    return (
        ProductVariant.objects.filter(product__store=store, product__is_active=True)
        .annotate(threshold=Coalesce("low_stock_threshold", Value(default), output_field=IntegerField()))
        .filter(stock__lte=F("threshold"))
        .annotate(waiting=Count("stock_requests", filter=Q(stock_requests__notified_at__isnull=True)))
        .select_related("product")
        .order_by("stock", "-waiting", "product__name")
    )


def _sales(store, start, end):
    qs = Order.objects.for_store(store).filter(sales_filter(), created_at__gte=start, created_at__lt=end)
    agg = qs.aggregate(revenue=Sum("total"), orders=Count("id"))
    return {"revenue": agg["revenue"] or 0, "orders": agg["orders"] or 0}


@dataclass
class Today:
    today: dict
    yesterday: dict
    yesterday_so_far: dict  # دیروز تا همین ساعت (مقایسه منصفانه وسط روز)

    @property
    def change(self):
        return change(self.today["revenue"], self.yesterday_so_far["revenue"])


def sales_today(store, now=None):
    now = timezone.localtime(now or timezone.now())
    midnight = timezone.make_aware(datetime.combine(now.date(), time.min))
    day = timedelta(days=1)
    return Today(
        today=_sales(store, midnight, midnight + day),
        yesterday=_sales(store, midnight - day, midnight),
        yesterday_so_far=_sales(store, midnight - day, now - day),
    )


def summary(store):
    now = timezone.localtime()
    midnight = timezone.make_aware(datetime.combine(now.date(), time.min))
    low = low_stock(store)
    return {
        "sales": sales_today(store),
        "new_today": Order.objects.for_store(store).filter(created_at__gte=midnight).count(),
        "awaiting_card": awaiting_card(store).count(),
        "to_prepare": to_prepare(store).count(),
        "to_ship": to_ship(store).count(),
        "orders": list(needs_action(store).order_by("created_at")[:10]),
        "low_stock_count": low.count(),
        "low_stock": list(low[:6]),
        "out_of_stock": low.filter(stock=0).count(),
        "waiting_requests": BackInStockRequest.objects.filter(variant__product__store=store,
                                                              notified_at__isnull=True).count(),
        "open_returns": ReturnRequest.objects.filter(order__store=store, status__in=[
            ReturnRequest.Status.REQUESTED, ReturnRequest.Status.APPROVED, ReturnRequest.Status.RECEIVED]).count(),
        "pending_reviews": Review.objects.filter(product__store=store, is_approved=False).count(),
        "unread_messages": ContactMessage.objects.for_store(store).filter(is_read=False).count(),
    }
