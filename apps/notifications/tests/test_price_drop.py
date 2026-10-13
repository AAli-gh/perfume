"""خبر کاهش قیمت محصولات علاقه‌مندی‌ها."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import ProductVariant
from apps.catalog.tests.factories import VariantFactory
from apps.notifications.models import NotificationSettings
from apps.notifications.price_drop import send_alerts
from apps.notifications.sms import console
from apps.wishlist.models import WishlistItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def shopper(client):
    user = get_user_model().objects.create_user(email="w@example.com", password="x-Strong-123", first_name="نسیم",
                                                phone="09121234567")
    client.force_login(user)
    return user


@pytest.fixture
def bottle(store):
    variant = VariantFactory(price=2_000_000, stock=5)
    VariantFactory(product=variant.product, size_ml=5, is_decant=True, price=100_000, stock=5)  # نمونه مبنا نیست
    return variant


def test_wishlist_add_records_bottle_price_and_alerts_once(client, store, shopper, bottle):
    client.post(reverse("wishlist:toggle", args=[bottle.product_id]))
    item = WishlistItem.objects.get()
    assert item.price_seen == 2_000_000 and item.price_alert
    console.outbox.clear()
    assert send_alerts(store) == 0  # قیمت تغییر نکرده
    ProductVariant.objects.filter(pk=bottle.pk).update(price=1_960_000)  # ۲٪: کمتر از حداقل ۵٪
    assert send_alerts(store) == 0
    ProductVariant.objects.filter(pk=bottle.pk).update(sale_price=1_700_000)
    assert send_alerts(store) == 1
    text = console.outbox[-1]["text"]
    assert "۱٬۷۰۰٬۰۰۰" in text and "۱۵٪" in text and bottle.product.get_absolute_url() in text
    item.refresh_from_db()
    assert item.price_seen == 1_700_000 and item.price_alerted_at
    assert send_alerts(store) == 0  # همان کاهش دوباره خبر داده نمی‌شود


def test_alert_respects_toggle_stock_and_store_setting(client, store, shopper, bottle):
    client.post(reverse("wishlist:toggle", args=[bottle.product_id]))
    ProductVariant.objects.filter(pk=bottle.pk).update(price=1_000_000)
    client.post(reverse("wishlist:price_alert", args=[bottle.product_id]), {"enabled": "0"})
    assert send_alerts(store) == 0
    client.post(reverse("wishlist:price_alert", args=[bottle.product_id]), {"enabled": "1"})
    NotificationSettings.objects.update_or_create(store=store, defaults={"price_drop_enabled": False})
    assert send_alerts(store) == 0
    NotificationSettings.objects.filter(store=store).update(price_drop_enabled=True)
    ProductVariant.objects.filter(product=bottle.product).update(stock=0)
    assert send_alerts(store) == 0  # ناموجود: خبر نده
    ProductVariant.objects.filter(pk=bottle.pk).update(stock=3)
    assert send_alerts(store) == 1


def test_legacy_items_get_a_baseline_without_alert(store, shopper, bottle):
    WishlistItem.objects.create(user=shopper, product=bottle.product)
    assert send_alerts(store) == 0 and WishlistItem.objects.get().price_seen == 2_000_000


def test_wishlist_page_shows_toggle(client, store, shopper, bottle):
    client.post(reverse("wishlist:toggle", args=[bottle.product_id]))
    page = client.get(reverse("wishlist:list")).content.decode()
    assert "خبر کاهش قیمت: روشن" in page
    response = client.post(reverse("wishlist:price_alert", args=[bottle.product_id]), {"enabled": "0"},
                           HTTP_HX_REQUEST="true")
    assert "خبر کاهش قیمت: خاموش" in response.content.decode() and not WishlistItem.objects.get().price_alert


def test_command(store):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("send_price_drop_alerts", stdout=out)
    assert "خبر کاهش قیمت ارسال شد" in out.getvalue()
