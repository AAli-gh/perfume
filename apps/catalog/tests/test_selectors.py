import pytest

from apps.catalog import selectors
from apps.catalog.services import set_product_notes
from apps.reviews.forms import ReviewForm
from apps.reviews.services import submit_review

from .factories import CollectionFactory, ProductFactory, ReviewFactory, ScentFactory, VariantFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(store):
    floral = ScentFactory(slug="floral", name="گلی")
    col = CollectionFactory(slug="spring")
    rose = ProductFactory(name="گل سرخ", scent=floral, collection=col)
    oud = ProductFactory(name="عود شب")
    set_product_notes(oud, top=["برگاموت"], heart=["قلب عود"], base=["مشک"])
    hidden = ProductFactory(name="مخفی", is_active=False)
    VariantFactory(product=rose, price=2_000_000)
    VariantFactory(product=rose, size_ml=100, price=3_000_000)
    VariantFactory(product=oud, price=5_000_000)
    VariantFactory(product=hidden, price=1_000_000)
    ReviewFactory(product=oud, rating=5)
    ReviewFactory(product=rose, rating=3)
    ReviewFactory(product=rose, rating=1, is_approved=False)
    return {"rose": rose, "oud": oud, "hidden": hidden, "col": col, "store": store}


def names(qs):
    return [p.name for p in qs]


def test_listable_products_excludes_inactive_and_annotates(catalog):
    by_name = {p.name: p for p in selectors.listable_products(catalog['store'])}
    assert set(by_name) == {"گل سرخ", "عود شب"}
    assert by_name["گل سرخ"].min_price == 2_000_000
    assert by_name["گل سرخ"].review_count == 1  # نظر تأییدنشده شمرده نمی‌شود
    assert by_name["گل سرخ"].rating_avg == 3


def test_price_bounds_rounds_to_step(catalog):
    assert selectors.price_bounds(catalog['store']) == (2_000_000, 5_000_000)


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
    result = names(selectors.filter_products(catalog['store'], selectors.ProductFilters(**filters)))
    assert result == expected if "sort" in filters else sorted(result) == sorted(expected)


def test_filter_by_collection(catalog):
    assert names(selectors.filter_products(catalog['store'], selectors.ProductFilters(collection=catalog["col"]))) == ["گل سرخ"]


def test_best_sellers_and_related(catalog):
    assert names(selectors.best_sellers(catalog['store'], limit=1)) == ["عود شب"]
    assert catalog["hidden"] not in selectors.related_products(catalog["rose"])


def test_submit_review_is_always_pending(catalog):
    form = ReviewForm({"name": "سارا", "rating": 5, "text": "خیلی خوب"})
    assert form.is_valid()
    review = submit_review(catalog["oud"], form)
    assert review.is_approved is False and review.user is None


def test_counted_lists_keep_model_ordering(store):
    """کوئری‌های GROUP BY ترتیب Meta را نادیده می‌گیرند؛ ترتیب باید صریح و قطعی باشد."""
    late = CollectionFactory(order=5, slug="late")
    early = CollectionFactory(order=1, slug="early")
    early.save()  # به‌روزرسانی ترتیب فیزیکی ردیف‌ها نباید روی خروجی اثر بگذارد
    assert [c.slug for c in selectors.collections_with_counts(store)] == ["early", "late"]
    assert late.pk < early.pk
