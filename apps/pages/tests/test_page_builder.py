from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.tests.factories import GIF, ProductFactory, ReviewFactory, VariantFactory
from apps.core.models import Store
from apps.pages import sections
from apps.pages.defaults import DEFAULT_HOME_SECTIONS
from apps.pages.models import Page, PageSection
from apps.pages.services import SPACING_AFTER_HERO, SPACING_DEFAULT, build_blocks, ensure_home_page

pytestmark = pytest.mark.django_db


@pytest.fixture
def home(store):
    return Page.objects.get(store=store, is_home=True)


def html(client, **kw):
    return client.get("/", **kw).content.decode()


# ---------- چیدمان پیش‌فرض ----------

def test_default_home_matches_previous_layout(home):
    assert [s.type for s in home.sections.order_by("order")] == DEFAULT_HOME_SECTIONS
    hero = home.sections.get(type="hero").settings
    assert hero["title"] == "دنیای رایحه‌های\nماندگار عطر مجد" and hero["cta_url"] == "/shop/"


def test_new_store_gets_home_page():
    store = Store.objects.create(name="فروشگاه تازه", code="fresh2")
    assert Page.objects.get(store=store, is_home=True).sections.count() == len(DEFAULT_HOME_SECTIONS)
    assert ensure_home_page(store).pk == Page.objects.get(store=store).pk  # تکرار، صفحه دوم نمی‌سازد


def test_home_renders_all_default_sections(client, store):
    ProductFactory(); VariantFactory()
    body = html(client)
    for text in ("دنیای رایحه‌های<br>ماندگار عطر مجد", "ارسال سریع", "هنر عطرسازی", "عضویت در خبرنامه"):
        assert text in body


# ---------- مدیریت بخش‌ها ----------

def test_reorder_and_disable(client, home):
    banner = home.sections.get(type="banner")
    features = home.sections.get(type="features")
    banner.order, features.order = 5, 45
    banner.save(); features.save()
    body = html(client)
    assert body.index("هنر عطرسازی") < body.index("ارسال سریع")
    features.is_enabled = False
    features.save()
    assert "ارسال سریع" not in html(client)


def test_edit_settings_reflected_and_escaped(client, home):
    hero = home.sections.get(type="hero")
    hero.settings = {**hero.settings, "title": "سطر یک\n<script>alert(1)</script>"}
    hero.full_clean(); hero.save()
    body = html(client)
    assert "سطر یک<br>&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<script>alert(1)</script>" not in body


@pytest.mark.parametrize("section_type, bad", [
    ("hero", {"cta_url": "javascript:alert(1)"}),
    ("hero", {"title": ""}),
    ("hero", {"image_static": "../../etc/passwd.jpg"}),
    ("features", {"items": [{"icon": "not-an-icon", "title": "x", "text": "y"}]}),
    ("features", {"items": "not a list"}),
    ("best_sellers", {"limit": 0}),
    ("best_sellers", {"limit": 500}),
    ("banner", {"cta_url": "data:text/html,evil"}),
])
def test_invalid_settings_rejected(home, section_type, bad):
    section = PageSection(page=home, type=section_type, settings=bad)
    with pytest.raises(ValidationError):
        section.full_clean()


def test_unknown_type_rejected_by_validation_and_skipped_when_rendering(client, home):
    with pytest.raises(ValidationError):
        PageSection(page=home, type="nope").full_clean()
    PageSection.objects.create(page=home, type="nope", order=1)
    assert client.get("/").status_code == 200


def test_broken_section_does_not_break_page(client, home):
    with mock.patch.object(sections.get("banner"), "get_context", side_effect=RuntimeError("boom")):
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "هنر عطرسازی" not in body and "عضویت در خبرنامه" in body


def test_empty_sections_are_hidden(client, home):
    assert "از مجله عطر مجد" not in html(client)  # هیچ مقاله‌ای وجود ندارد


def test_spacing_rule(rf, home, store):
    request = rf.get("/")
    request.store = store
    blocks = build_blocks(home, request)
    assert blocks[0].section.type == "hero" and blocks[0].spacing == ""
    assert blocks[1].spacing == SPACING_AFTER_HERO
    assert all(b.spacing == SPACING_DEFAULT for b in blocks[2:])


def test_uploaded_image_overrides_theme_image(client, home):
    hero = home.sections.get(type="hero")
    hero.image = SimpleUploadedFile("hero.gif", GIF, content_type="image/gif")
    hero.save()
    body = html(client)
    assert "/media/pages/sections/hero" in body and "img/hero-shop.jpg" not in body


# ---------- انواع جدید ----------

def test_new_section_types_render(client, home, store):
    p = ProductFactory(name="عطر ویژه", is_featured=True)
    VariantFactory(product=p)
    ReviewFactory(product=p, rating=5, text="بی‌نظیر بود")
    from apps.catalog.models import Category

    Category.objects.create(name="عطر زنانه", slug="women")
    for i, (key, settings) in enumerate([
        ("featured_products", {}),
        ("testimonials", {}),
        ("categories", {}),
        ("faq", {"items": [{"question": "ارسال چقدر طول می‌کشد؟", "answer": "۲ تا ۴ روز کاری"}]}),
    ]):
        PageSection.objects.create(page=home, type=key, order=100 + i, settings=sections.get(key).clean_settings(settings))
    body = html(client)
    for text in ("محصولات ویژه", "عطر ویژه", "«بی‌نظیر بود»", "عطر زنانه", "/category/women/", "ارسال چقدر طول می‌کشد؟"):
        assert text in body


def test_every_registered_type_has_valid_defaults_and_template():
    from django.template.loader import get_template

    for section_type in sections.all_types():
        section_type.clean_settings({})
        get_template(section_type.template)


# ---------- چند فروشگاه و کارایی ----------

def test_pages_are_per_store(client, home, other_store):
    other = Page.objects.get(store=other_store, is_home=True)
    hero = other.sections.get(type="hero")
    hero.settings = {**hero.settings, "title": "فروشگاه دوم"}
    hero.save()
    assert "فروشگاه دوم" in html(client, HTTP_HOST="second.test")
    assert "فروشگاه دوم" not in html(client)


def test_best_sellers_scoped_to_store(client, other_store):
    from apps.catalog.tests.factories import BrandFactory, ScentFactory

    theirs = ProductFactory(store=other_store, name="محصول دیگری", brand=BrandFactory(store=other_store), scent=ScentFactory(store=other_store))
    VariantFactory(product=theirs)
    assert "محصول دیگری" not in html(client)


def test_home_query_count_is_bounded(client, store):
    for _ in range(6):
        VariantFactory(product=ProductFactory())
    client.get("/")
    with CaptureQueriesContext(connection) as q:
        client.get("/")
    assert len(q) <= 20, [x["sql"][:80] for x in q.captured_queries]


def test_draft_sections_not_shown(client, home):
    PageSection.objects.create(page=home, type="faq", status="draft", order=1,
                               settings={"title": "پیش‌نویس", "items": [{"question": "س", "answer": "ج"}]})
    assert "پیش‌نویس" not in html(client)


def test_admin_page_with_sections_renders(admin_client, home):
    assert admin_client.get(reverse("admin:pages_page_change", args=[home.pk])).status_code == 200
