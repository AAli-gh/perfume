"""دکانت (نمونه) و باکس تست: انتخاب نمونه، سبد، ثبت سفارش، موجودی و نمایش."""

import pytest
from django.urls import reverse

from apps.catalog import samples, selectors
from apps.catalog.models import Product, ProductVariant
from apps.catalog.profile import Kind
from apps.catalog.tests.factories import ProductFactory, VariantFactory
from apps.orders.models import Order, OrderItem
from apps.orders.tests.test_checkout import VALID
from apps.orders.workflow import transition

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())


@pytest.fixture
def perfumes(store):
    out = []
    for i in range(4):
        p = ProductFactory(name=f"عطر {i}")
        VariantFactory(product=p, size_ml=50, price=2_000_000, stock=5)
        out.append(VariantFactory(product=p, size_ml=5, is_decant=True, price=150_000, stock=3))
    return out


@pytest.fixture
def box(store, perfumes):
    product = ProductFactory(name="باکس تست", kind=Kind.SAMPLE_BOX, scent=None, sample_count=3)
    return VariantFactory(product=product, size_ml=5, price=500_000, stock=10)


def add_box(client, box, picks, quantity=1):
    return client.post(reverse("cart:add"), {"variant": box.pk, "quantity": quantity,
                                             "samples": [p.pk for p in picks]})


def test_validate_picks_rules(box, perfumes):
    assert samples.validate_picks(box, [p.pk for p in perfumes[:3]]) == perfumes[:3]
    for bad in ([perfumes[0].pk] * 3, [p.pk for p in perfumes[:2]], [p.pk for p in perfumes], ["x"]):
        with pytest.raises(samples.PickError):
            samples.validate_picks(box, bad)
    bottle = ProductVariant.objects.filter(product=perfumes[0].product, is_decant=False).first()
    with pytest.raises(samples.PickError):  # شیشه کامل نمونه نیست
        samples.validate_picks(box, [bottle.pk, perfumes[1].pk, perfumes[2].pk])
    with pytest.raises(samples.PickError, match="به این تعداد"):
        samples.validate_picks(box, [p.pk for p in perfumes[:3]], quantity=4)
    assert set(samples.sample_choices(box.product.store, 5)) == set(perfumes)


def test_box_order_reserves_samples_and_cancel_releases(client, box, perfumes):
    assert add_box(client, box, perfumes[:3]).status_code == 302
    cart_page = client.get(reverse("cart:detail")).content.decode()
    assert "عطر 0، عطر 1، عطر 2" in cart_page
    client.post(reverse("orders:checkout"), VALID)
    order = Order.objects.get()
    parent = order.items.get(parent=None)
    assert parent.unit_price == 500_000 and order.subtotal == 500_000
    contents = list(parent.contents.order_by("product_name"))
    assert [c.product_name for c in contents] == ["عطر 0", "عطر 1", "عطر 2"]
    assert all(c.unit_price == 0 and c.size_ml == 5 for c in contents)
    stock = lambda v: ProductVariant.objects.get(pk=v.pk).stock  # noqa: E731
    assert stock(box) == 9 and [stock(p) for p in perfumes] == [2, 2, 2, 3]
    assert order.line_items == [parent]
    transition(order, Order.Status.CANCELLED)
    assert stock(box) == 10 and [stock(p) for p in perfumes] == [3, 3, 3, 3]


def test_box_without_valid_picks_is_rejected_or_dropped(client, box, perfumes):
    response = client.post(reverse("cart:add"), {"variant": box.pk, "samples": [perfumes[0].pk]})
    assert response.status_code == 302 and response["Location"] == box.product.get_absolute_url()
    assert client.get(reverse("cart:detail")).context["cart"].is_empty
    add_box(client, box, perfumes[:3])
    Product.objects.filter(pk=perfumes[1].product_id).update(is_active=False)  # یک نمونه دیگر در دسترس نیست
    assert client.get(reverse("cart:detail")).context["cart"].is_empty  # باکس بدون نمونه معتبر حذف شد


def test_box_return_restocks_contents(client, box, perfumes):
    from apps.orders import returns

    add_box(client, box, perfumes[:3])
    client.post(reverse("orders:checkout"), VALID)
    order = Order.objects.get()
    for status in (Order.Status.PROCESSING, Order.Status.SHIPPED):
        transition(order, status)
    available = returns.available(order)
    assert list(available) == [order.items.get(parent=None)]  # نمونه‌ها جدا مرجوع نمی‌شوند
    req = returns.request_return(order, {item: 1 for item in available}, reason="changed_mind")
    returns.receive(req)
    assert [ProductVariant.objects.get(pk=p.pk).stock for p in perfumes[:3]] == [3, 3, 3]
    assert set(OrderItem.objects.filter(order=order).values_list("returned_quantity", flat=True)) == {1}


def test_prices_and_pages(client, store, box, perfumes):
    listed = {p.pk: p for p in selectors.listable_products(store)}
    perfume = listed[perfumes[0].product_id]
    assert perfume.min_price == 2_000_000 and perfume.decant_price == 150_000  # کارت: قیمت شیشه، نه نمونه
    assert perfumes[0].product.default_variant.size_ml == 50
    page = client.get(perfumes[0].product.get_absolute_url()).content.decode()
    assert "۵ میل · نمونه" in page and "اول امتحان کنید" in page and box.product.name in page
    assert page.index("۵۰ میل") < page.index("۵ میل · نمونه")  # شیشه‌ها اول
    box_page = client.get(box.product.get_absolute_url()).content.decode()
    assert box_page.count('name="samples"') == 4 and 'data-max="3"' in box_page
    samples_page = client.get(reverse("catalog:samples")).content.decode()
    assert "باکس تست" in samples_page and "نمونه برای امتحان" in samples_page
