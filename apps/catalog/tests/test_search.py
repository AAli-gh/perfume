import pytest

from apps.catalog import selectors
from apps.catalog.models import Attribute, AttributeValue, Category, Product, Tag
from apps.catalog.search import normalize
from apps.catalog.services import set_product_notes

from .factories import BrandFactory, ProductFactory, VariantFactory

pytestmark = pytest.mark.django_db


def names(store, **filters):
    return [p.name for p in selectors.filter_products(store, selectors.ProductFilters(**filters))]


@pytest.mark.parametrize("raw, expected", [
    ("مي‌خك", "میخک"),                # ي/ك عربی + نیم‌فاصله
    ("زَعفَران", "زعفران"),            # اعراب
    ("عـــود", "عود"),                 # کشیده
    ("آکوا", "اکوا"),
    ("۱۰۰ ميل", "100 میل"),            # ارقام فارسی
    ("  Royal   OUD ", "royal oud"),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.fixture
def catalog(store):
    royal = BrandFactory(name="رویال عود", slug="royal")
    saffron = ProductFactory(name="زعفران شاهانه", brand=royal)
    rose = ProductFactory(name="شکوفه آرامش", short_description="رایحه‌ای گلی و سبک")
    oud = ProductFactory(name="عود رازآلود")
    for p in (saffron, rose, oud):
        VariantFactory(product=p)
    set_product_notes(saffron, top=["زعفران", "هل"], base=["عود"])
    set_product_notes(oud, top=["برگاموت"], heart=["قلب عود"], base=["مشک"])
    set_product_notes(rose, top=["گلابی"], heart=["یاس"], base=["مشک سفید"])
    return {"saffron": saffron, "rose": rose, "oud": oud, "store": store}


def test_search_by_name_brand_and_notes(catalog):
    s = catalog["store"]
    assert names(s, q="شکوفه") == ["شکوفه آرامش"]
    assert set(names(s, q="رویال")) == {"زعفران شاهانه"}              # برند
    assert set(names(s, q="برگاموت")) == {"عود رازآلود"}               # نت
    assert set(names(s, q="مشک")) == {"عود رازآلود", "شکوفه آرامش"}


def test_search_prefix_and_arabic_letters(catalog):
    s = catalog["store"]
    assert names(s, q="زعف") == ["زعفران شاهانه"]          # بخشی از کلمه
    assert names(s, q="شكوفه") == ["شکوفه آرامش"]          # ک عربی
    assert names(s, q="گل") == ["شکوفه آرامش"]             # کلمه درون توضیحات
    assert names(s, q="ناموجود") == []


def test_all_words_required(catalog):
    assert names(catalog["store"], q="مشک برگاموت") == ["عود رازآلود"]


def test_name_match_ranks_first(catalog):
    # «عود» در نام «عود رازآلود» و در نت پایه «زعفران شاهانه» آمده؛ نام وزن بیشتری دارد
    assert names(catalog["store"], q="عود")[0] == "عود رازآلود"


def test_explicit_sort_overrides_rank(catalog):
    VariantFactory(product=catalog["oud"], size_ml=100, price=9_000_000)
    result = names(catalog["store"], q="عود", sort="-price")
    assert set(result) == {"عود رازآلود", "زعفران شاهانه"}


def test_index_updates_when_notes_change(catalog):
    s = catalog["store"]
    assert names(s, q="وانیل") == []
    set_product_notes(catalog["rose"], base=["وانیل"])
    assert names(s, q="وانیل") == ["شکوفه آرامش"]


def test_index_updates_when_product_renamed(catalog):
    p = catalog["rose"]
    p.name = "نسیم بهاری"
    p.save()
    assert names(catalog["store"], q="نسیم") == ["نسیم بهاری"]


def test_brand_rename_reindexes_in_background(catalog, django_capture_on_commit_callbacks):
    brand = catalog["saffron"].brand
    brand.name = "خاندان مجد"
    with django_capture_on_commit_callbacks(execute=True):
        brand.save()
    assert names(catalog["store"], q="خاندان") == ["زعفران شاهانه"]


def test_filter_by_category_includes_descendants(catalog):
    s = catalog["store"]
    perfume = Category.objects.create(name="عطر", slug="perfume")
    women = Category.objects.create(name="زنانه", slug="women", parent=perfume)
    catalog["rose"].categories.add(women)
    catalog["oud"].categories.add(perfume)
    assert set(names(s, categories=["perfume"])) == {"شکوفه آرامش", "عود رازآلود"}
    assert names(s, categories=["women"]) == ["شکوفه آرامش"]
    assert names(s, q="زنانه") == ["شکوفه آرامش"]  # دسته وارد ایندکس جستجو هم می‌شود


def test_filter_by_tag_and_note(catalog):
    s = catalog["store"]
    gift = Tag.objects.create(name="هدیه", slug="gift")
    catalog["oud"].tags.add(gift)
    assert names(s, tags=["gift"]) == ["عود رازآلود"]
    musk = catalog["oud"].notes.get(note__name="مشک").note
    assert names(s, notes=[musk.slug]) == ["عود رازآلود"]


def test_attribute_filters_or_within_and_across(catalog):
    s = catalog["store"]
    conc = Attribute.objects.create(name="غلظت", slug="concentration")
    gender = Attribute.objects.create(name="جنسیت", slug="gender")
    edp = AttributeValue.objects.create(attribute=conc, value="ادوپرفیوم", slug="edp")
    edt = AttributeValue.objects.create(attribute=conc, value="ادوتویلت", slug="edt")
    unisex = AttributeValue.objects.create(attribute=gender, value="یونیسکس", slug="unisex")
    catalog["oud"].attribute_values.add(edp, unisex)
    catalog["rose"].attribute_values.add(edt)
    catalog["saffron"].attribute_values.add(edp)
    assert set(names(s, attributes=["edp", "edt"])) == {"عود رازآلود", "شکوفه آرامش", "زعفران شاهانه"}
    assert names(s, attributes=["edp", "unisex"]) == ["عود رازآلود"]


def test_category_cannot_be_its_own_ancestor(catalog):
    from django.core.exceptions import ValidationError

    a = Category.objects.create(name="الف", slug="a")
    b = Category.objects.create(name="ب", slug="b", parent=a)
    a.parent = b
    with pytest.raises(ValidationError):
        a.full_clean()
    b.refresh_from_db()
    assert str(b) == "الف › ب"


def test_set_product_notes_preserves_order_and_reuses_notes(catalog):
    set_product_notes(catalog["rose"], top=["هل", "برگاموت"])
    assert catalog["rose"].notes_by_layer()["top"] == ["هل", "برگاموت"]
    from apps.catalog.models import FragranceNote

    assert FragranceNote.objects.filter(name="برگاموت").count() == 1  # نت تکراری ساخته نمی‌شود


def test_products_are_indexed_on_create(store):
    p = ProductFactory(name="نام تازه")
    p.refresh_from_db()
    assert "نام تازه" in p.search_document and p.search_vector
    assert Product.objects.filter(search_vector__isnull=True).count() == 0
