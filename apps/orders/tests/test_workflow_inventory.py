"""موجودی، چرخه وضعیت سفارش، قیمت‌گذاری و قفل کد تخفیف."""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from apps.cart.pricing import calculate
from apps.catalog import inventory
from apps.catalog.models import ProductVariant, StockMovement
from apps.catalog.tests.factories import VariantFactory
from apps.discounts.models import Coupon
from apps.orders.models import Order
from apps.orders.tasks import release_expired_reservations
from apps.orders.workflow import InvalidTransition, transition

pytestmark = pytest.mark.django_db

CHECKOUT = {
    "first_name": "علی", "last_name": "رضایی", "phone": "09121234567", "province": "تهران", "city": "تهران",
    "address": "خیابان", "postal_code": "1234567890", "payment_method": "cod", "accept_terms": "on",
}


def ledger(variant):
    return StockMovement.objects.filter(variant=variant).aggregate(s=Sum("change"))["s"] or 0


def place_order(client, variant, qty=1, **extra):
    client.post(reverse("cart:add"), {"variant": variant.pk, "quantity": qty})
    client.post(reverse("orders:checkout"), {**CHECKOUT, **extra})
    return Order.objects.order_by("-pk").first()


# ---------- قیمت‌گذاری ----------

class Line:
    def __init__(self, price, qty):
        self.unit_price, self.quantity = price, qty


def test_pricing_calculation(store):
    cfg = store.config
    cfg.shipping_cost, cfg.free_shipping_over = 100_000, 1_000_000
    p = calculate([Line(300_000, 2)], cfg)
    assert (p.subtotal, p.discount, p.shipping, p.total) == (600_000, 0, 100_000, 700_000)
    coupon = Coupon(code="X", percent=10)
    p = calculate([Line(600_000, 2)], cfg, coupon)
    assert (p.discount, p.shipping, p.total) == (120_000, 0, 1_080_000)  # ارسال رایگان بعد از تخفیف
    assert calculate([], cfg).total == 0


def test_invalid_coupon_ignored_by_pricing(store):
    coupon = Coupon(code="MIN", percent=50, min_subtotal=10_000_000)
    p = calculate([Line(1_000_000, 1)], store.config, coupon)
    assert p.coupon is None and p.discount == 0


def test_currency_label_from_store(client, store):
    from apps.core.templatetags.majd import toman

    assert toman(1500) == "۱٬۵۰۰ تومان"
    store.config.currency_label = "ریال"
    store.config.save()
    from apps.core.stores import use_store

    with use_store(store):
        assert toman(1500) == "۱٬۵۰۰ ریال"


# ---------- موجودی ----------

def test_checkout_reserves_stock_in_ledger(client):
    variant = VariantFactory(stock=5)
    inventory.record_initial(variant)
    order = place_order(client, variant, qty=2)
    variant.refresh_from_db()
    assert variant.stock == 3 == ledger(variant)
    assert StockMovement.objects.filter(reason="reserved", reference=order.number, change=-2).exists()


def test_reserve_is_all_or_nothing():
    a, b = VariantFactory(stock=5), VariantFactory(stock=1)
    with pytest.raises(inventory.OutOfStock):
        inventory.reserve([inventory.StockLine(a.pk, 2), inventory.StockLine(b.pk, 3)], "R1")
    a.refresh_from_db()
    assert a.stock == 5 and not StockMovement.objects.exists()


def test_set_stock_records_difference(admin_user):
    variant = VariantFactory(stock=10)
    inventory.record_initial(variant)
    inventory.set_stock(variant, 7, user=admin_user)
    variant.refresh_from_db()
    assert variant.stock == 7 == ledger(variant)
    assert StockMovement.objects.get(reason="adjustment").change == -3


def test_admin_stock_edit_goes_through_ledger(admin_client):
    variant = VariantFactory(stock=10)
    inventory.record_initial(variant)
    product = variant.product
    resp = admin_client.get(reverse("admin:catalog_product_change", args=[product.pk]))
    form = resp.context["adminform"].form
    data = {k: v for k, v in form.initial.items() if v is not None and not isinstance(v, (list, tuple))}
    data.update({
        "store": product.store_id, "brand": product.brand_id, "scent": product.scent_id, "is_active": "on",
        "variants-TOTAL_FORMS": "1", "variants-INITIAL_FORMS": "1", "variants-MIN_NUM_FORMS": "0", "variants-MAX_NUM_FORMS": "1000",
        "variants-0-id": variant.pk, "variants-0-product": product.pk, "variants-0-size_ml": 50,
        "variants-0-price": variant.price, "variants-0-stock": 4,
        "notes-TOTAL_FORMS": "0", "notes-INITIAL_FORMS": "0", "notes-MIN_NUM_FORMS": "0", "notes-MAX_NUM_FORMS": "1000",
        "images-TOTAL_FORMS": "0", "images-INITIAL_FORMS": "0", "images-MIN_NUM_FORMS": "0", "images-MAX_NUM_FORMS": "1000",
    })
    data.pop("image", None)
    resp = admin_client.post(reverse("admin:catalog_product_change", args=[product.pk]), data)
    assert resp.status_code == 302, resp.context["adminform"].form.errors if resp.context else resp
    variant.refresh_from_db()
    assert variant.stock == 4 == ledger(variant)


