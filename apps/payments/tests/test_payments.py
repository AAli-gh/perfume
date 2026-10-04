import os
import subprocess
import sys
from datetime import timedelta
from unittest import mock

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.catalog.tests.factories import VariantFactory
from apps.orders.models import Order
from apps.payments.gateways import PaymentError
from apps.payments.gateways.zarinpal import ZarinpalGateway
from apps.payments.models import GatewayAccount, Payment
from apps.payments.services import handle_callback, online_payment_available, start_payment

pytestmark = pytest.mark.django_db

CHECKOUT = {
    "first_name": "علی", "last_name": "رضایی", "phone": "09121234567", "province": "تهران", "city": "تهران",
    "address": "خیابان", "postal_code": "1234567890", "payment_method": "online", "accept_terms": "on",
}


@pytest.fixture
def order(client):
    variant = VariantFactory(stock=5, price=1_000_000)
    client.post(reverse("cart:add"), {"variant": variant.pk})
    client.post(reverse("orders:checkout"), CHECKOUT)
    return Order.objects.get()


def cb(authority, status="OK"):
    return {"Authority": authority, "Status": status}


# ---------- جریان کامل با درگاه آزمایشی ----------

def test_full_flow_with_test_gateway(client, order):
    resp = client.get(reverse("payments:start", args=[order.number]))
    payment = order.payments.get()
    assert resp.status_code == 302 and resp.url == reverse("payments:test_gateway", args=[payment.authority])
    assert client.get(resp.url).status_code == 200
    resp = client.get(reverse("payments:callback", args=["test"]), cb(payment.authority))
    order.refresh_from_db()
    payment.refresh_from_db()
    assert order.status == "paid" and payment.status == "succeeded" and payment.ref_id
    assert payment.amount == order.total
    detail = client.get(order.get_absolute_url()).content.decode()
    assert "کد پیگیری پرداخت" in detail


def test_callback_is_idempotent(order, store):
    start_payment(order, lambda code: "http://x/cb")
    payment = order.payments.get()
    for _ in range(3):
        handle_callback("test", cb(payment.authority), store)
    order.refresh_from_db()
    assert order.status == "paid" and order.history.filter(to_status="paid").count() == 1


def test_user_cancel_allows_retry(order, store):
    start_payment(order, lambda code: "x")
    first = order.payments.get()
    handle_callback("test", cb(first.authority, "NOK"), store)
    first.refresh_from_db()
    assert first.status == "cancelled"
    start_payment(order, lambda code: "x")
    assert order.payments.count() == 2


def test_expired_order_is_not_verified(order, store):
    start_payment(order, lambda code: "x")
    payment = order.payments.get()
    Order.objects.filter(pk=order.pk).update(status="cancelled", inventory_released=True)
    with mock.patch("apps.payments.gateways.test.TestGateway.verify") as verify:
        handle_callback("test", cb(payment.authority), store)
    verify.assert_not_called()  # تراکنش verify نمی‌شود ← درگاه مبلغ را برمی‌گرداند
    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.status == "expired" and order.status == "cancelled"


def test_start_payment_after_deadline_cancels_order(order):
    Order.objects.filter(pk=order.pk).update(reserved_until=timezone.now() - timedelta(seconds=1))
    order.refresh_from_db()
    with pytest.raises(PaymentError, match="مهلت پرداخت"):
        start_payment(order, lambda code: "x")
    order.refresh_from_db()
    assert order.status == "cancelled" and order.inventory_released


def test_callback_from_other_store_rejected(order, other_store):
    start_payment(order, lambda code: "x")
    with pytest.raises(PaymentError):
        handle_callback("test", cb(order.payments.get().authority), other_store)


def test_unknown_gateway_and_authority(order, store):
    with pytest.raises(PaymentError):
        handle_callback("nope", cb("X"), store)
    with pytest.raises(PaymentError):
        handle_callback("test", cb("NOT-EXISTING"), store)


