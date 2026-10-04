import pytest
from django.urls import reverse

from apps.catalog.tests.factories import ProductFactory
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


def test_review_without_htmx_redirects_with_message(client, store):
    product = ProductFactory()
    r = client.post(reverse("reviews:create", args=[product.slug]), {"name": "ع", "rating": 5, "text": "خوب بود"},
                    follow=True)
    assert r.redirect_chain[-1][0].endswith(product.get_absolute_url() + "#reviews")
    assert "پس از تأیید" in r.content.decode()
    assert not Review.objects.get().is_approved  # پیش از تأیید نمایش داده نمی‌شود


def test_invalid_review_without_htmx(client, store):
    product = ProductFactory()
    client.post(reverse("reviews:create", args=[product.slug]), {"name": "", "rating": 9, "text": ""})
    assert not Review.objects.exists()


def test_review_for_inactive_product_404(client, store):
    product = ProductFactory(is_active=False)
    assert client.post(reverse("reviews:create", args=[product.slug]), {"name": "x"}).status_code == 404
