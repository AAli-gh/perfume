"""معرفی به دوستان: لینک دعوت، کد تخفیف دوست، پاداش معرف پس از تحویل اولین سفارش."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.tests.factories import VariantFactory
from apps.discounts import credits, referrals
from apps.discounts.models import Coupon, LoyaltyEntry, Referral
from apps.notifications.sms import console
from apps.orders.models import Order
from apps.orders.tests.test_checkout import VALID
from apps.orders.workflow import transition

pytestmark = pytest.mark.django_db
User = get_user_model()
SIGNUP = {"first_name": "سارا", "last_name": "ی", "password1": "Atr-Majd-2026!", "password2": "Atr-Majd-2026!"}


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
    console.outbox.clear()


@pytest.fixture
def program(store):
    conf = store.config
    conf.referral_enabled, conf.referral_friend_percent, conf.referral_reward_points = True, 15, 200
    conf.loyalty_enabled = True
    conf.save()
    return conf


@pytest.fixture
def referrer(store):
    return User.objects.create_user(email="ali@example.com", password="x-Strong-123", first_name="علی",
                                    phone="09125550000")


def deliver(order):
    for status in (Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.DELIVERED):
        transition(order, status)


def test_invite_link_signup_coupon_and_reward(client, store, program, referrer):
    code = referrals.code_for(store, referrer).code
    assert referrals.code_for(store, referrer).code == code  # پایدار
    response = client.get(reverse("referral", args=[code]))
    assert response["Location"] == reverse("accounts:register")
    client.post(reverse("accounts:register"), {**SIGNUP, "email": "sara@example.com"})
    ref = Referral.objects.get()
    assert ref.referrer == referrer and ref.friend.email == "sara@example.com"
    coupon = Coupon.objects.get(code=ref.friend_coupon)
    assert coupon.percent == 15 and coupon.usage_limit == 1 and coupon.max_discount == 500_000
    profile = client.get(reverse("accounts:profile")).content.decode()
    assert ref.friend_coupon in profile and "/r/" in profile

    variant = VariantFactory(price=2_000_000, stock=5)
    client.post(reverse("cart:add"), {"variant": variant.pk})
    client.post(reverse("cart:coupon"), {"code": ref.friend_coupon})
    client.post(reverse("orders:checkout"), VALID)
    order = Order.objects.get()
    assert order.coupon_code == ref.friend_coupon and order.discount == 300_000
    transition(order, Order.Status.PAID)
    ref.refresh_from_db()
    assert ref.status == Referral.Status.PENDING  # فقط پس از تحویل
    deliver(order)
    ref.refresh_from_db()
    assert ref.status == Referral.Status.REWARDED and ref.reward_points == 200 and ref.order_number == order.number
    assert credits.points_balance(store, referrer) == 200
    assert LoyaltyEntry.objects.filter(reason=LoyaltyEntry.Reason.REFERRAL).count() == 1
    assert any(m["to"] == "09125550000" and "۲۰۰ امتیاز" in m["text"] for m in console.outbox)
    assert referrals.reward_for_order(order) is None  # یک بار


def test_reward_is_coupon_when_loyalty_is_off(client, store, program, referrer):
    program.loyalty_enabled = False
    program.save()
    friend = User.objects.create_user(email="f@example.com", password="x")
    ref = referrals.attach(store, friend, referrals.code_for(store, referrer).code)
    order = Order.objects.create(store=store, user=friend, first_name="f", last_name="f", phone="09120000001",
                                 province="تهران", city="تهران", address="a", postal_code="1234567890",
                                 subtotal=1_000_000, total=1_000_000, payment_method=Order.PaymentMethod.COD)
    deliver(order)
    ref.refresh_from_db()
    assert ref.status == Referral.Status.REWARDED and ref.reward_coupon.startswith("TY")
    assert Coupon.objects.filter(code=ref.reward_coupon, usage_limit=1).exists()


def test_attach_rules(store, program, referrer):
    code = referrals.code_for(store, referrer).code
    assert referrals.attach(store, referrer, code) is None  # خودش را دعوت نمی‌کند
    old = User.objects.create_user(email="old@example.com", password="x")
    User.objects.filter(pk=old.pk).update(date_joined="2020-01-01T00:00Z")
    old.refresh_from_db()
    assert referrals.attach(store, old, code) is None  # فقط حساب تازه
    assert referrals.attach(store, User.objects.create_user(email="n@example.com", password="x"), "NOPE") is None
    new = User.objects.create_user(email="new@example.com", password="x")
    assert referrals.attach(store, new, code.lower()) is not None
    assert referrals.attach(store, new, code) is None  # فقط یک معرف
    program.referral_enabled = False
    program.save()
    assert referrals.attach(store, User.objects.create_user(email="z@example.com", password="x"), code) is None


def test_disabled_program_hides_panel_and_link_does_nothing(client, store, referrer):
    client.force_login(referrer)
    assert "دعوت از دوستان" not in client.get(reverse("accounts:profile")).content.decode()
    client.logout()
    assert client.get(reverse("referral", args=["ANY"]))["Location"] == reverse("pages:home")
