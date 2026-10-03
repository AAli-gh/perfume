"""مسیرهای بدون HTMX و موارد مرزی سبد خرید."""

import pytest
from django.urls import reverse

from apps.cart.cart import Cart  # noqa: F401
from apps.catalog.tests.factories import VariantFactory
from apps.discounts.models import Coupon

pytestmark = pytest.mark.django_db


def test_add_out_of_stock_without_htmx(client, store):
    variant = VariantFactory(stock=0)
    r = client.post(reverse("cart:add"), {"variant": variant.pk}, follow=True)
    assert "در حال حاضر موجود نیست" in r.content.decode()


def test_update_delta_to_zero_removes_line(client, store):
    variant = VariantFactory(stock=5)
    client.post(reverse("cart:add"), {"variant": variant.pk})
    client.post(reverse("cart:update", args=[variant.pk]), {"delta": "-1"})
    assert client.session.get("cart", {}) in ({}, None) or str(variant.pk) not in client.session.get("cart", {})


def test_update_ignores_variant_not_in_cart(client, store):
    variant = VariantFactory(stock=5)
    r = client.post(reverse("cart:update", args=[variant.pk]), {"quantity": "3"})
    assert r.status_code == 302 and not client.session.get("cart")


def test_update_of_other_store_variant_is_404(client, other_store):
    from apps.core.stores import use_store

    with use_store(other_store):
        variant = VariantFactory(product__store=other_store, product__brand__store=other_store,
                                 product__scent__store=other_store)
    assert client.post(reverse("cart:update", args=[variant.pk]), {"quantity": "1"}).status_code == 404


def test_remove_and_coupon_without_htmx(client, store):
    variant = VariantFactory(stock=5, price=1_000_000)
    Coupon.objects.create(code="OFF", percent=10)
    client.post(reverse("cart:add"), {"variant": variant.pk})
    r = client.post(reverse("cart:coupon"), {"code": "off"}, follow=True)
    assert "OFF" in r.content.decode()
    r = client.post(reverse("cart:coupon"), {"code": "NOPE"}, follow=True)
    assert "کد تخفیف معتبر نیست" in r.content.decode()
    client.post(reverse("cart:coupon_remove"))
    client.post(reverse("cart:remove", args=[variant.pk]))
    r = client.get(reverse("cart:detail"))
    assert "رفتن به فروشگاه" in r.content.decode()  # سبد خالی


def test_coupon_remove_with_htmx(client, store):
    variant = VariantFactory(stock=5)
    client.post(reverse("cart:add"), {"variant": variant.pk})
    r = client.post(reverse("cart:coupon_remove"), HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and 'id="cart-area"' in r.content.decode()
