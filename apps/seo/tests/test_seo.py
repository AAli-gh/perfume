import json
import re

import pytest
from django.urls import reverse

from apps.blog.models import Category as BlogCategory
from apps.blog.models import Post
from apps.catalog.models import Category
from apps.catalog.tests.factories import GIF, CollectionFactory, ProductFactory, ReviewFactory, VariantFactory
from apps.core.models import StoreDomain
from apps.seo.jsonld import json_dumps_safe

pytestmark = pytest.mark.django_db


def head(client, url, **kw):
    r = client.get(url, **kw)
    body = r.content.decode()
    return r, body.split("</head>")[0]


def meta(html, name, attr="name"):
    m = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', html)
    return m.group(1) if m else None


def title(html):
    return re.search(r"<title>(.*?)</title>", html, re.S).group(1)


def canonical(html):
    return re.search(r'<link rel="canonical" href="([^"]*)"', html).group(1)


def jsonld(html):
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def by_type(blocks, kind):
    return next(b for b in blocks if b["@type"] == kind)


@pytest.fixture
def product(store):
    p = ProductFactory(name="عود شب", slug="night-oud", short_description="عطری گرم با نت عود و عنبر.")
    VariantFactory(product=p, size_ml=50, price=2_000_000, stock=3)
    VariantFactory(product=p, size_ml=100, price=3_500_000, stock=0)
    return p


@pytest.fixture
def post(store):
    cat = BlogCategory.objects.create(name="آموزش", slug="tips")
    return Post.objects.create(title="راهنمای انتخاب عطر", slug="guide", category=cat, excerpt="چطور عطر مناسب بخریم؟",
                               body="## مقدمه\n\nمتن", cover="blog/x.jpg")


# ---------- عنوان‌ها و توضیح‌ها (همان مقادیر قبلی) ----------

@pytest.mark.parametrize("url,expected", [
    ("/shop/", "فروشگاه | عطر مجد"),
    ("/collections/", "کالکشن‌ها | عطر مجد"),
    ("/blog/", "مجله | عطر مجد"),
    ("/about/", "درباره ما | عطر مجد"),
    ("/contact/", "تماس با ما | عطر مجد"),
    ("/cart/", "سبد خرید | عطر مجد"),
    ("/account/login/", "ورود | عطر مجد"),
    ("/account/register/", "ثبت‌نام | عطر مجد"),
])
def test_page_titles_unchanged(client, store, url, expected):
    _, html = head(client, url)
    assert title(html) == expected
    assert meta(html, "description") == "عطر مجد؛ فروشگاه آنلاین عطرهای لوکس، عود و رایحه‌های شرقی."


def test_home_meta_and_structured_data(client, store):
    store.config.tagline = "خانه عطرهای لوکس"
    store.config.instagram_url = "https://instagram.com/majd"
    store.config.phone_link = "+982112345678"
    store.config.save()
    r, html = head(client, "/")
    assert title(html) == "عطر مجد | خانه عطرهای لوکس"
    assert canonical(html) == "http://testserver/"
    assert meta(html, "robots").startswith("index")
    assert meta(html, "og:url", "property") == "http://testserver/"
    blocks = jsonld(html)
    site = by_type(blocks, "WebSite")
    assert site["potentialAction"]["target"]["urlTemplate"] == "http://testserver/shop/?q={search_term_string}"
    org = by_type(blocks, "OnlineStore")
    assert org["sameAs"] == ["https://instagram.com/majd"] and org["telephone"] == "+982112345678"


def test_site_verification_only_on_home(client, store):
    store.config.google_site_verification = "abc_123"
    store.config.bing_site_verification = "BING1"
    store.config.save()
    _, html = head(client, "/")
    assert meta(html, "google-site-verification") == "abc_123" and meta(html, "msvalidate.01") == "BING1"
    _, html = head(client, "/shop/")
    assert meta(html, "google-site-verification") is None


