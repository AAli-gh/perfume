"""مشتریان: فهرست، گروه‌ها، یادداشت داخلی و پیامک گروهی با کد تخفیف."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.discounts.models import Coupon
from apps.notifications.models import Campaign, NotificationLog
from apps.notifications.sms import console
from apps.orders import customers as C
from apps.orders.models import CustomerProfile, Order

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
    console.outbox.clear()


def order(store, phone, total, *, days_ago=0, first="سارا", status=Order.Status.PENDING,
          method=Order.PaymentMethod.COD):
    o = Order.objects.create(store=store, first_name=first, last_name="احمدی", phone=phone, province="تهران",
                             city="تهران", address="x", postal_code="1234567890", total=total, subtotal=total,
                             status=status, payment_method=method)
    Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
    return o


@pytest.fixture
def data(store, other_store):
    order(store, "09120000001", 15_000_000, days_ago=200)
    order(store, "09120000001", 9_000_000, days_ago=150, first="سارا جان")   # VIP و ۹۰ روز خرید نکرده
    order(store, "09120000002", 3_000_000, days_ago=5, first="رضا")           # جدید، یک‌بار
    order(store, "09120000003", 4_000_000, days_ago=40, first="مینا")
    order(store, "09120000003", 2_000_000, days_ago=2, first="مینا")          # تکراری
    order(store, "09120000004", 8_000_000, status=Order.Status.CANCELLED)     # لغو ← مشتری حساب نمی‌شود
    order(store, "09120000005", 8_000_000, method=Order.PaymentMethod.ONLINE)  # آنلاینِ پرداخت‌نشده
    order(other_store, "09120000009", 50_000_000)
    return store


def phones(store, **filters):
    return [c["phone"] for c in C.customers(store, C.CustomerFilters(**filters))]


def test_customer_aggregates_and_segments(data):
    rows = {c["phone"]: c for c in C.customers(data)}
    assert set(rows) == {"09120000001", "09120000002", "09120000003"}
    sara = rows["09120000001"]
    assert (sara["orders"], sara["spent"], sara["first_name"]) == (2, 24_000_000, "سارا جان")  # نام آخرین سفارش
    assert phones(data, segment="vip") == ["09120000001"]
    assert phones(data, segment="inactive") == ["09120000001"]
    assert phones(data, segment="new") == ["09120000002"]
    assert phones(data, segment="one_time") == ["09120000002"]
    assert phones(data, segment="repeat", sort="recent") == ["09120000003", "09120000001"]
    assert phones(data, search="مینا") == ["09120000003"]


@pytest.fixture
def staff(client):
    user = User.objects.create_user(email="crm@example.com", password="x-Strong-123", is_staff=True)
    for codename in ("view_user", "change_user", "add_campaign"):
        user.user_permissions.add(Permission.objects.get(codename=codename))
    client.force_login(user)
    return user


def test_customer_pages_and_notes(client, data, staff):
    page = client.get(reverse("builder:customers"), {"seg": "vip"})
    assert [r["phone"] for r in page.context["rows"]] == ["09120000001"]
    detail = client.get(reverse("builder:customer", args=["09120000001"]))
    assert detail.status_code == 200 and len(detail.context["orders"]) == 2
    client.post(reverse("builder:customer", args=["09120000001"]), {"tags": "همکار، عمده", "note": "بسته‌بندی ویژه"})
    profile = CustomerProfile.objects.get()
    assert profile.tag_list == ["همکار", "عمده"] and profile.updated_by == staff
    assert phones(data, tag="عمده") == ["09120000001"]
    assert client.get(reverse("builder:customer", args=["09129999999"])).status_code == 404


def test_customers_need_permission(client, data):
    user = User.objects.create_user(email="d@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="change_themesettings"))
    client.force_login(user)
    assert client.get(reverse("builder:customers")).status_code == 403


def test_sms_campaign_with_coupon(client, data, staff):
    url = reverse("builder:campaign_new") + "?seg=repeat"
    form = client.get(url)
    assert form.context["count"] == 2
    response = client.post(url, {"name": "بازگشت", "message": "{name} عزیز، کد {code} برای {percent}٪ تخفیف",
                                 "with_coupon": "on", "percent": "15", "days": "7", "opt_out": "on",
                                 "confirm": "on"})
    assert response.status_code == 302
    campaign = Campaign.objects.get()
    coupon = Coupon.objects.get(code=campaign.coupon_code)
    assert coupon.percent == 15 and coupon.usage_limit == 2 and coupon.valid_to > timezone.now()
    assert (campaign.sent, campaign.status) == (2, "done")
    texts = {m["to"]: m["text"] for m in console.outbox}
    assert set(texts) == {"09120000001", "09120000003"}
    assert "مینا عزیز" in texts["09120000003"] and coupon.code in texts["09120000003"] and "لغو۱۱" in texts["09120000003"]
    assert NotificationLog.objects.filter(campaign=campaign, status=NotificationLog.SENT).count() == 2


def test_campaign_validation(client, data, staff):
    url = reverse("builder:campaign_new") + "?seg=vip"
    bad = client.post(url, {"name": "x", "message": "کد {code}", "confirm": "on", "days": "7"})
    assert bad.status_code == 422 and not Campaign.objects.exists()
    unknown = client.post(url, {"name": "x", "message": "سلام {foo}", "confirm": "on"})
    assert unknown.status_code == 422
