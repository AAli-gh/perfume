"""جداسازی داده‌ها بین فروشگاه‌ها (Multi-Tenant readiness)."""

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.blog.models import Category, Post
from apps.catalog.models import Brand
from apps.catalog.tests.factories import BrandFactory, ProductFactory, ScentFactory, VariantFactory
from apps.core.models import Store, StoreDomain
from apps.core.stores import get_current_store, get_default_store, resolve_store, use_store
from apps.discounts.models import Coupon
from apps.marketing.models import NewsletterSubscriber
from apps.orders.models import Order

pytestmark = pytest.mark.django_db
OTHER = {"HTTP_HOST": "second.test"}


def make_product(store, slug="oud", name="عود"):
    product = ProductFactory(
        store=store, slug=slug, name=name,
        brand=BrandFactory(store=store, slug=f"b-{store.code}"),
        scent=ScentFactory(store=store, slug=f"s-{store.code}"),
    )
    variant = VariantFactory(product=product, price=1_000_000)
    return product, variant


# ---------- تشخیص فروشگاه ----------

def test_single_default_store_created_by_migration(store):
    assert store.is_default and store.code == "default"
    assert store.config.shipping_cost > 0


def test_resolve_by_domain_and_fallback(store, other_store):
    assert resolve_store("second.test") == other_store
    assert resolve_store("SECOND.test:8080") == other_store  # پورت و حروف بزرگ نادیده گرفته می‌شوند
    assert resolve_store("unknown.example") == store
    other_store.is_active = False
    other_store.save()
    assert resolve_store("second.test") == store


def test_only_one_default_store_allowed(store):
    with pytest.raises(IntegrityError), transaction.atomic():
        Store.objects.create(name="x", code="x", is_default=True)


def test_model_default_uses_current_store(store, other_store):
    assert Brand.objects.create(name="الف", slug="a").store == store
    with use_store(other_store):
        assert get_current_store() == other_store
        assert Brand.objects.create(name="ب", slug="a").store == other_store  # همان slug در فروشگاه دیگر مجاز است
    assert get_current_store() == store


def test_slug_unique_within_store(store):
    Brand.objects.create(name="الف", slug="dup")
    with pytest.raises(IntegrityError), transaction.atomic():
        Brand.objects.create(name="ب", slug="dup")


def test_middleware_sets_request_store(client, store, other_store):
    assert client.get("/").context["STORE"] == store
    assert client.get("/", **OTHER).context["STORE"] == other_store


def test_site_context_comes_from_store_settings(client, other_store):
    other_store.config.phone = "۰۹۹۹"
    other_store.config.save()
    resp = client.get("/", **OTHER)
    assert resp.context["SITE"]["name"] == "فروشگاه دوم"
    assert resp.context["SITE"]["phone"] == "۰۹۹۹"


# ---------- جداسازی کاتالوگ ----------

def test_products_isolated_per_store(client, store, other_store):
    mine, _ = make_product(store, slug="mine", name="محصول یک")
    theirs, _ = make_product(other_store, slug="theirs", name="محصول دو")

    names = [p.name for p in client.get(reverse("catalog:shop")).context["page"].object_list]
    assert names == ["محصول یک"]
    names = [p.name for p in client.get(reverse("catalog:shop"), **OTHER).context["page"].object_list]
    assert names == ["محصول دو"]

    assert client.get(theirs.get_absolute_url()).status_code == 404
    assert client.get(theirs.get_absolute_url(), **OTHER).status_code == 200


def test_same_slug_in_two_stores_resolves_per_host(client, store, other_store):
    make_product(store, slug="same", name="نسخه اول")
    make_product(other_store, slug="same", name="نسخه دوم")
    assert client.get("/product/same/").context["product"].name == "نسخه اول"
    assert client.get("/product/same/", **OTHER).context["product"].name == "نسخه دوم"


def test_review_cannot_target_other_store_product(client, other_store):
    theirs, _ = make_product(other_store, slug="t")
    resp = client.post(reverse("reviews:create", args=["t"]), {"name": "x", "rating": 5, "text": "متن کافی"})
    assert resp.status_code == 404


# ---------- سبد، تخفیف، سفارش ----------

def test_cart_rejects_variant_from_other_store(client, other_store):
    _, variant = make_product(other_store)
    resp = client.post(reverse("cart:add"), {"variant": variant.pk})
    assert resp.status_code == 404


def test_cart_hides_lines_from_other_store(client, store, other_store):
    _, theirs = make_product(other_store)
    client.post(reverse("cart:add"), {"variant": theirs.pk}, **OTHER)
    assert len(client.get(reverse("cart:detail"), **OTHER).context["cart"]) == 1
    assert client.get(reverse("cart:detail")).context["cart"].is_empty


def test_shipping_cost_from_store_settings(client, store, other_store):
    _, variant = make_product(other_store)
    client.post(reverse("cart:add"), {"variant": variant.pk}, **OTHER)
    assert client.get(reverse("cart:detail"), **OTHER).context["cart"].shipping == 50_000


def test_coupon_scoped_to_store(client, store, other_store):
    _, variant = make_product(store)
    Coupon.objects.create(store=other_store, code="THEIRS", percent=10)
    client.post(reverse("cart:add"), {"variant": variant.pk})
    resp = client.post(reverse("cart:coupon"), {"code": "theirs"}, HTTP_HX_REQUEST="true")
    assert "معتبر نیست" in resp.content.decode()


def test_order_belongs_to_request_store_and_is_private(client, other_store):
    _, variant = make_product(other_store)
    client.post(reverse("cart:add"), {"variant": variant.pk}, **OTHER)
    client.post(reverse("orders:checkout"), {
        "first_name": "علی", "last_name": "رضایی", "phone": "09121234567", "province": "تهران", "city": "تهران",
        "address": "خیابان", "postal_code": "1234567890", "payment_method": "cod", "accept_terms": "on",
    }, **OTHER)
    order = Order.objects.get()
    assert order.store == other_store
    assert client.get(order.get_absolute_url(), **OTHER).status_code == 200
    assert client.get(order.get_absolute_url()).status_code == 404  # از دامنه فروشگاه دیگر دیده نمی‌شود


# ---------- مجله و بازاریابی ----------

def test_blog_isolated(client, store, other_store):
    from apps.catalog.tests.factories import GIF
    from django.core.files.uploadedfile import SimpleUploadedFile

    cat = Category.objects.create(store=other_store, name="دسته", slug="c")
    Post.objects.create(store=other_store, category=cat, title="مقاله دوم", slug="p", excerpt="x", body="y",
                        cover=SimpleUploadedFile("c.gif", GIF))
    assert client.get(reverse("blog:list")).context["total"] == 0
    assert client.get(reverse("blog:list"), **OTHER).context["total"] == 1
    assert client.get("/blog/p/").status_code == 404
    assert client.get("/blog/p/", **OTHER).status_code == 200


def test_newsletter_per_store(client, store, other_store):
    client.post(reverse("marketing:newsletter"), {"email": "a@x.ir"})
    client.post(reverse("marketing:newsletter"), {"email": "a@x.ir"}, **OTHER)
    assert NewsletterSubscriber.objects.count() == 2
    assert {s.store for s in NewsletterSubscriber.objects.all()} == {store, other_store}


def test_default_store_recreated_if_missing():
    StoreDomain.objects.all().delete()
    Store.objects.all().delete()
    store = get_default_store()
    assert store.is_default and store.config is not None
