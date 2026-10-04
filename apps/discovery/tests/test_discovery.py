import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog import recommend
from apps.catalog.models import FragranceNote, ScentFamily
from apps.catalog.services import set_product_notes
from apps.catalog.tests.factories import ProductFactory, ScentFactory, VariantFactory
from apps.discovery import finder
from apps.discovery.compare import MAX_ITEMS
from apps.orders.models import Order, OrderItem
from apps.wishlist.models import WishlistItem

pytestmark = pytest.mark.django_db
User = get_user_model()


def make(name, notes, *, scent="woody", price=1_000_000, **profile):
    family = ScentFactory(slug=scent, name={"woody": "چوبی", "floral": "گلی", "fresh": "خنک"}.get(scent, scent))
    p = ProductFactory(name=name, slug=name, scent=family, **profile)
    VariantFactory(product=p, price=price, size_ml=50)
    VariantFactory(product=p, price=price * 2, size_ml=100)
    set_product_notes(p, *notes)
    return p


@pytest.fixture
def perfumes(store):
    return {
        "oud": make("oud", (["زعفران"], ["عود", "رز"], ["عنبر", "مشک"]), gender="unisex", concentration="extrait",
                    longevity=5, sillage=5, seasons=["winter"], occasions=["evening", "formal"], price=5_000_000),
        "oud2": make("oud2", (["هل"], ["عود"], ["عنبر", "چوب صندل"]), gender="men", longevity=4, sillage=4,
                     seasons=["autumn", "winter"], occasions=["evening"], price=4_000_000),
        "rose": make("rose", (["برگاموت"], ["رز", "یاس"], ["مشک"]), scent="floral", gender="women", longevity=3,
                     sillage=2, seasons=["spring"], occasions=["daily", "romantic"], price=2_000_000),
        "fresh": make("fresh", (["لیمو", "نعناع"], ["اسطوخودوس"], ["چوب سدر"]), scent="fresh", gender="men",
                      longevity=2, sillage=3, seasons=["summer"], occasions=["daily", "office"], price=1_500_000),
    }


def _ids(products):
    return [p.slug for p in products]


# ---------- موتور شباهت ----------

def test_similarity_weights_base_notes_and_family(perfumes):
    pool = list(recommend.candidates(perfumes["oud"].store))
    oud = next(p for p in pool if p.slug == "oud")
    similar = recommend.similar_products(oud, pool=pool)
    assert _ids(similar)[:2] == ["oud2", "rose"] and "fresh" not in _ids(similar)
    assert similar[0].similarity > similar[1].similarity
    assert recommend.similarity(oud, oud) == 1.0


def test_product_page_shows_note_based_similar_products(client, perfumes):
    html = client.get(perfumes["oud"].get_absolute_url()).content.decode()
    assert "بیشترین نت مشترک" in html and 'href="/product/oud2/"' in html
    assert client.session["recently_viewed"] == [perfumes["oud"].pk]


# ---------- مقایسه ----------

def test_compare_toggle_limit_and_badge(client, perfumes, store):
    extra = [make(f"x{i}", (["لیمو"], [], [])) for i in range(2)]
    ids = [perfumes[k].pk for k in ("oud", "oud2", "rose", "fresh")]
    for pk in ids:
        assert client.post(reverse("discovery:compare_toggle", args=[pk]), HTTP_HX_REQUEST="true").status_code == 200
    response = client.post(reverse("discovery:compare_toggle", args=[extra[0].pk]), HTTP_HX_REQUEST="true")
    html = response.content.decode()
    assert f"حداکثر {MAX_ITEMS}" in html and 'id="compare-badge"' in html and "hx-swap-oob" in html
    assert client.session["compare"] == ids
    client.post(reverse("discovery:compare_toggle", args=[ids[0]]))  # بدون HTMX: حذف و redirect
    assert client.session["compare"] == ids[1:]


