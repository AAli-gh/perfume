import pytest

from apps.catalog import selectors
from apps.catalog.forms import ReviewForm
from apps.catalog.services import submit_review

from .factories import CollectionFactory, ProductFactory, ReviewFactory, ScentFactory, VariantFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog():
    floral = ScentFactory(slug="floral", name="گلی")
    col = CollectionFactory(slug="spring")
    rose = ProductFactory(name="گل سرخ", scent=floral, collection=col)
    oud = ProductFactory(name="عود شب", notes_middle="قلب عود")
    hidden = ProductFactory(name="مخفی", is_active=False)
    VariantFactory(product=rose, price=2_000_000)
    VariantFactory(product=rose, size_ml=100, price=3_000_000)
    VariantFactory(product=oud, price=5_000_000)
    VariantFactory(product=hidden, price=1_000_000)
    ReviewFactory(product=oud, rating=5)
    ReviewFactory(product=rose, rating=3)
    ReviewFactory(product=rose, rating=1, is_approved=False)
    return {"rose": rose, "oud": oud, "hidden": hidden, "col": col}


def names(qs):
    return [p.name for p in qs]


def test_listable_products_excludes_inactive_and_annotates(catalog):
    by_name = {p.name: p for p in selectors.listable_products()}
    assert set(by_name) == {"گل سرخ", "عود شب"}
    assert by_name["گل سرخ"].min_price == 2_000_000
    assert by_name["گل سرخ"].review_count == 1  # نظر تأییدنشده شمرده نمی‌شود
    assert by_name["گل سرخ"].rating_avg == 3


def test_price_bounds_rounds_to_step(catalog):
    assert selectors.price_bounds() == (2_000_000, 5_000_000)


@pytest.mark.parametrize(
    "filters, expected",
    [
        ({"q": "عود"}, ["عود شب"]),
        ({"scents": ["floral"]}, ["گل سرخ"]),
        ({"max_price": 3_000_000}, ["گل سرخ"]),
        ({"min_price": 3_000_000}, ["عود شب"]),
        ({"sort": "price"}, ["گل سرخ", "عود شب"]),
        ({"sort": "-price"}, ["عود شب", "گل سرخ"]),
        ({"sort": "rating"}, ["عود شب", "گل سرخ"]),
    ],
)
def test_filter_products(catalog, filters, expected):
    result = names(selectors.filter_products(selectors.ProductFilters(**filters)))
    assert result == expected if "sort" in filters else sorted(result) == sorted(expected)


def test_filter_by_collection(catalog):
    assert names(selectors.filter_products(selectors.ProductFilters(collection=catalog["col"]))) == ["گل سرخ"]


def test_best_sellers_and_related(catalog):
    assert names(selectors.best_sellers(limit=1)) == ["عود شب"]
    assert catalog["hidden"] not in selectors.related_products(catalog["rose"])


def test_submit_review_is_always_pending(catalog):
    form = ReviewForm({"name": "سارا", "rating": 5, "text": "خیلی خوب"})
    assert form.is_valid()
    review = submit_review(catalog["oud"], form)
    assert review.is_approved is False and review.user is None