def test_legacy_callback_url_routes_to_zarinpal(client, order, store):
    GatewayAccount.objects.create(store=store, gateway="zarinpal", merchant_id="m")
    Payment.objects.create(order=order, gateway="zarinpal", amount=order.total, status="pending", authority="A0001")
    resp = client.get("/orders/payment/callback/", cb("A0001", "NOK"))
    assert resp.status_code == 302
    assert Payment.objects.get(authority="A0001").status == "cancelled"


# ---------- در دسترس بودن پرداخت آنلاین ----------

@override_settings(PAYMENT_TEST_GATEWAY_ENABLED=False)
def test_online_availability_depends_on_active_account(store):
    assert not online_payment_available(store)
    account = GatewayAccount.objects.create(store=store, gateway="zarinpal", merchant_id="m")
    assert online_payment_available(store)
    account.is_active = False
    account.save()
    assert not online_payment_available(store)


def test_test_gateway_cannot_be_enabled_in_production():
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.prod", "SECRET_KEY": "k3Y-q9Z_" * 8,
           "PAYMENT_TEST_GATEWAY_ENABLED": "True"}
    out = subprocess.run(
        [sys.executable, "-c", "import django;django.setup();from django.conf import settings;print(settings.PAYMENT_TEST_GATEWAY_ENABLED)"],
        env=env, capture_output=True, text=True, check=True,
    )
    assert out.stdout.strip() == "False"


# ---------- آداپتور زرین‌پال (HTTP شبیه‌سازی‌شده) ----------

class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


@pytest.fixture
def zarinpal(order, store):
    account = GatewayAccount.objects.create(store=store, gateway="zarinpal", merchant_id="MERCHANT", sandbox=True)
    payment = Payment.objects.create(order=order, gateway="zarinpal", amount=1_150_000)
    return ZarinpalGateway(account), payment


def test_zarinpal_initiate(zarinpal):
    gw, payment = zarinpal
    with mock.patch("requests.post", return_value=FakeResponse({"data": {"code": 100, "authority": "A123"}})) as post:
        result = gw.initiate(payment, "https://shop/cb")
    url, kwargs = post.call_args[0][0], post.call_args[1]
    assert url == "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
    assert kwargs["json"]["amount"] == 11_500_000  # تومان × ۱۰ = ریال
    assert kwargs["json"]["merchant_id"] == "MERCHANT" and kwargs["timeout"]
    assert result.authority == "A123" and result.redirect_url.endswith("/pg/StartPay/A123")


def test_zarinpal_initiate_rejected(zarinpal):
    gw, payment = zarinpal
    with mock.patch("requests.post", return_value=FakeResponse({"data": [], "errors": {"code": -9}})):
        with pytest.raises(PaymentError):
            gw.initiate(payment, "x")


def test_zarinpal_network_error(zarinpal):
    import requests

    gw, payment = zarinpal
    with mock.patch("requests.post", side_effect=requests.ConnectionError):
        with pytest.raises(PaymentError, match="ارتباط"):
            gw.initiate(payment, "x")


@pytest.mark.parametrize("code, ok", [(100, True), (101, True), (-51, False)])
def test_zarinpal_verify(zarinpal, code, ok):
    gw, payment = zarinpal
    payment.authority = "A1"
    with mock.patch("requests.post", return_value=FakeResponse({"data": {"code": code, "ref_id": 777, "card_pan": "6037**"}})):
        result = gw.verify(payment, gw.parse_callback(cb("A1")))
    assert result.ok is ok
    if ok:
        assert result.ref_id == "777"


def test_zarinpal_end_to_end_via_service(client, order, store):
    GatewayAccount.objects.create(store=store, gateway="zarinpal", merchant_id="M", sandbox=True)
    responses = [FakeResponse({"data": {"code": 100, "authority": "Z9"}}),
                 FakeResponse({"data": {"code": 100, "ref_id": 4242}})]
    with mock.patch("requests.post", side_effect=responses):
        resp = client.get(reverse("payments:start", args=[order.number]))
        assert resp.url == "https://sandbox.zarinpal.com/pg/StartPay/Z9"
        client.get(reverse("payments:callback", args=["zarinpal"]), cb("Z9"))
    order.refresh_from_db()
    assert order.status == "paid" and order.payments.get().ref_id == "4242"