def test_product_meta_and_offers(client, product):
    ReviewFactory(product=product, rating=5)
    ReviewFactory(product=product, rating=4)
    ReviewFactory(product=product, rating=1, is_approved=False)  # تأییدنشده حساب نمی‌شود
    _, html = head(client, product.get_absolute_url())
    assert title(html) == "عود شب | عطر مجد"
    assert meta(html, "description") == "عطری گرم با نت عود و عنبر."
    assert meta(html, "og:type", "property") == "product"
    assert meta(html, "og:image", "property").startswith("http://testserver/media/")
    data = by_type(jsonld(html), "Product")
    assert data["brand"]["name"] == product.brand.name and data["sku"] == "night-oud"
    offers = data["offers"]
    assert offers["@type"] == "AggregateOffer" and offers["priceCurrency"] == "IRR"
    assert (offers["lowPrice"], offers["highPrice"]) == (20_000_000, 35_000_000)  # تومان × ۱۰ = ریال
    assert offers["availability"] == "https://schema.org/InStock"
    assert data["aggregateRating"] == {"@type": "AggregateRating", "ratingValue": 4.5, "reviewCount": 2,
                                       "bestRating": 5, "worstRating": 1}
    crumbs = by_type(jsonld(html), "BreadcrumbList")["itemListElement"]
    assert [c["name"] for c in crumbs] == ["خانه", "عطرها", "عود شب"]


def test_out_of_stock_and_no_rating(client, store):
    p = ProductFactory()
    VariantFactory(product=p, stock=0)
    data = by_type(jsonld(head(client, p.get_absolute_url())[1]), "Product")
    assert data["offers"]["@type"] == "Offer" and data["offers"]["availability"].endswith("OutOfStock")
    assert "aggregateRating" not in data


def test_currency_settings_used(client, product, store):
    store.config.currency_code, store.config.currency_factor = "USD", 1
    store.config.save()
    offers = by_type(jsonld(head(client, product.get_absolute_url())[1]), "Product")["offers"]
    assert offers["priceCurrency"] == "USD" and offers["lowPrice"] == 2_000_000


def test_custom_meta_fields_override(client, product):
    product.meta_title = "خرید عطر عود شب اصل"
    product.meta_description = "توضیح اختصاصی برای گوگل"
    product.save()
    _, html = head(client, product.get_absolute_url())
    assert title(html) == "خرید عطر عود شب اصل" and meta(html, "description") == "توضیح اختصاصی برای گوگل"


def test_description_is_clean_and_truncated(client, store):
    p = ProductFactory(short_description="  <b>متن</b>\nبا   فاصله " + "خیلی " * 60)
    VariantFactory(product=p)
    desc = meta(head(client, p.get_absolute_url())[1], "description")
    assert len(desc) <= 160 and desc.endswith("…") and "<b>" not in desc and "  " not in desc


def test_post_meta_and_article(client, post):
    _, html = head(client, post.get_absolute_url())
    assert title(html) == "راهنمای انتخاب عطر | مجله عطر مجد"
    assert meta(html, "og:type", "property") == "article"
    article = by_type(jsonld(html), "BlogPosting")
    assert article["headline"] == "راهنمای انتخاب عطر" and article["articleSection"] == "آموزش"
    assert article["datePublished"] and article["dateModified"]
    assert [c["name"] for c in by_type(jsonld(html), "BreadcrumbList")["itemListElement"]] == ["خانه", "مجله", post.title]


def test_jsonld_cannot_break_out_of_script(client, store):
    p = ProductFactory(name='</script><script>alert(1)</script>', short_description="x")
    VariantFactory(product=p)
    _, html = head(client, p.get_absolute_url())
    assert "<script>alert(1)" not in html
    assert by_type(jsonld(html), "Product")["name"] == '</script><script>alert(1)</script>'
    assert "<" not in json_dumps_safe({"a": "<>&"})


# ---------- robots / canonical ----------

def test_noindex_item(client, product):
    product.noindex = True
    product.save()
    _, html = head(client, product.get_absolute_url())
    assert meta(html, "robots") == "noindex, follow" and not jsonld(html)


