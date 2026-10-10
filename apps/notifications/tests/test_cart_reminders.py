"""سبد ذخیره‌شده مشتری واردشده، بازگرداندن پس از ورود و پیامک یادآوری سبد رهاشده."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.cart.models import SavedCart
from apps.catalog.tests.factories import VariantFactory
from apps.notifications.cart_reminders import send_reminders
from apps.notifications.services import settings_for
from apps.notifications.sms import console
from apps.orders.tests.test_checkout import VALID

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def _clean():
    console.outbox.clear()


@pytest.fixture
def shopper(client):
    user = User.objects.create_user(email="mina@example.com", password="x-Strong-123", first_name="مینا",
                                    phone="09125550000")
    client.force_login(user)
    return user


def age(cart, hours):
    SavedCart.objects.filter(pk=cart.pk).update(updated_at=timezone.now() - timedelta(hours=hours))


def test_cart_is_saved_and_restored_on_another_device(client, store, shopper, client_class=None):
    v = VariantFactory(stock=5, product__name="عود رازآلود")
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 2})
    saved = SavedCart.objects.get(user=shopper)
    assert saved.items == {str(v.pk): 2}
    from django.test import Client

    other = Client()
    other.post(reverse("accounts:login"), {"username": "mina@example.com", "password": "x-Strong-123"})
    assert other.get(reverse("cart:detail")).context["cart"].lines[0].quantity == 2


def test_reminder_sent_once_after_delay(client, store, shopper):
    v = VariantFactory(stock=5, price=2_000_000, product__name="عود رازآلود")
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 1})
    cart = SavedCart.objects.get()
    assert send_reminders(store) == 0  # هنوز زود است
    age(cart, 4)
    assert send_reminders(store) == 1
    text = console.outbox[-1]["text"]
    assert console.outbox[-1]["to"] == "09125550000" and "مینا عزیز" in text and "عود رازآلود" in text and "/cart/" in text
    assert send_reminders(store) == 0  # یک بار
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 1})  # سبد عوض شد ← یادآوری دوباره مجاز
    age(cart, 4)
    assert send_reminders(store) == 1


def test_no_reminder_after_order_or_when_disabled(client, store, shopper):
    v = VariantFactory(stock=5)
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 1})
    conf = settings_for(store)
    conf.cart_reminder_enabled = False
    conf.save()
    age(SavedCart.objects.get(), 5)
    assert send_reminders(store) == 0
    conf.cart_reminder_enabled = True
    conf.save()
    client.post(reverse("orders:checkout"), VALID)  # سفارش ثبت شد ← سبد خالی
    assert SavedCart.objects.get().items == {}
    assert send_reminders(store) == 0


def test_old_carts_are_not_reminded(client, store, shopper):
    v = VariantFactory(stock=5)
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 1})
    age(SavedCart.objects.get(), 24 * 5)
    assert send_reminders(store) == 0


def test_studio_abandoned_carts_page(client, store, shopper):
    v = VariantFactory(stock=5, price=3_000_000)
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 2})
    from django.contrib.auth.models import Permission

    staff = User.objects.create_user(email="ops2@example.com", password="x-Strong-123", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="view_order"))
    client.force_login(staff)
    page = client.get(reverse("builder:abandoned_carts"))
    assert page.context["total_value"] == 6_000_000 and len(page.context["carts"]) == 1
