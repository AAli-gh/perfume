"""مسیرهای خطای پرداخت: درگاه غیرفعال، سفارش منقضی، بازگشت نامعتبر، انتخاب حساب درگاه."""

from datetime import timedelta
from unittest import mock

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order
from apps.payments.gateways import PaymentError
from apps.payments.models import GatewayAccount, Payment
from apps.payments.services import gateway_for

from .test_payments import cb, order  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db


def test_start_without_any_gateway_shows_error(client, order):  # noqa: F811
    with override_settings(PAYMENT_TEST_GATEWAY_ENABLED=False):
        r = client.get(reverse("payments:start", args=[order.number]), follow=True)
    assert "درگاه پرداخت برای این فروشگاه فعال نیست" in r.content.decode()
    assert not order.payments.exists()


def test_start_on_expired_order_cancels_it(client, order):  # noqa: F811
    Order.objects.filter(pk=order.pk).update(reserved_until=timezone.now() - timedelta(minutes=1))
    r = client.get(reverse("payments:start", args=[order.number]), follow=True)
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert "مهلت پرداخت" in r.content.decode()


def test_start_on_paid_order_refused(client, order):  # noqa: F811
    Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID)
    r = client.get(reverse("payments:start", args=[order.number]), follow=True)
    assert "دیگر قابل پرداخت نیست" in r.content.decode()


def test_start_of_someone_elses_order_is_404(order):  # noqa: F811
    from django.test import Client

    assert Client().get(reverse("payments:start", args=[order.number])).status_code == 404


def test_gateway_initiate_failure_marks_payment_failed(client, order, store):  # noqa: F811
    GatewayAccount.objects.create(store=store, gateway="zarinpal", merchant_id="m" * 36, is_active=True)
    with mock.patch("apps.payments.gateways.zarinpal.ZarinpalGateway.initiate",
                    side_effect=PaymentError("درگاه پاسخ نداد")):
        r = client.get(reverse("payments:start", args=[order.number]), follow=True)
    payment = order.payments.get()
    assert payment.status == Payment.Status.FAILED and payment.message == "درگاه پاسخ نداد"
    assert "درگاه پاسخ نداد" in r.content.decode()


def test_callback_with_unknown_authority_goes_home(client, store):
    r = client.get(reverse("payments:callback", args=["test"]), cb("NOPE"), follow=True)
    assert r.redirect_chain[-1][0] == reverse("pages:home")
    assert "تراکنش پیدا نشد" in r.content.decode()


def test_cancelled_and_failed_callbacks(client, order):  # noqa: F811
    start = client.get(reverse("payments:start", args=[order.number]))
    payment = order.payments.get()
    r = client.get(reverse("payments:callback", args=["test"]), cb(payment.authority, "NOK"), follow=True)
    assert "لغو شد" in r.content.decode()
    payment.refresh_from_db()
    assert payment.status == Payment.Status.CANCELLED and start.status_code == 302


def test_gateway_for_selects_requested_account(store):
    GatewayAccount.objects.create(store=store, gateway="zarinpal", merchant_id="a" * 36, is_active=True)
    gateway, account = gateway_for(store, "zarinpal")
    assert gateway.code == "zarinpal" and account.merchant_id == "a" * 36
    gateway, account = gateway_for(store, "test")
    assert gateway.code == "test" and account is None
    with override_settings(PAYMENT_TEST_GATEWAY_ENABLED=False), pytest.raises(PaymentError):
        gateway_for(store, "test")