@pytest.mark.parametrize("url", ["/shop/?brand=x", "/shop/?q=عود", "/blog/?cat=tips", "/shop/?sort=price&page=2"])
def test_filtered_pages_noindex_with_clean_canonical(client, store, url):
    _, html = head(client, url)
    assert meta(html, "robots") == "noindex, follow"
    assert "?" not in canonical(html)


def test_pagination_canonical_keeps_page(client, store):
    for _ in range(10):
        VariantFactory()
    _, html = head(client, "/shop/?page=2")
    assert canonical(html) == "http://testserver/shop/?page=2" and meta(html, "robots").startswith("index")
    _, html = head(client, "/shop/?page=1")
    assert canonical(html) == "http://testserver/shop/"


@pytest.mark.parametrize("url", ["/cart/", "/account/login/", "/orders/checkout/", "/account/wishlist/"])
def test_private_pages_noindex(client, store, url):
    from apps.accounts.models import User

    client.force_login(User.objects.create_user(email="u@example.com", password="x-12345-y"))
    r, html = head(client, url)
    if r.status_code == 200:
        assert meta(html, "robots") == "noindex, follow"
    else:
        assert r.status_code in (302, 405)  # تسویه حساب فقط POST می‌پذیرد


def test_canonical_uses_primary_domain(client, store, product):
    StoreDomain.objects.create(store=store, domain="shop.example.com", is_primary=True)
    _, html = head(client, product.get_absolute_url())
    assert canonical(html) == "http://shop.example.com/product/night-oud/"
    assert by_type(jsonld(html), "Product")["url"] == "http://shop.example.com/product/night-oud/"


def test_staging_noindex_everywhere(client, store, settings):
    settings.SEO_NOINDEX = True
    _, html = head(client, "/")
    assert meta(html, "robots") == "noindex, follow" and not jsonld(html)
    assert "Disallow: /\n" in client.get("/robots.txt").content.decode()


def test_preview_mode_noindex(client, store):
    from apps.accounts.models import User

    client.force_login(User.objects.create_user(email="s@example.com", password="x-12345-y", is_staff=True,
                                                is_superuser=True))
    client.get(reverse("builder:preview"))
    assert meta(head(client, "/")[1], "robots") == "noindex, follow"


# ---------- robots.txt و sitemap ----------

def test_robots_txt(client, store):
    r = client.get("/robots.txt")
    text = r.content.decode()
    assert r["Content-Type"].startswith("text/plain")
    for path in ["/cart/", "/account/", "/orders/"]:
        assert f"Disallow: {path}" in text
    assert "/admin/" not in text and "/studio/" not in text  # پنل‌ها پنهان‌اند (برای غیرکارکنان ۴۰۴)
    assert "Sitemap: http://testserver/sitemap.xml" in text
    assert "Disallow: /\n" not in text and "Disallow: /shop" not in text


def test_sitemap_contents(client, store, product, post):
    hidden = ProductFactory(slug="hidden", noindex=True)
    inactive = ProductFactory(slug="inactive", is_active=False)
    draft = Post.objects.create(title="پیش‌نویس", slug="draft", category=post.category, excerpt="x", body="x",
                                cover="blog/x.jpg", is_published=False)
    coll = CollectionFactory(slug="summer")
    Category.objects.create(name="زنانه", slug="women")
    xml = client.get("/sitemap.xml").content.decode()
    for loc in ["http://testserver/", "http://testserver/shop/", "http://testserver/product/night-oud/",
                f"http://testserver{post.get_absolute_url()}", "http://testserver/collections/summer/",
                "http://testserver/category/women/"]:
        assert f"<loc>{loc}</loc>" in xml, loc
    for path in [hidden.get_absolute_url(), inactive.get_absolute_url(), draft.get_absolute_url()]:
        assert path not in xml
    assert "<lastmod>" in xml and coll.slug in xml


def test_sitemap_is_per_store(client, store, other_store):
    from apps.core.stores import use_store

    with use_store(other_store):
        other = ProductFactory(store=other_store, slug="other-only", brand__store=other_store,
                               scent__store=other_store)
    mine = ProductFactory(slug="mine-only")
    other_store.domains.update(is_primary=True)
    xml = client.get("/sitemap.xml", HTTP_HOST="second.test").content.decode()
    assert "http://second.test/product/other-only/" in xml and mine.slug not in xml
    xml = client.get("/sitemap.xml").content.decode()
    assert other.slug not in xml and "mine-only" in xml