def test_compare_table_highlights_best_and_shared_notes(client, perfumes):
    for key in ("oud", "oud2", "rose"):
        client.post(reverse("discovery:compare_toggle", args=[perfumes[key].pk]))
    response = client.get(reverse("discovery:compare"))
    html = response.content.decode()
    assert response.status_code == 200 and response.context["shared_notes"] == []
    groups = {g.title: g for g in response.context["groups"]}
    price = next(r for r in groups["خلاصه"].rows if r.label == "قیمت")
    longevity = next(r for r in groups["شخصیت رایحه"].rows if r.label == "ماندگاری")
    assert price.best == {2} and longevity.best == {0}  # ارزان‌ترین: rose؛ ماندگارترین: oud
    assert "chip-shared" in html and "بهترین" in html and "شباهت به «oud»" in html
    assert 'name="robots" content="noindex' in html


def test_compare_only_differences_and_share_link(client, perfumes, other_store):
    for key in ("oud", "oud2"):
        client.post(reverse("discovery:compare_toggle", args=[perfumes[key].pk]))
    full = client.get(reverse("discovery:compare")).context["groups"]
    diff = client.get(reverse("discovery:compare"), {"diff": "1"}).context["groups"]
    assert sum(len(g.rows) for g in diff) < sum(len(g.rows) for g in full)
    assert all(not r.is_same for g in diff for r in g.rows)

    foreign = ProductFactory(store=other_store, slug="rose")  # همان slug در فروشگاه دیگر
    shared = client.get(reverse("discovery:compare"), {"p": "fresh,rose,unknown"})
    assert [p.pk for p in shared.context["products"]] == [perfumes["fresh"].pk, perfumes["rose"].pk]
    assert foreign.pk not in [p.pk for p in shared.context["products"]]
    assert client.session["compare"] == [perfumes["oud"].pk, perfumes["oud2"].pk]  # فهرست شخصی دست نخورد


def test_compare_ignores_other_store_and_inactive(client, perfumes, other_store):
    foreign = ProductFactory(store=other_store)
    assert client.post(reverse("discovery:compare_toggle", args=[foreign.pk])).status_code == 404
    perfumes["fresh"].is_active = False
    perfumes["fresh"].save()
    assert client.post(reverse("discovery:compare_toggle", args=[perfumes["fresh"].pk])).status_code == 404
    client.post(reverse("discovery:compare_set"), {"product": [perfumes["oud"].pk, foreign.pk, "x"]})
    assert client.session["compare"] == [perfumes["oud"].pk]
    client.post(reverse("discovery:compare_clear"))
    assert "هنوز عطری" in client.get(reverse("discovery:compare")).content.decode()


# ---------- پیشنهاد شخصی ----------

@pytest.fixture
def buyer(client, perfumes, store):
    user = User.objects.create_user(email="buyer@example.com", password="x-Strong-123")
    order = Order.objects.create(store=store, user=user, first_name="a", last_name="b", phone="09120000000",
                                 province="تهران", city="تهران", address="x", postal_code="1234567890", total=1,
                                 payment_method=Order.PaymentMethod.COD)
    OrderItem.objects.create(order=order, variant=perfumes["oud"].variants.first(), product_name="oud", size_ml=50,
                             unit_price=1, quantity=1)
    client.force_login(user)
    return user


def test_recommendations_from_purchases_exclude_bought(client, buyer, perfumes):
    html = client.get(reverse("accounts:profile")).content.decode()
    assert "پیشنهاد برای شما" in html and "نت‌های محبوب شما" in html and "عنبر" in html
    from apps.discovery.taste import recommendations_for

    request = client.get(reverse("accounts:profile")).wsgi_request
    products, taste, sources = recommendations_for(request)
    assert sources["purchases"] == 1 and _ids(products)[0] == "oud2" and "oud" not in _ids(products)
    assert any("نت‌های محبوب شما" in r for r in products[0].reasons)


def test_cancelled_and_unpaid_online_orders_do_not_count(client, buyer, perfumes):
    Order.objects.update(status=Order.Status.CANCELLED)
    from apps.discovery.taste import purchased_counts

    assert purchased_counts(buyer, perfumes["oud"].store) == {}
    Order.objects.update(status=Order.Status.PENDING, payment_method=Order.PaymentMethod.ONLINE)
    assert purchased_counts(buyer, perfumes["oud"].store) == {}


