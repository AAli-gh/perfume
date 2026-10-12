"""مرجوعی، بازپرداخت و لغو بخشی سفارش."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import ProductVariant, StockMovement
from apps.catalog.tests.factories import VariantFactory
from apps.notifications.sms import console
from apps.orders import returns
from apps.orders.models import Order, OrderItem, ReturnRequest
from apps.orders.selectors import remember_order

pytestmark = pytest.mark.django_db
S, R = Order.Status, ReturnRequest


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
    console.outbox.clear()


@pytest.fixture
def order(store):
    a, b = VariantFactory(price=4_000_000, stock=5), VariantFactory(price=2_000_000, stock=5)
    o = Order.objects.create(store=store, first_name="نگار", last_name="ک", phone="09121110000", province="تهران",
                             city="تهران", address="x", postal_code="1234567890", subtotal=10_000_000,
                             discount=1_000_000, shipping=100_000, total=9_100_000, status=S.SHIPPED,
                             payment_method=Order.PaymentMethod.ONLINE, paid_at=timezone.now(),
                             shipped_at=timezone.now())
    ia = OrderItem.objects.create(order=o, variant=a, product_name="عود", size_ml=50, unit_price=4_000_000, quantity=2)
    ib = OrderItem.objects.create(order=o, variant=b, product_name="رز", size_ml=50, unit_price=2_000_000, quantity=1)
    return {"order": o, "a": a, "b": b, "ia": ia, "ib": ib}


def test_refund_amount_excludes_discount_share(order):
    assert returns.refund_for(order["order"], {order["ia"]: 1}) == 3_600_000  # ۴م منهای ۱۰٪ سهم تخفیف


def test_full_return_flow_restocks_and_refunds(order):
    req = returns.request_return(order["order"], {order["ia"]: 1}, reason=R.Reason.DAMAGED, description="شکسته")
    assert req.refund_amount == 3_600_000 and req.status == R.Status.REQUESTED
    with pytest.raises(returns.ReturnError):  # بیشتر از باقی‌مانده
        returns.request_return(order["order"], {order["ia"]: 2}, reason=R.Reason.OTHER)
    returns.approve(req)
    returns.receive(req)
    assert ProductVariant.objects.get(pk=order["a"].pk).stock == 6
    assert order["a"].movements.latest("pk").reason == StockMovement.Reason.RETURNED
    order["ia"].refresh_from_db()
    assert order["ia"].returned_quantity == 1
    returns.refund(req, amount=3_600_000, method=R.RefundMethod.CARD, reference="TRX-1")
    req.refresh_from_db()
    assert req.status == R.Status.REFUNDED and req.refunded_at
    assert any("بازپرداخت شد" in m["text"] for m in console.outbox)


def test_receive_without_restock(order):
    req = returns.request_return(order["order"], {order["ib"]: 1}, reason=R.Reason.DAMAGED)
    returns.receive(req, restock=False)
    assert ProductVariant.objects.get(pk=order["b"].pk).stock == 5


def test_customer_request_window(client, order, store):
    o = order["order"]
    session = client.session
    remember_order(type("R", (), {"session": session, "user": type("U", (), {"is_authenticated": False})()})(), o)
    session.save()
    page = client.get(o.get_absolute_url())
    assert page.context["can_return"] and "درخواست مرجوعی" in page.content.decode()
    client.post(reverse("orders:request_return", args=[o.number]),
                {f"qty-{order['ib'].pk}": "1", "reason": "changed_mind", "description": "اندازه"})
    req = ReturnRequest.objects.get()
    assert req.by_customer and req.items.get().quantity == 1
    assert not client.get(o.get_absolute_url()).context["can_return"]  # درخواست باز دارد
    Order.objects.filter(pk=o.pk).update(shipped_at=timezone.now() - timedelta(days=30))
    req.status = R.Status.REJECTED
    req.save()
    assert not returns.customer_can_request(Order.objects.get(pk=o.pk))  # مهلت ۷ روزه گذشته


def test_partial_cancel_before_shipping(order):
    o = order["order"]
    Order.objects.filter(pk=o.pk).update(status=S.PROCESSING)
    req = returns.partial_cancel(Order.objects.get(pk=o.pk), {order["ia"]: 1}, reason=R.Reason.OUT_OF_STOCK)
    o.refresh_from_db()
    assert (o.subtotal, o.discount, o.total) == (6_000_000, 600_000, 5_500_000)
    assert req.kind == R.Kind.CANCEL and req.status == R.Status.RECEIVED and req.refund_amount == 3_600_000
    assert ProductVariant.objects.get(pk=order["a"].pk).stock == 6
    assert o.history.filter(note__startswith="لغو بخشی").exists()
    with pytest.raises(returns.ReturnError):  # همه اقلام ← لغو کل سفارش
        returns.partial_cancel(o, {order["ia"]: 1, order["ib"]: 1}, reason=R.Reason.OTHER)


def test_partial_cancel_unpaid_cod_closes_without_refund(order):
    o = order["order"]
    Order.objects.filter(pk=o.pk).update(status=S.PENDING, paid_at=None, payment_method=Order.PaymentMethod.COD)
    req = returns.partial_cancel(Order.objects.get(pk=o.pk), {order["ib"]: 1}, reason=R.Reason.OUT_OF_STOCK)
    assert req.status == R.Status.CLOSED and req.refund_amount == 0
    assert Order.objects.get(pk=o.pk).total == 9_100_000 - 1_800_000


def test_studio_return_actions(client, order):
    user = get_user_model().objects.create_user(email="r@example.com", password="x-Strong-123", is_staff=True)
    for codename in ("view_order", "change_order"):
        user.user_permissions.add(Permission.objects.get(codename=codename))
    client.force_login(user)
    o = order["order"]
    response = client.post(reverse("builder:order_adjust", args=[o.pk]),
                           {f"qty-{order['ia'].pk}": "2", "reason": "wrong"})
    req = ReturnRequest.objects.get()
    assert response.status_code == 302 and not req.by_customer
    client.post(reverse("builder:return", args=[req.pk]), {"action": "approve"})
    client.post(reverse("builder:return", args=[req.pk]), {"action": "receive", "restock": "on"})
    client.post(reverse("builder:return", args=[req.pk]), {"action": "refund", "amount": "۷٬۲۰۰٬۰۰۰",
                                                           "method": "gateway", "reference": "X"})
    req.refresh_from_db()
    assert (req.status, req.refund_amount) == (R.Status.REFUNDED, 7_200_000)
    assert ProductVariant.objects.get(pk=order["a"].pk).stock == 7
    assert client.get(reverse("builder:returns"), {"show": "all"}).status_code == 200


def test_studio_return_errors_and_edge_cases(client, order):
    user = get_user_model().objects.create_user(email="r2@example.com", password="x-Strong-123", is_staff=True)
    for codename in ("view_order", "change_order"):
        user.user_permissions.add(Permission.objects.get(codename=codename))
    client.force_login(user)
    o = order["order"]
    adjust = reverse("builder:order_adjust", args=[o.pk])
    assert client.get(adjust).status_code == 200
    # علت انتخاب نشده
    assert client.post(adjust, {f"qty-{order['ia'].pk}": "1", "reason": "nope"})["Location"] == adjust
    # بدون کالا
    assert client.post(adjust, {"reason": "wrong"})["Location"] == adjust
    assert not ReturnRequest.objects.exists()
    assert client.get(reverse("builder:order_adjust", args=[999999])).status_code == 404
    client.post(adjust, {f"qty-{order['ia'].pk}": "1", "reason": "wrong"})
    req = ReturnRequest.objects.get()
    detail = reverse("builder:return", args=[req.pk])
    assert client.post(detail, {"action": "bogus"}).status_code == 404
    client.post(detail, {"action": "approve"})
    client.post(detail, {"action": "receive"})
    # روش بازپرداخت نامعتبر و مبلغ نامعتبر
    assert client.post(detail, {"action": "refund", "amount": "100", "method": "cash?"})["Location"] == detail
    assert client.post(detail, {"action": "refund", "amount": "abc", "method": "gateway"})["Location"] == detail
    req.refresh_from_db()
    assert req.refunded_at is None
    # سفارش لغوشده ← امکان مرجوعی نیست
    Order.objects.filter(pk=o.pk).update(status=S.CANCELLED)
    assert client.get(adjust)["Location"] == reverse("builder:orders")