# ---------- صفحه‌های کالکشن و دسته ----------

def test_collection_landing_page(client, store):
    coll = CollectionFactory(name="کالکشن تابستان", slug="summer", tagline="رایحه‌های خنک")
    inside = ProductFactory(collection=coll, name="عطر داخل")
    outside = ProductFactory(name="عطر بیرون")
    VariantFactory(product=inside)
    VariantFactory(product=outside)
    r, html = head(client, "/collections/summer/")
    body = r.content.decode()
    assert r.status_code == 200 and title(html) == "کالکشن تابستان | عطر مجد"
    assert meta(html, "description") == "رایحه‌های خنک" and canonical(html) == "http://testserver/collections/summer/"
    assert "عطر داخل" in body and "عطر بیرون" not in body
    assert [c["name"] for c in by_type(jsonld(html), "BreadcrumbList")["itemListElement"]] == \
        ["خانه", "کالکشن‌ها", "کالکشن تابستان"]
    assert client.get("/collections/nope/").status_code == 404
    # پیوندهای قدیمی ?collection= همچنان کار می‌کنند (ولی noindex)
    r, html = head(client, "/shop/?collection=summer")
    assert "عطر بیرون" not in r.content.decode() and meta(html, "robots") == "noindex, follow"


def test_category_landing_includes_subcategories(client, store):
    women = Category.objects.create(name="زنانه", slug="women", description="عطرهای زنانه")
    edp = Category.objects.create(name="ادوپرفیوم زنانه", slug="women-edp", parent=women)
    a, b, c = ProductFactory(name="عطر الف"), ProductFactory(name="عطر ب"), ProductFactory(name="عطر ج")
    for p in (a, b, c):
        VariantFactory(product=p)
    a.categories.add(women)
    b.categories.add(edp)
    body = client.get("/category/women/").content.decode()
    assert "عطر الف" in body and "عطر ب" in body and "عطر ج" not in body
    crumbs = by_type(jsonld(head(client, "/category/women-edp/")[1]), "BreadcrumbList")["itemListElement"]
    assert [x["name"] for x in crumbs] == ["خانه", "فروشگاه", "زنانه", "ادوپرفیوم زنانه"]
    Category.objects.filter(pk=women.pk).update(is_active=False)
    assert client.get("/category/women/").status_code == 404


def test_shop_category_param_filters(client, store):
    """رفع باگ: پیوند ?category= قبلاً نادیده گرفته می‌شد و همه محصولات را نشان می‌داد."""
    women = Category.objects.create(name="زنانه", slug="women")
    a, b = ProductFactory(name="عطر الف"), ProductFactory(name="عطر ب")
    for p in (a, b):
        VariantFactory(product=p)
    a.categories.add(women)
    body = client.get("/shop/?category=women").content.decode()
    assert "عطر الف" in body and "عطر ب" not in body
    assert "۰ محصول" in client.get("/shop/?category=nope").content.decode()


def test_landing_filter_form_keeps_scope(client, store):
    coll = CollectionFactory(slug="summer")
    VariantFactory(product=ProductFactory(collection=coll))
    body = client.get("/collections/summer/").content.decode()
    assert '<input type="hidden" name="collection" value="summer">' in body


# ---------- ۴۰۴ ----------

def test_404_page_is_themed_and_noindex(client, store):
    r, html = head(client, "/no-such-page/")
    assert r.status_code == 404
    assert meta(html, "robots") == "noindex, follow" and "صفحه پیدا نشد" in title(html)
    assert "صفحه‌ای که دنبالش بودید پیدا نشد" in r.content.decode()


def test_500_template_is_standalone():
    from django.template.loader import get_template

    html = get_template("500.html").render({})
    assert "مشکلی پیش آمد" in html and "{%" not in html


def test_product_image_gif_factory_still_works():
    assert GIF.startswith(b"GIF")