def test_wishlist_and_views_build_taste_for_new_users(client, perfumes, store):
    user = User.objects.create_user(email="fan@example.com", password="x-Strong-123")
    WishlistItem.objects.create(user=user, product=perfumes["rose"])
    client.force_login(user)
    client.get(perfumes["fresh"].get_absolute_url())
    from apps.discovery.taste import recommendations_for

    request = client.get("/").wsgi_request
    products, taste, sources = recommendations_for(request)
    assert sources == {"purchases": 0, "wishlist": 1, "views": 1}
    assert "rose" not in _ids(products) and "رز" in taste.favorite_notes()


def test_home_for_you_section_hidden_for_new_visitor_shown_after_views(client, perfumes):
    assert "پیشنهاد ویژه برای شما" not in client.get("/").content.decode()
    assert "عطر مناسب خودتان را پیدا کنید" in client.get("/").content.decode()  # بخش عطریاب
    client.get(perfumes["oud"].get_absolute_url())
    assert "پیشنهاد ویژه برای شما" in client.get("/").content.decode()


# ---------- عطریاب ----------

ANSWERS = {"gender": "women", "occasion": "evening", "season": "winter", "budget": "high", "intensity": "strong"}


def _walk(client, answers, htmx=True):
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    response = None
    for index, step in enumerate(finder.STEPS):
        value = answers.get(step.key, [])
        response = client.post(reverse("discovery:finder"), {"step": index, step.key: value}, **headers)
        assert response.status_code in (200, 302), (step.key, response.content[:300])
    return response


def test_finder_wizard_htmx_flow_and_results(client, perfumes):
    page = client.get(reverse("discovery:finder"))
    assert page.status_code == 200 and "سؤال ۱ از ۸" in page.content.decode()
    family = ScentFamily.objects.get(slug="woody").pk
    amber = FragranceNote.objects.get(name="عنبر").pk
    last = _walk(client, {**ANSWERS, "families": [family], "likes": [amber]})
    assert last["HX-Redirect"] == reverse("discovery:finder_results")
    results = client.get(reverse("discovery:finder_results"))
    products = results.context["products"]
    assert _ids(products)[0] == "oud"  # یونیسکس، شب، زمستان، قوی، چوبی، عنبر
    assert "oud2" not in _ids(products)  # مردانه ← برای «زنانه» حذف
    assert products[0].match >= 90 and any("عنبر" in r for r in products[0].reasons)


def test_finder_without_js_dislikes_and_budget(client, perfumes):
    musk = FragranceNote.objects.get(name="مشک").pk
    bands = {code: limit for code, _, limit in finder.budget_bands(list(recommend.candidates(perfumes["oud"].store)))}
    response = _walk(client, {**ANSWERS, "gender": "any", "dislikes": [musk], "budget": "low"}, htmx=False)
    assert response.status_code == 302 and response["Location"] == reverse("discovery:finder_results")
    products = client.get(reverse("discovery:finder_results")).context["products"]
    assert all(p.min_price <= bands["low"] for p in products)
    assert {"oud", "rose"}.isdisjoint(_ids(products))  # مشک در پایه ← حذف


def test_finder_validation_back_and_reset(client, perfumes):
    response = client.post(reverse("discovery:finder"), {"step": 0}, HTTP_HX_REQUEST="true")
    assert response.status_code == 422 and "field-error" in response.content.decode()
    client.post(reverse("discovery:finder"), {"step": 0, "gender": "men"})
    back = client.get(reverse("discovery:finder"), {"step": 0}, HTTP_HX_REQUEST="true").content.decode()
    assert 'value="men"' in back and "checked" in back
    assert client.get(reverse("discovery:finder_results")).status_code == 302  # پاسخ‌ها ناقص
    client.post(reverse("discovery:finder_reset"))
    assert "finder" not in client.session
    assert client.post(reverse("discovery:finder"), {"step": "x"}).status_code == 404


def test_finder_scores_unknown_profile_neutrally(store):
    p = make("plain", (["لیمو"], [], []))
    pool = [x for x in recommend.candidates(store) if x.pk == p.pk]
    match, reasons = finder.score(pool[0], ANSWERS)
    assert match is not None and 30 <= match <= 70
