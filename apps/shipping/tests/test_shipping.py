import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.catalog.tests.factories import VariantFactory
from apps.orders.models import Order
from apps.orders.workflow import transition
from apps.shipping.carriers import Carrier, Shipment, ShipmentNotSupported, carrier_choices, register
from apps.shipping.carriers.registry import _CARRIERS
from apps.shipping.models import ProvinceRate, ShippingMethod

pytestmark = pytest.mark.django_db

CHECKOUT = {
    "first_name": "علی", "last_name": "رضایی", "phone": "09121234567", "email": "", "province": "فارس",
    "city": "شیراز", "address": "خیابان زند", "postal_code": "1234567890", "note": "",
    "payment_method": "cod", "accept_terms": "on",
}


@pytest.fixture
def post(store):
    method = ShippingMethod.objects.create(store=store, name="پست پیشتاز", description="۳ تا ۵ روز", cost=80_000,
                                           free_over=5_000_000, tracking_url_template="https://track.example/?id={code}")
    ProvinceRate.objects.create(method=method, province="فارس", cost=120_000)
    return method


@pytest.fixture
def courier(store):
    return ShippingMethod.objects.create(store=store, name="پیک تهران", cost=60_000, provinces=["تهران"], priority=1)


@pytest.fixture
def cart(client):
    variant = VariantFactory(price=1_000_000, stock=10)
    client.post(reverse("cart:add"), {"variant": variant.pk, "quantity": 1})
    return variant


def test_cost_for_uses_province_rate_base_cost_and_free_threshold(post):
    assert post.cost_for("فارس", 1_000_000) == 120_000
    assert post.cost_for("تهران", 1_000_000) == 80_000
    assert post.cost_for("", 1_000_000) == 80_000
    assert post.cost_for("فارس", 5_000_000) == 0


def test_serves_and_tracking_url(post, courier):
    assert post.serves("فارس") and courier.serves("تهران") and not courier.serves("فارس")
    assert courier.serves("")  # پیش از انتخاب استان
    assert post.tracking_url("AB 12") == "https://track.example/?id=AB 12"
    assert courier.tracking_url("X1") == ""


def test_validation_rejects_bad_values(store):
    method = ShippingMethod(store=store, name="x", carrier="nope", provinces=["مریخ"],
                            tracking_url_template="http://insecure")
    with pytest.raises(ValidationError) as exc:
        method.full_clean()
    assert {"carrier", "provinces", "tracking_url_template"} <= set(exc.value.message_dict)


def test_cart_uses_default_method_and_falls_back_to_store_setting(client, store, cart):
    store.config.shipping_cost = 99_000
    store.config.save()
    assert client.get(reverse("cart:detail")).context["cart"].shipping == 99_000  # بدون روش ارسال
    ShippingMethod.objects.create(store=store, name="پست", cost=70_000)
    assert client.get(reverse("cart:detail")).context["cart"].shipping == 70_000


def test_checkout_with_shipping_method_and_province_rate(client, post, courier, cart):
    response = client.post(reverse("orders:checkout"), {**CHECKOUT, "shipping_method": post.pk})
    order = Order.objects.get()
    assert response.status_code == 302
    assert (order.shipping, order.total, order.shipping_method, order.shipping_method_name) == (
        120_000, 1_120_000, post, "پست پیشتاز")


def test_checkout_rejects_method_that_does_not_serve_province(client, post, courier, cart):
    response = client.post(reverse("orders:checkout"), {**CHECKOUT, "shipping_method": courier.pk})
    assert response.status_code == 422 and not Order.objects.exists()
    assert "به استان فارس ارسال نمی‌کند" in response.content.decode()


def test_checkout_rejects_method_of_another_store(client, post, other_store, cart):
    foreign = ShippingMethod.objects.create(store=other_store, name="خارجی", cost=0)
    response = client.post(reverse("orders:checkout"), {**CHECKOUT, "shipping_method": foreign.pk})
    assert response.status_code == 422 and not Order.objects.exists()


def test_quote_endpoint_updates_summary(client, post, cart):
    response = client.post(reverse("orders:quote"), {"province": "فارس", "shipping_method": post.pk},
                           HTTP_HX_REQUEST="true")
    html = response.content.decode()
    assert response.status_code == 200 and 'id="checkout-summary"' in html
    assert "۱۲۰٬۰۰۰" in html and "۱٬۱۲۰٬۰۰۰" in html and "پست پیشتاز" in html
    bogus = client.post(reverse("orders:quote"), {"province": "<script>", "shipping_method": "999"}).content.decode()
    assert "<script>" not in bogus and "۸۰٬۰۰۰" in bogus  # استان نامعتبر ← هزینه پایه


def test_cart_page_shows_shipping_options(client, post, courier, cart):
    html = client.get(reverse("cart:detail")).content.decode()
    assert "روش ارسال" in html and "پست پیشتاز · ۳ تا ۵ روز" in html and "پیک تهران" in html


def test_shipped_status_records_time_and_order_page_shows_tracking(client, post, cart):
    client.post(reverse("orders:checkout"), {**CHECKOUT, "shipping_method": post.pk})
    order = Order.objects.get()
    order.tracking_code = "TRK123"
    order.save()
    transition(order, Order.Status.PROCESSING)
    transition(order, Order.Status.SHIPPED)
    order.refresh_from_db()
    assert order.shipped_at is not None and order.tracking_url == "https://track.example/?id=TRK123"
    html = client.get(order.get_absolute_url()).content.decode()
    assert "TRK123" in html and 'href="https://track.example/?id=TRK123"' in html


def test_carrier_adapter_registry_and_api_hooks(store):
    @register
    class FakeCarrier(Carrier):
        code, label, supports_api = "fake", "حمل آزمایشی", True

        def quote(self, *, province, amount):
            return 42_000 if self.method.api_key else None

        def create_shipment(self, order):
            return Shipment(tracking_code=f"F-{order.number}")

    try:
        assert ("fake", "حمل آزمایشی") in carrier_choices()
        method = ShippingMethod.objects.create(store=store, name="API", carrier="fake", cost=1, api_key="k")
        assert method.cost_for("تهران", 10) == 42_000
        method.api_key = ""
        assert method.cost_for("تهران", 10) == 1  # API قیمت نداد ← جدول نرخ
        assert method.carrier_adapter.create_shipment(Order(number="MJ1")).tracking_code == "F-MJ1"
    finally:
        _CARRIERS.pop("fake")
    manual = ShippingMethod.objects.create(store=store, name="دستی", cost=1)
    with pytest.raises(ShipmentNotSupported):
        manual.carrier_adapter.create_shipment(Order(number="MJ2"))
