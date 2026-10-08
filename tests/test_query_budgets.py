"""بودجه کوئری صفحه‌های اصلی و تشخیص N+1.

اگر تغییری تعداد کوئری را از بودجه بالاتر ببرد یا تعداد کوئری با زیاد شدن محصولات رشد کند، این تست شکست
می‌خورد. بودجه‌ها اندکی بالاتر از مقدار فعلی‌اند (برای تغییرات کوچک)، نه چند برابر.
"""

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.blog.models import Post
from apps.catalog.models import Collection
from apps.catalog.tests.factories import ProductFactory, ReviewFactory, VariantFactory

pytestmark = pytest.mark.django_db

BUDGETS = {
    "/": 16,
    "/shop/": 14,
    "/shop/?scent=woody&sort=price": 14,
    "/shop/?q=عطر خنک زیر ۴ میلیون": 14,
    "/shop/?q=عطر خنک زیر سه تومن": 15,  # بدون نتیجه دقیق: کنار گذاشتن شرط قیمت
    "/search/suggest/?q=زنانه شیرین برای شب": 10,
    "/product/mystic-oud/": 17,
    "/collections/": 8,
    "/collections/oud/": 15,
    "/blog/": 11,
    "/cart/": 10,
    "/sitemap.xml": 6,
    "/robots.txt": 6,
}


def count(client, url):
    client.get(url)  # گرم کردن cache توکن‌های پوسته و …
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)
    assert response.status_code == 200, url
    return len(queries)


@pytest.fixture
def seeded(client, store):
    call_command("seed_demo", verbosity=0)
    client.post("/cart/add/", {"variant": VariantFactory(product__name="سبد").pk})
    return client


@pytest.mark.parametrize("url,budget", BUDGETS.items())
def test_query_budget(seeded, url, budget):
    used = count(seeded, url)
    assert used <= budget, f"{url}: {used} کوئری (بودجه {budget})"


def test_post_detail_budget(seeded):
    assert count(seeded, Post.objects.first().get_absolute_url()) <= 9


@pytest.mark.parametrize("url", ["/", "/shop/", "/collections/oud/", "/blog/", "/product/mystic-oud/"])
def test_no_n_plus_one_when_catalog_grows(seeded, store, url):
    before = count(seeded, url)
    oud = Collection.objects.get(store=store, slug="oud")
    for _ in range(12):
        product = ProductFactory(collection=oud, is_featured=True)
        VariantFactory(product=product)
        VariantFactory(product=product, size_ml=100)
        ReviewFactory(product=product)
    post = Post.objects.first()
    for i in range(6):
        Post.objects.create(title=f"مقاله {i}", slug=f"extra-{i}", category=post.category, excerpt="x", body="x",
                            cover=post.cover.name)
    assert count(seeded, url) == before, f"{url}: تعداد کوئری با تعداد محصولات رشد کرد"


def test_discovery_pages_budget_and_no_n_plus_one(seeded, store):
    from apps.catalog.models import Product

    for slug in ("mystic-oud", "royal-saffron", "velvet-oud", "amber-night"):
        seeded.post(f"/compare/{Product.objects.get(store=store, slug=slug).pk}/toggle/")
    seeded.get("/product/mystic-oud/")  # سابقه بازدید ← بخش «پیشنهاد برای شما» فعال
    budgets = {"/compare/": 11, "/finder/": 9, "/": 18}
    used = {url: count(seeded, url) for url in budgets}
    assert all(used[u] <= b for u, b in budgets.items()), used
    for _ in range(12):
        product = ProductFactory()
        VariantFactory(product=product)
    assert {url: count(seeded, url) for url in budgets} == used, "کوئری با تعداد محصولات رشد کرد"
