import pytest
from django.urls import reverse

from apps.catalog import selectors
from apps.catalog.profile import Gender, Occasion, Season
from apps.catalog.services import set_product_notes
from apps.catalog.smart_search import Vocab, parse, tokenize

from .factories import BrandFactory, ProductFactory, ScentFactory, VariantFactory

VOCAB = Vocab(
    families=[(1, "fresh", "خنک و تازه"), (2, "floral", "گُلی"), (3, "oriental", "شرقی")],
    notes=[(10, "vanilla", "وانیل"), (11, "oud", "عود"), (12, "leather", "چرم"), (13, "saffron", "زعفران"),
           (14, "amber", "کهربا")],
    brands=[(20, "royal", "رویال عود")],
    categories=[],
    tags=[],
    product_names=["عود رازالود", "شب کهربایی", "رویال عود"],
    price_range=(3_000_000, 9_000_000),
)


def summary(text):
    return [(c.kind, c.value, c.negated) for c in parse(text, VOCAB).criteria]


@pytest.mark.parametrize("text, expected", [
    ("عطر خنک زیر سه تومن", [("feel", "fresh", False), ("price", (None, 3_000_000), False)]),
    ("زیر ۳ میلیون", [("price", (None, 3_000_000), False)]),
    ("کمتر از 2.5 میلیون تومان", [("price", (None, 2_500_000), False)]),
    ("زیر ۳٫۵", [("price", (None, 3_500_000), False)]),  # بدون واحد ← از روی بازه قیمت فروشگاه
    ("زیر 3,500,000 تومان", [("price", (None, 3_500_000), False)]),
    ("بین ۴ تا ۶ میلیون", [("price", (4_000_000, 6_000_000), False)]),
    ("بین دو و نیم و سه و نیم میلیون", [("price", (2_500_000, 3_500_000), False)]),
    ("از ۵ میلیون به بالا", [("price", (5_000_000, None), False)]),
    ("بالای پنج تومن", [("price", (5_000_000, None), False)]),
    ("حدود ۴ میلیون", [("price", (3_200_000, 4_800_000), False)]),
    ("سه میلیون و پانصد هزار تومان به پایین", [("price", (None, 3_500_000), False)]),
    ("۵۰۰ هزار تومنی", [("price", (400_000, 600_000), False)]),
    ("مردونه ماندگار برای زمستون",
     [("gender", Gender.MEN, False), ("longevity", 4, False), ("season", Season.WINTER, False)]),
    ("زنانه شیرین برای شب", [("gender", Gender.WOMEN, False), ("feel", "sweet", False),
                              ("occasion", Occasion.EVENING, False)]),
    ("عطر گرم بدون عود و چرم", [("feel", "warm", False), ("note", 11, True), ("note", 12, True)]),
    ("نه شیرین", [("feel", "sweet", True)]),
    ("عطر وانیلی", [("note", 10, False)]),
    ("کهربایی", [("note", 14, False)]),
    ("زعفرون", [("note", 13, False)]),  # محاوره
    ("زعفرن", [("note", 13, False)]),  # اشتباه تایپی
    ("رویال عود", [("brand", 20, False)]),  # بلندترین تطبیق: برند، نه نت «عود»
    ("۱۰۰ میل زیر ۶ میلیون", [("size", 100, False), ("price", (None, 6_000_000), False)]),
    ("100ml", [("size", 100, False)]),
    ("تابستونی اداری ارزون", [("season", Season.SUMMER, False), ("occasion", Occasion.OFFICE, False),
                              ("sort", "price", False)]),
    ("اکستریت پرپخش", [("concentration", "extrait", False), ("sillage", "strong", False)]),
    ("باکس هدیه", [("gift_box", True, False)]),
    ("گلی", [("family", 2, False)]),  # خانواده خود فروشگاه بر حس عمومی مقدم است
])
def test_parse(text, expected):
    assert summary(text) == expected


def test_unknown_words_become_text_and_chip_removal():
    parsed = parse("عطر خنک بلابلا زیر سه تومن", VOCAB)
    assert parsed.text == "بلابلا"
    price = parsed.of("price")[0]
    assert parsed.without(price) == "عطر خنک بلابلا"
    assert price.label == "قیمت تا ۳ میلیون تومان"


def test_tokenize_splits_numbers_and_keeps_raw():
    raw, norm = tokenize("زیر۳میلیون، عطرِ خنك!")
    assert norm == ["زیر", "3", "میلیون", "عطر", "خنک"]
    assert len(raw) == len(norm)


def test_needs_filters():
    assert not parse("خنک", VOCAB).needs_filters  # یک واژه: جستجوی متنی کافی است
    assert parse("خنک زیر ۳ میلیون", VOCAB).needs_filters
    assert parse("بدون عود", VOCAB).needs_filters


# ---------- روی پایگاه داده ----------

@pytest.fixture
def shop(store):
    fresh = ScentFactory(slug="fresh", name="خنک و تازه")
    oriental = ScentFactory(slug="oriental", name="شرقی")
    floral = ScentFactory(slug="floral", name="گلی")
    brand = BrandFactory(slug="mystic", name="میستیک اورا")

    def make(name, scent, prices, **profile):
        p = ProductFactory(name=name, scent=scent, brand=brand, **profile)
        for size, price in zip((50, 100), prices, strict=False):
            VariantFactory(product=p, size_ml=size, price=price)
        return p

    products = {
        "aqua": make("آکوا", fresh, (2_800_000, 4_200_000), gender="men", seasons=["summer"], occasions=["daily"],
                     longevity=3, sillage=3),
        "cobalt": make("کبالت", fresh, (3_400_000, 5_000_000), gender="men", seasons=["summer", "spring"],
                       occasions=["office"], longevity=3, sillage=4),
        "breeze": make("نسیم", fresh, (2_500_000,), gender="women", seasons=["spring"], occasions=["daily"]),
        "amber": make("شب کهربایی", oriental, (4_200_000, 6_700_000), gender="women", seasons=["winter"],
                      occasions=["evening"], longevity=5, sillage=4),
        "rose": make("رز", floral, (3_200_000,), gender="women", seasons=["spring"], occasions=["romantic"]),
        "noprofile": make("بی‌نشان", oriental, (3_000_000,)),
    }
    set_product_notes(products["amber"], top=["زعفران"], base=["وانیل", "عود"])
    set_product_notes(products["rose"], heart=["رز"], base=["وانیل"])
    set_product_notes(products["aqua"], top=["لیمو"])
    return {**products, "store": store}


