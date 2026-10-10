"""کارت هدیه و امتیاز باشگاه مشتریان: پیش‌نمایش، خرج در سفارش، لغو، کسب امتیاز، خرید کارت و استودیو."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.catalog.profile import Kind
from apps.catalog.tests.factories import ProductFactory, VariantFactory
from apps.discounts import credits
from apps.discounts.models import GiftCard, LoyaltyEntry
from apps.notifications.sms import console
from apps.orders.models import Order, ReturnRequest
from apps.orders import returns
from apps.orders.tests.test_checkout import VALID
from apps.orders.workflow import transition

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
    console.outbox.clear()


@pytest.fixture
def club(store):
    config = store.config
    config.shipping_cost, config.free_shipping_over = 100_000, 0
    config.loyalty_enabled, config.loyalty_earn_per, config.loyalty_point_value = True, 100_000, 1000
    config.loyalty_min_redeem, config.loyalty_max_percent = 50, 50
    config.save()
    return config


@pytest.fixture
def shopper(client):
    user = User.objects.create_user(email="c@example.com", password="x-Strong-123", first_name="سارا",
                                    phone="09123334455")
    client.force_login(user)
    return user


def add(client, price=2_000_000, qty=1):
    v = VariantFactory(price=price, stock=10)
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": qty})
    return v


def test_gift_card_partial_payment_and_restore_on_cancel(client, store, club, shopper):
    card = credits.issue_card(store, 500_000)
    add(client)
    page = client.post(reverse("orders:quote"), {**VALID, "gift_card": credits.format_code(card.code).lower()},
                       HTTP_HX_REQUEST="true")
    assert "کارت هدیه" in page.content.decode() and page.context["credits"].payable == 1_600_000
    client.post(reverse("orders:checkout"), {**VALID, "gift_card": card.code})
    order = Order.objects.get()
    card.refresh_from_db()
    assert (order.gift_card_amount, order.total, card.balance) == (500_000, 1_600_000, 0)
    assert card.transactions.filter(amount=-500_000, order_number=order.number).exists()
    transition(order, Order.Status.CANCELLED)
    card.refresh_from_db()
    assert card.balance == 500_000


def test_invalid_gift_card_is_a_form_error(client, store, club, shopper):
    add(client)
    response = client.post(reverse("orders:checkout"), {**VALID, "gift_card": "NOPE-NOPE"})
    assert response.status_code == 422 and "کارت هدیه پیدا نشد" in response.content.decode()


def test_gift_card_covering_everything_marks_order_paid(client, store, club, shopper):
    card = credits.issue_card(store, 10_000_000)
    add(client)
    response = client.post(reverse("orders:checkout"), {**VALID, "payment_method": "online", "gift_card": card.code})
    order = Order.objects.get()
    assert response["Location"] == order.get_absolute_url()
    assert order.total == 0 and order.status == Order.Status.PAID and order.paid_at


def test_points_earn_redeem_and_cap(client, store, club, shopper):
    add(client, price=3_000_000)
    client.post(reverse("orders:checkout"), VALID)
    order = Order.objects.get()
    for status in (Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.DELIVERED):
        transition(order, status)
    assert credits.points_balance(store, shopper) == 30  # ۳ میلیون بدون ارسال
    credits.add_points(store, shopper, 2000, LoyaltyEntry.Reason.MANUAL)
    add(client, price=1_000_000)
    checkout = client.get(reverse("cart:detail")).context
    assert 'name="use_points"' in client.get(reverse("cart:detail")).content.decode()
    del checkout
    client.post(reverse("orders:checkout"), {**VALID, "use_points": "on"})
    second = Order.objects.latest("pk")
    # سقف ۵۰٪ از ۱٬۱۰۰٬۰۰۰ ← ۵۵۰ امتیاز
    assert (second.points_used, second.points_amount, second.total) == (550, 550_000, 550_000)
    assert credits.points_balance(store, shopper) == 2030 - 550
    transition(second, Order.Status.CANCELLED)
    assert credits.points_balance(store, shopper) == 2030


def test_points_hidden_when_club_disabled_or_below_minimum(client, store, shopper):
    add(client)
    assert 'name="use_points"' not in client.get(reverse("cart:detail")).content.decode()


def test_purchased_gift_card_issued_after_payment_with_sms(client, store, club, shopper):
    product = ProductFactory(kind=Kind.GIFT_CARD, scent=None, name="کارت هدیه")
    v = VariantFactory(product=product, size_ml=0, price=1_000_000, stock=1000)
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 2})
    client.post(reverse("orders:checkout"), {**VALID, "payment_method": "card", "gift_from": "مریم"})
    order = Order.objects.get()
    assert not GiftCard.objects.exists()
    console.outbox.clear()
    transition(order, Order.Status.PAID)
    cards = GiftCard.objects.filter(order_number=order.number)
    assert cards.count() == 2 and all(c.balance == 1_000_000 and c.sender_name == "مریم" for c in cards)
    texts = [m["text"] for m in console.outbox if "کارت هدیه" in m["text"]]
    assert len(texts) == 2 and re.search(r"[A-Z0-9]{4}-[A-Z0-9]{4}", texts[0])
    page = client.get(order.get_absolute_url()).content.decode()
    assert "کارت‌های هدیه شما" in page
    transition(order, Order.Status.CANCELLED)
    assert not GiftCard.objects.filter(order_number=order.number, is_active=True).exists()


def test_refund_as_store_credit_issues_card(store, club):
    v = VariantFactory(price=2_000_000, stock=3)
    order = Order.objects.create(store=store, first_name="x", last_name="y", phone="09120000000", province="تهران",
                                 city="تهران", address="a", postal_code="1234567890", subtotal=2_000_000,
                                 total=2_000_000, status=Order.Status.DELIVERED)
    from apps.orders.models import OrderItem

    item = OrderItem.objects.create(order=order, variant=v, product_name="عود", size_ml=50, unit_price=2_000_000,
                                    quantity=1)
    req = returns.request_return(order, {item: 1}, reason=ReturnRequest.Reason.CHANGED_MIND)
    returns.receive(req)
    returns.refund(req, amount=2_000_000, method=ReturnRequest.RefundMethod.CREDIT)
    card = GiftCard.objects.get(source=GiftCard.Source.REFUND)
    req.refresh_from_db()
    assert card.balance == 2_000_000 and req.refund_reference == card.code


def test_studio_issue_gift_cards_and_adjust_points(client, store, club, shopper):
    Order.objects.create(store=store, user=shopper, first_name="سارا", last_name="ی", phone="09123334455",
                         province="تهران", city="تهران", address="a", postal_code="1234567890", total=1_000_000,
                         subtotal=1_000_000, payment_method=Order.PaymentMethod.COD)
    staff = User.objects.create_user(email="gc@example.com", password="x-Strong-123", is_staff=True)
    for codename in ("change_product", "view_user", "change_user"):
        staff.user_permissions.add(Permission.objects.get(codename=codename))
    client.force_login(staff)
    response = client.post(reverse("builder:gift_cards"), {"amount": "۵۰۰٬۰۰۰", "count": "3",
                                                           "recipient_phone": "09121112222", "message": "تولدت مبارک"})
    assert response.status_code == 302 and GiftCard.objects.count() == 3
    assert len([m for m in console.outbox if m["to"] == "09121112222"]) == 3
    client.post(reverse("builder:customer_points", args=["09123334455"]), {"points": "120", "note": "جبران تأخیر"})
    assert credits.points_balance(store, shopper) == 120
    page = client.get(reverse("builder:customer", args=["09123334455"]))
    assert page.context["account"].points == 120
