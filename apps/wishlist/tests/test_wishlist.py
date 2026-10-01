import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.tests.factories import ProductFactory, VariantFactory
from apps.wishlist.models import WishlistItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user("w@x.ir", "Atr-Majd-2026!")


@pytest.fixture
def product():
    p = ProductFactory(name="عود")
    VariantFactory(product=p)
    return p


def test_toggle_with_htmx(client, user, product):
    client.force_login(user)
    url = reverse("wishlist:toggle", args=[product.pk])
    resp = client.post(url, HTTP_HX_REQUEST="true")
    assert "در فهرست علاقه‌مندی‌ها" in resp.content.decode()
    assert WishlistItem.objects.filter(user=user, product=product).exists()
    client.post(url, HTTP_HX_REQUEST="true")
    assert not WishlistItem.objects.exists()


def test_anonymous_redirected_to_login(client, product):
    resp = client.post(reverse("wishlist:toggle", args=[product.pk]), HTTP_HX_REQUEST="true")
    assert resp.status_code == 204 and resp["HX-Redirect"].startswith(reverse("accounts:login"))
    resp = client.post(reverse("wishlist:toggle", args=[product.pk]))
    assert resp.status_code == 302 and "login" in resp.url
    assert not WishlistItem.objects.exists()


def test_list_page_and_product_button_state(client, user, product):
    client.force_login(user)
    client.post(reverse("wishlist:toggle", args=[product.pk]))
    assert "عود" in client.get(reverse("wishlist:list")).content.decode()
    assert 'aria-pressed="true"' in client.get(product.get_absolute_url()).content.decode()


def test_cannot_wishlist_other_store_product(client, user, other_store):
    from apps.catalog.tests.factories import BrandFactory, ScentFactory

    theirs = ProductFactory(store=other_store, brand=BrandFactory(store=other_store), scent=ScentFactory(store=other_store))
    client.force_login(user)
    assert client.post(reverse("wishlist:toggle", args=[theirs.pk])).status_code == 404


def test_wishlist_requires_login(client):
    assert client.get(reverse("wishlist:list")).status_code == 302