def find(shop, q, **filters):
    result = selectors.search_shop(shop["store"], selectors.ProductFilters(q=q, **filters))
    return [p.name for p in result.products], result


@pytest.mark.django_db
def test_fresh_under_three_million(shop):
    names, result = find(shop, "عطر خنک زیر سه تومن")
    assert set(names) == {"آکوا", "نسیم"}  # کبالت ۳٫۴ میلیون است؛ آکوا با حجم ۵۰ زیر ۳ میلیون
    assert result.exact


@pytest.mark.django_db
def test_relaxes_price_when_nothing_matches(shop):
    names, result = find(shop, "عطر خنک زیر یک میلیون")
    assert not result.exact and [c.kind for c in result.relaxed] == ["price"]
    assert names == ["نسیم", "آکوا", "کبالت"]  # بدون شرط قیمت: ارزان‌ترین اول


@pytest.mark.django_db
def test_gender_includes_unisex_and_unknown_after_exact(shop):
    names, _ = find(shop, "زنانه شیرین")
    assert names == ["شب کهربایی", "رز"] or set(names) == {"شب کهربایی", "رز"}
    names, _ = find(shop, "زنانه شرقی")
    assert names[0] == "شب کهربایی" and names[-1] == "بی‌نشان"  # بدون مشخصات: آخر


@pytest.mark.django_db
def test_season_occasion_longevity(shop):
    # محصول بدون مشخصات رایحه حذف نمی‌شود ولی بعد از تطبیق‌های قطعی می‌آید
    assert find(shop, "تابستونی برای محیط کار")[0] == ["کبالت", "بی‌نشان"]
    assert find(shop, "عطر خیلی ماندگار برای شب")[0] == ["شب کهربایی", "بی‌نشان"]


@pytest.mark.django_db
def test_note_exclusion(shop):
    names, _ = find(shop, "زنانه بدون عود")
    assert "شب کهربایی" not in names and {"نسیم", "رز"} <= set(names)


@pytest.mark.django_db
def test_size_and_price_on_same_variant(shop):
    # «۱۰۰ میل زیر ۵ میلیون»: حجم ۱۰۰ آکوا ۴٫۲ میلیون است؛ حجم ۱۰۰ کبالت دقیقاً ۵ میلیون
    assert set(find(shop, "۱۰۰ میل زیر ۵ میلیون")[0]) == {"آکوا", "کبالت"}
    assert find(shop, "۱۰۰ میل زیر ۴ میلیون")[1].relaxed


@pytest.mark.django_db
def test_sort_from_query_and_explicit_sort_wins(shop):
    assert find(shop, "خنک ارزان")[0] == ["نسیم", "آکوا", "کبالت"]
    assert find(shop, "خنک ارزان", sort="-price")[0] == ["کبالت", "آکوا", "نسیم"]


@pytest.mark.django_db
def test_product_name_query_is_plain_text(shop):
    names, result = find(shop, "شب کهربایی")  # «شب» موقعیت و «کهربا» نت است، ولی این نام محصول است
    assert names == ["شب کهربایی"] and result.parsed is None


@pytest.mark.django_db
def test_unknown_words_are_ignored_and_reported(shop):
    names, result = find(shop, "زنانه خنک فلان‌بهمان")
    assert names == ["نسیم"]
    assert result.parsed.ignored == ["«فلان‌بهمان»"]


@pytest.mark.django_db
def test_shop_page_shows_chips_and_relaxed_notice(client, shop):
    resp = client.get(reverse("catalog:shop"), {"q": "عطر خنک زیر یک میلیون"})
    body = resp.content.decode()
    assert "برداشت ما از جستجوی شما" in body and "خنک و تازه" in body
    assert "نزدیک‌ترین گزینه‌ها" in body
    # ✕ هر برچسب همان عبارت بدون کلمات آن شرط است
    assert "q=%D8%B9%D8%B7%D8%B1+%D8%AE%D9%86%DA%A9" in body  # q=عطر خنک


@pytest.mark.django_db
def test_suggest_endpoint(client, shop):
    resp = client.get(reverse("catalog:search_suggest"), {"q": "زنانه شیرین"}, HTTP_HX_REQUEST="true")
    body = resp.content.decode()
    assert "شب کهربایی" in body and "شیرین" in body and "آکوا" not in body
    empty = client.get(reverse("catalog:search_suggest"), {"q": ""}).content.decode()
    assert "عطر خنک زیر ۴ میلیون" in empty  # نمونه‌ها


@pytest.mark.django_db
def test_vocab_cache_invalidated_on_new_note(shop, django_capture_on_commit_callbacks):
    assert find(shop, "زنانه پچولی")[1].parsed.ignored == ["«پچولی»"]  # هنوز در هیچ عطری نیست
    with django_capture_on_commit_callbacks(execute=True):
        set_product_notes(shop["rose"], base=["پچولی"])
    names, result = find(shop, "زنانه پچولی")
    assert names == ["رز"] and result.parsed.of("note")
