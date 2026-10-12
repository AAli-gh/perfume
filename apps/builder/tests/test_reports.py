from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.orders import reports
from apps.orders.models import Order, OrderItem

pytestmark = pytest.mark.django_db
User = get_user_model()


def _order(store, total, *, status=Order.Status.PENDING, method=Order.PaymentMethod.COD, paid=False, days_ago=0,
           city="تهران", coupon="", product="عود"):
    o = Order.objects.create(store=store, first_name="a", last_name="b", phone="09120000000", province="تهران",
                             city=city, address="x", postal_code="1234567890", total=total, subtotal=total,
                             status=status, payment_method=method, coupon_code=coupon,
                             paid_at=timezone.now() if paid else None)
    Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
    OrderItem.objects.create(order=o, product_name=product, size_ml=50, unit_price=total, quantity=1)
    return o


@pytest.fixture
def data(store, other_store):
    _order(store, 1_000_000, coupon="MAJD10")                                  # پرداخت در محل ← فروش
    _order(store, 2_000_000, method=Order.PaymentMethod.ONLINE, paid=True, status=Order.Status.PAID,
           product="زعفران")
    _order(store, 9_000_000, method=Order.PaymentMethod.ONLINE)                 # آنلاینِ پرداخت‌نشده ← فروش نیست
    _order(store, 5_000_000, status=Order.Status.CANCELLED)                     # لغو ← فروش نیست
    _order(store, 3_000_000, days_ago=40)                                       # خارج از بازه ۳۰ روزه
    _order(other_store, 7_000_000)                                              # فروشگاه دیگر
    return store


def test_summary_counts_only_real_sales_of_the_store(data):
    period = reports.Period.last(30)
    summary = reports.summary(data, period)
    assert (summary["revenue"], summary["orders"], summary["average"], summary["units"], summary["cancelled"]) == (
        3_000_000, 2, 1_500_000, 2, 1)
    assert reports.summary(data, period.previous())["revenue"] == 3_000_000
    assert reports.change(3_000_000, 3_000_000) == 0 and reports.change(5, 0) is None


def test_daily_series_has_every_day(data):
    days = reports.daily(data, reports.Period.last(7))
    assert len(days) == 7 and days[-1]["revenue"] == 3_000_000 and sum(d["orders"] for d in days) == 2


def test_breakdowns(data):
    period = reports.Period.last(30)
    assert [p["product_name"] for p in reports.top_products(data, period)] == ["زعفران", "عود"]
    assert reports.top_coupons(data, period) == [{"coupon_code": "MAJD10", "orders": 1, "discount": 0}]
    assert {s["status"] for s in reports.by_status(data, period)} == {"pending", "paid", "cancelled"}
    assert sum(p["amount"] for p in reports.by_payment_method(data, period)) == 3_000_000


def test_period_falls_back_to_30_days():
    assert reports.Period.last(12345).days == 30


@pytest.fixture
def analyst(client):
    user = User.objects.create_user(email="analyst@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="view_order"))
    client.force_login(user)
    return user


def test_report_page_renders_chart_and_tables(client, data, analyst):
    response = client.get(reverse("builder:reports"), {"days": 30})
    html = response.content.decode()
    assert response.status_code == 200
    assert "۳٬۰۰۰٬۰۰۰" in html and "<svg" in html and "<title>" in html and "زعفران" in html
    assert 'href="/studio/reports/"' in client.get(reverse("builder:dashboard")).content.decode()


def test_report_requires_permission(client, data):
    staff = User.objects.create_user(email="designer@example.com", password="x-Strong-123", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="change_themesettings"))
    client.force_login(staff)
    assert client.get(reverse("builder:reports")).status_code == 403
    client.logout()
    assert client.get(reverse("builder:reports")).status_code == 404


def test_csv_export_is_escaped_and_audited(client, data, analyst):
    _order(data, 1_000, city="=HYPERLINK(\"http://evil\")")
    response = client.get(reverse("builder:reports"), {"days": 7, "format": "csv"})
    body = response.content.decode("utf-8")
    assert response["Content-Type"].startswith("text/csv") and body.startswith("﻿")
    assert "'=HYPERLINK" in body and "\n=HYPERLINK" not in body and ",=HYPERLINK" not in body
    assert body.count("\n") == 1 + 5  # سرستون + ۵ سفارش ۷ روز اخیر (فقط همین فروشگاه)
    from apps.core.models import AuditLog

    assert AuditLog.objects.filter(action="studio.export_orders").exists()


def test_chart_geometry_and_labels():
    from datetime import date

    from apps.builder.views import CHART_H, _chart

    days = [{"day": date(2026, 10, d), "revenue": r, "orders": 1 if r else 0} for d, r in [(1, 0), (2, 500), (3, 1000)]]
    chart = _chart(days)
    tall = chart["bars"][2]
    assert chart["bars"][0]["h"] == 0 and tall["y"] + tall["h"] == CHART_H and chart["bars"][1]["h"] == tall["h"] / 2
    assert [g["value"] for g in chart["grid"]] == [500, 1000] and all(g["label_y"] < g["y"] for g in chart["grid"])
    assert chart["bars"][0]["label"]  # برچسب تاریخ شمسی
