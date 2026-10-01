import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from apps.cart.cart import Cart
from apps.cart.services import apply_coupon_code
from apps.catalog.models import ProductVariant
from apps.catalog.tests.factories import VariantFactory
from apps.orders.models import Coupon, Order, OrderItem
from apps.orders.services import change_status

pytestmark = pytest.mark.django_db


@pytest.fixture
def order():
    variant = VariantFactory(stock=3)
    o = Order.objects.create(first_name="a", last_name="b", phone="09120000000", province="تهران",
                             city="تهران", address="x", postal_code="1234567890", total=1)
    OrderItem.objects.create(order=o, variant=variant, product_name="x", size_ml=50, unit_price=1, quantity=2)
    return o


def test_cancel_restocks(order):
    change_status(order, Order.Status.CANCELLED)
    order.save()
    assert ProductVariant.objects.get().stock == 5


def test_other_status_change_keeps_stock(order):
    change_status(order, Order.Status.SHIPPED)
    order.save()
    assert ProductVariant.objects.get().stock == 3


def test_admin_cancel_uses_service(order, admin_client):
    data = {
        "first_name": "a", "last_name": "b", "phone": "09120000000", "email": "", "province": "تهران",
        "city": "تهران", "address": "x", "postal_code": "1234567890", "note": "",
        "status": "cancelled", "payment_method": "online",
        "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1", "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
        "items-0-id": str(order.items.get().pk), "items-0-order": str(order.pk),
    }
    resp = admin_client.post(f"/admin/orders/order/{order.pk}/change/", data)
    assert resp.status_code == 302, resp.content[:500]
    assert ProductVariant.objects.get().stock == 5


def _cart():
    request = RequestFactory().get("/")
    request.session = SessionStore()
    return Cart(request)


def test_apply_coupon_code_service():
    variant = VariantFactory(price=1_000_000)
    Coupon.objects.create(code="OFF10", percent=10)
    cart = _cart()
    cart.add(variant, 1)
    assert not apply_coupon_code(cart, "").ok
    assert not apply_coupon_code(cart, "nope").ok
    result = apply_coupon_code(cart, "off10")
    assert result.ok and cart.discount == 100_000
