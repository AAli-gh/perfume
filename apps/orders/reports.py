"""گزارش فروش (فقط خواندنی): خلاصه، فروش روزانه، وضعیت‌ها، روش پرداخت و پرفروش‌ترین محصولات.

«فروش» = سفارش‌هایی که لغو نشده‌اند و یا پرداخت شده‌اند یا روش پرداختشان آنلاین نیست
(کارت به کارت و پرداخت در محل از لحظه ثبت فروش حساب می‌شوند؛ آنلاینِ پرداخت‌نشده نه).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Order, OrderItem

PERIODS = {7: "۷ روز", 30: "۳۰ روز", 90: "۹۰ روز", 365: "یک سال"}


def sales_filter():
    return ~Q(status=Order.Status.CANCELLED) & (Q(paid_at__isnull=False) | ~Q(payment_method=Order.PaymentMethod.ONLINE))


@dataclass(frozen=True)
class Period:
    days: int
    start: date
    end: date  # شامل

    @classmethod
    def last(cls, days, today=None):
        days = days if days in PERIODS else 30
        end = today or timezone.localdate()
        return cls(days, end - timedelta(days=days - 1), end)

    def previous(self):
        return Period(self.days, self.start - timedelta(days=self.days), self.start - timedelta(days=1))


def _orders(store, period):
    return Order.objects.for_store(store).filter(created_at__date__gte=period.start, created_at__date__lte=period.end)


def summary(store, period):
    sales = _orders(store, period).filter(sales_filter())
    agg = sales.aggregate(revenue=Sum("total"), orders=Count("id"), discount=Sum("discount"), shipping=Sum("shipping"))
    revenue, count = agg["revenue"] or 0, agg["orders"] or 0
    items = OrderItem.objects.filter(order__in=sales).aggregate(units=Sum("quantity"))["units"] or 0
    return {
        "revenue": revenue, "orders": count, "average": revenue // count if count else 0, "units": items,
        "discount": agg["discount"] or 0, "shipping": agg["shipping"] or 0,
        "cancelled": _orders(store, period).filter(status=Order.Status.CANCELLED).count(),
    }


def change(current, previous):
    """درصد تغییر نسبت به دوره قبل (None اگر دوره قبل صفر بوده)."""
    if not previous:
        return None
    return round((current - previous) * 100 / previous)


def daily(store, period):
    rows = (
        _orders(store, period).filter(sales_filter())
        .annotate(day=TruncDate("created_at", tzinfo=timezone.get_current_timezone()))
        .values("day").annotate(revenue=Sum("total"), orders=Count("id")).order_by("day")
    )
    by_day = {r["day"]: r for r in rows}
    days = []
    for i in range(period.days):
        day = period.start + timedelta(days=i)
        row = by_day.get(day, {})
        days.append({"day": day, "revenue": row.get("revenue") or 0, "orders": row.get("orders") or 0})
    return days


def by_status(store, period):
    labels = dict(Order.Status.choices)
    rows = _orders(store, period).values("status").annotate(orders=Count("id"), amount=Sum("total")).order_by("-orders")
    return [{"label": labels.get(r["status"], r["status"]), **r} for r in rows]


def by_payment_method(store, period):
    labels = dict(Order.PaymentMethod.choices)
    rows = (_orders(store, period).filter(sales_filter()).values("payment_method")
            .annotate(orders=Count("id"), amount=Sum("total")).order_by("-amount"))
    return [{"label": labels.get(r["payment_method"], r["payment_method"]), **r} for r in rows]


def top_products(store, period, limit=10):
    return list(
        OrderItem.objects.filter(order__in=_orders(store, period).filter(sales_filter()))
        .values("product_name").annotate(units=Sum("quantity"), amount=Sum(F("unit_price") * F("quantity")))
        .order_by("-amount")[:limit]
    )


def top_coupons(store, period, limit=5):
    return list(
        _orders(store, period).filter(sales_filter()).exclude(coupon_code="")
        .values("coupon_code").annotate(orders=Count("id"), discount=Sum("discount")).order_by("-orders")[:limit]
    )


def export_rows(store, period):
    """ردیف‌های CSV سفارش‌های دوره (همه وضعیت‌ها)."""
    yield ["شماره", "تاریخ", "وضعیت", "روش پرداخت", "روش ارسال", "استان", "شهر", "جمع جزء", "تخفیف", "کد تخفیف",
           "هزینه ارسال", "مبلغ نهایی", "کد رهگیری", "فروش حساب می‌شود"]
    sales_ids = set(_orders(store, period).filter(sales_filter()).values_list("id", flat=True))
    for o in _orders(store, period).order_by("created_at").iterator():
        yield [o.number, timezone.localtime(o.created_at).strftime("%Y-%m-%d %H:%M"), o.get_status_display(),
               o.get_payment_method_display(), o.shipping_method_name, o.province, o.city, o.subtotal, o.discount,
               o.coupon_code, o.shipping, o.total, o.tracking_code, "بله" if o.id in sales_ids else "خیر"]