# ---------- چرخه وضعیت ----------

def test_cancel_releases_stock_exactly_once(client, admin_user):
    variant = VariantFactory(stock=5)
    inventory.record_initial(variant)
    order = place_order(client, variant, qty=2)
    transition(order, Order.Status.CANCELLED, by=admin_user)
    with pytest.raises(InvalidTransition):  # لغوشده وضعیت پایانی است ← آزادسازی دوباره ممکن نیست
        transition(order, Order.Status.PENDING)
    variant.refresh_from_db()
    assert variant.stock == 5 == ledger(variant)
    assert order.history.get().changed_by == admin_user


@pytest.mark.parametrize("path, ok", [
    (["processing", "shipped", "delivered"], True),
    (["paid", "processing", "shipped"], True),
    (["shipped"], False),
    (["delivered"], False),
    (["processing", "pending"], False),
])
def test_transition_rules(client, path, ok):
    order = place_order(client, VariantFactory(stock=5))
    run = lambda: [transition(order, s) for s in path]  # noqa: E731
    if ok:
        run()
        assert order.status == path[-1] and order.history.count() == len(path)
    else:
        with pytest.raises(InvalidTransition):
            run()


def test_paid_sets_paid_at(client):
    order = place_order(client, VariantFactory(stock=5))
    transition(order, Order.Status.PAID)
    order.refresh_from_db()
    assert order.is_paid


def test_admin_rejects_invalid_transition(admin_client, client):
    order = place_order(client, VariantFactory(stock=5))
    transition(order, Order.Status.CANCELLED)
    resp = admin_client.post(reverse("admin:orders_order_changelist"), {
        "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
        "form-0-id": order.pk, "form-0-status": "processing", "_save": "ذخیره",
    })
    order.refresh_from_db()
    assert order.status == "cancelled"
    assert "فقط به این وضعیت‌ها" in resp.content.decode()


# ---------- مهلت پرداخت ----------

def test_online_order_gets_payment_deadline(client, store):
    order = place_order(client, VariantFactory(stock=5), payment_method="online")
    assert order.reserved_until is not None
    delta = order.reserved_until - order.created_at
    assert abs(delta - timedelta(minutes=store.config.payment_timeout_minutes)) < timedelta(seconds=5)
    cod = place_order(client, VariantFactory(stock=5))
    assert cod.reserved_until is None


def test_expired_unpaid_orders_release_stock(client):
    variant = VariantFactory(stock=5)
    inventory.record_initial(variant)
    order = place_order(client, variant, qty=3, payment_method="online")
    Order.objects.filter(pk=order.pk).update(reserved_until=timezone.now() - timedelta(minutes=1))
    fresh = place_order(client, variant, qty=1, payment_method="online")
    assert release_expired_reservations.delay().get() == 1
    order.refresh_from_db(); fresh.refresh_from_db(); variant.refresh_from_db()
    assert order.status == "cancelled" and fresh.status == "pending"
    assert variant.stock == 4 == ledger(variant)
    assert order.history.get().note == "انقضای مهلت پرداخت"


# ---------- هم‌زمانی: سقف کد تخفیف ----------

@pytest.mark.django_db(transaction=True)
def test_coupon_usage_limit_holds_under_concurrency(store):
    """دو سفارش هم‌زمان با کدی که فقط یک بار قابل استفاده است: فقط یکی موفق می‌شود."""
    from django.test import Client

    Coupon.objects.create(code="ONCE", percent=10, usage_limit=1)
    variant = VariantFactory(stock=10)
    clients = [Client(), Client()]
    for c in clients:
        c.post(reverse("cart:add"), {"variant": variant.pk})
        c.post(reverse("cart:coupon"), {"code": "ONCE"})
    barrier = threading.Barrier(2)

    def checkout(c):
        barrier.wait()
        try:
            c.post(reverse("orders:checkout"), CHECKOUT)
        finally:
            connection.close()

    threads = [threading.Thread(target=checkout, args=(c,)) for c in clients]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert Coupon.objects.get().used_count == 1
    assert Order.objects.filter(coupon_code="ONCE").count() == 1
    assert Order.objects.count() == 1  # سفارش دوم با پیام خطا متوقف شد، نه بدون تخفیف
