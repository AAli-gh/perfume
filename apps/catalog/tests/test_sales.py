"""حراج زمان‌دار: قیمت فعلی، نمایش، سبد، سفارش، جستجو و ابزار استودیو."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.catalog import sales, selectors
from apps.catalog.models import ProductVariant, SaleCampaign
from apps.catalog.tests.factories import BrandFactory, ProductFactory, VariantFactory
from apps.core.jalali import parse_jalali, to_jalali_text

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())


def test_current_price_respects_window(store):
    v = VariantFactory(price=4_000_000, sale_price=3_000_000)
    assert v.on_sale and v.current_price == 3_000_000 and v.discount_percent == 25
    v.sale_starts_at = timezone.now() + timedelta(days=1)
    assert not v.on_sale and v.current_price == 4_000_000
    v.sale_starts_at, v.sale_ends_at = None, timezone.now() - timedelta(minutes=1)
    assert v.current_price == 4_000_000
    v.sale_ends_at, v.sale_price = None, 4_500_000  # بیشتر از قیمت اصلی ← حراج نیست
    assert v.current_price == 4_000_000


def test_listing_uses_sale_price_for_min_price_sort_and_filter(store):
    cheap = VariantFactory(price=3_000_000, product__name="ارزان")
    sale = VariantFactory(price=5_000_000, sale_price=2_500_000, product__name="حراجی")
    products = list(selectors.listable_products(store).order_by("min_price"))
    assert [p.name for p in products] == ["حراجی", "ارزان"]
    assert products[0].min_regular_price == 5_000_000
    found = selectors.filter_products(store, selectors.ProductFilters(max_price=2_800_000))
    assert [p.name for p in found] == ["حراجی"]
    assert cheap and sale


def test_card_product_page_and_cart_show_sale(client, store):
    v = VariantFactory(price=5_000_000, sale_price=4_000_000, sale_ends_at=timezone.now() + timedelta(days=3))
    page = client.get(v.product.get_absolute_url()).content.decode()
    assert "۴٬۰۰۰٬۰۰۰" in page and "<del" in page and "۲۰٪ تخفیف" in page and "حراج تا" in page
    shop = client.get(reverse("catalog:shop")).content.decode()
    assert "sale-badge" in shop and "۵٬۰۰۰٬۰۰۰" in shop
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 2})
    cart = client.get(reverse("cart:detail"))
    assert cart.context["cart"].subtotal == 8_000_000


def test_order_stores_sale_price(client, store):
    from apps.orders.models import Order
    from apps.orders.tests.test_checkout import VALID

    v = VariantFactory(price=5_000_000, sale_price=4_000_000)
    client.post(reverse("cart:add"), {"variant": v.pk, "quantity": 1})
    client.post(reverse("orders:checkout"), VALID)
    order = Order.objects.get()
    assert order.items.get().unit_price == 4_000_000 and order.subtotal == 4_000_000


def test_campaign_create_and_end(store):
    brand = BrandFactory(name="رویال", slug="royal")
    a = VariantFactory(price=5_230_000, product__brand=brand)
    b = VariantFactory(price=3_000_000)
    campaign, applied, replaced = sales.create_campaign(
        store, ProductVariant.objects.filter(product__brand=brand), name="حراج پاییزه", percent=20, rounding=10_000)
    a.refresh_from_db()
    b.refresh_from_db()
    assert (applied, replaced) == (1, 0) and a.sale_price == 4_180_000 and b.sale_price is None
    assert campaign.status() == "active"
    sales.end_campaign(campaign)
    a.refresh_from_db()
    assert a.sale_price is None and campaign.status() == "ended"


def test_jalali_parsing():
    _date, moment, has_time = parse_jalali("۱۴۰۵/۰۷/۱۸ ۱۴:۳۰")
    assert (moment.year, moment.month, moment.day, moment.hour, moment.minute, has_time) == (2026, 10, 10, 14, 30, True)
    _date, moment, _ = parse_jalali("1405-08-01", end_of_day=True)
    assert (moment.month, moment.day, moment.hour, moment.minute) == (10, 23, 23, 59)
    with pytest.raises(ValueError):
        parse_jalali("1405/13/01")
    assert to_jalali_text(timezone.make_aware(timezone.datetime(2026, 10, 10, 9, 5))) == "۱۴۰۵/۰۷/۱۸ ۰۹:۰۵"


def test_studio_sale_with_jalali_dates(client, store):
    user = User.objects.create_user(email="s@example.com", password="x-Strong-123", is_staff=True)
    user.user_permissions.add(Permission.objects.get(codename="change_product"))
    client.force_login(user)
    v = VariantFactory(price=4_000_000)
    response = client.post(reverse("builder:sales"), {
        "name": "یلدا", "percent": "15", "starts_at": "۱۴۰۵/۰۹/۲۵", "ends_at": "۱۴۰۵/۰۹/۳۰", "rounding": "0"})
    assert response.status_code == 302
    campaign = SaleCampaign.objects.get()
    v.refresh_from_db()
    assert v.sale_price == 3_400_000 and campaign.status() == "scheduled"
    assert timezone.localtime(campaign.ends_at).hour == 23  # «تا ۳۰ آذر» یعنی تا پایان آن روز
    assert v.current_price == 4_000_000  # هنوز شروع نشده
    bad = client.post(reverse("builder:sales"), {"name": "x", "percent": "10", "ends_at": "۱۳۹۰/۰۱/۰۱",
                                                 "rounding": "0"})
    assert bad.status_code == 422
    client.post(reverse("builder:sale_end", args=[campaign.pk]))
    v.refresh_from_db()
    assert v.sale_price is None


def test_admin_variant_inline_uses_jalali_dates(admin_client, store):
    product = ProductFactory()
    VariantFactory(product=product, sale_price=1, sale_ends_at=timezone.now())
    page = admin_client.get(reverse("admin:catalog_product_change", args=[product.pk])).content.decode()
    assert 'data-jalali="datetime"' in page and "jalali-picker.js" in page
