"""مشتریان فروشگاه بر اساس سفارش‌ها (هر شماره موبایل یک مشتری؛ مهمان و عضو با هم).

«خرید» همان تعریف گزارش فروش است: سفارش لغونشده‌ای که پرداخت شده یا روش پرداختش آنلاین نیست.
گروه‌های آماده: VIP (مجموع خرید بالا)، خرید نکرده در ۹۰ روز اخیر، مشتری جدید، یک‌بار خرید، خرید تکراری.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Max, Min, OuterRef, Q, Subquery, Sum
from django.utils import timezone

from .models import CustomerProfile, Order
from .reports import sales_filter

SEGMENTS = [
    ("all", "همه مشتریان"),
    ("vip", "VIP"),
    ("inactive", "۹۰ روز خرید نکرده"),
    ("new", "جدید (۳۰ روز اخیر)"),
    ("one_time", "یک‌بار خرید"),
    ("repeat", "خرید تکراری"),
]
SORTS = {"spent": "-spent", "orders": "-orders", "recent": "-last", "old": "last"}


@dataclass(frozen=True)
class CustomerFilters:
    segment: str = "all"
    search: str = ""
    tag: str = ""
    vip_threshold: int = 20_000_000
    inactive_days: int = 90
    sort: str = "spent"


def customers(store, filters=CustomerFilters(), now=None):
    """QuerySet از dictهایی با phone، name، email، orders، spent، last، first."""
    now = now or timezone.now()
    orders = Order.objects.for_store(store).filter(sales_filter())
    latest = Order.objects.for_store(store).filter(phone=OuterRef("phone")).order_by("-created_at")
    qs = (orders.values("phone")
          .annotate(orders=Count("id"), spent=Sum("total"), last=Max("created_at"), first=Min("created_at"),
                    first_name=Subquery(latest.values("first_name")[:1]),
                    last_name=Subquery(latest.values("last_name")[:1]),
                    email=Subquery(latest.exclude(email="").values("email")[:1]),
                    user_id=Max("user_id")))
    f = filters
    if f.segment == "vip":
        qs = qs.filter(spent__gte=f.vip_threshold)
    elif f.segment == "inactive":
        qs = qs.filter(last__lt=now - timedelta(days=f.inactive_days))
    elif f.segment == "new":
        qs = qs.filter(first__gte=now - timedelta(days=30))
    elif f.segment == "one_time":
        qs = qs.filter(orders=1)
    elif f.segment == "repeat":
        qs = qs.filter(orders__gte=2)
    if f.search:
        qs = qs.filter(Q(phone__contains=f.search) | Q(first_name__icontains=f.search)
                       | Q(last_name__icontains=f.search))
    if f.tag:
        phones = CustomerProfile.objects.for_store(store).filter(tags__icontains=f.tag).values("phone")
        qs = qs.filter(phone__in=phones)
    return qs.order_by(SORTS.get(f.sort, "-spent"), "phone")


def customer(store, phone):
    rows = list(customers(store, CustomerFilters()).filter(phone=phone))
    return rows[0] if rows else None


def profile_for(store, phone):
    return CustomerProfile.objects.for_store(store).filter(phone=phone).first()


def profiles(store, phones):
    return {p.phone: p for p in CustomerProfile.objects.for_store(store).filter(phone__in=list(phones))}


def save_profile(store, phone, *, note, tags, user=None):
    profile, _ = CustomerProfile.objects.get_or_create(store=store, phone=phone)
    profile.note, profile.tags = note, tags
    profile.updated_by = user if user and user.is_authenticated else None
    profile.save()
    return profile
