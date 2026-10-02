import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.tests.factories import GIF
from apps.pages.models import Page, PageSection
from apps.builder.services import editable_page
from apps.pages.services import page_sections
from apps.themes import chrome
from apps.themes import tokens as T
from apps.themes.models import ThemePreset, ThemeSettings
from apps.themes.services import editable_settings

pytestmark = pytest.mark.django_db

PANELS = ["preset", "colors", "typography", "components", "branding", "header", "footer"]
def _png():
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (4, 4), "#c47a45").save(buf, "PNG")
    return buf.getvalue()


PNG = _png()


def make_user(email, *, staff=True, superuser=False, perms=()):
    user = User.objects.create_user(email=email, password="pass-1234-xyz", is_staff=staff, is_superuser=superuser)
    for perm in perms:
        app, codename = perm.split(".")
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
    return user


@pytest.fixture
def admin_client(client, store):
    client.force_login(make_user("boss@example.com", superuser=True))
    return client


@pytest.fixture
def ts(store):
    return editable_settings(store)


@pytest.fixture
def shopper(store):
    """مشتری ناشناس: فقط نسخه منتشرشده را می‌بیند."""
    from django.test import Client

    return Client()


@pytest.fixture
def home(store):
    return editable_page(Page.objects.get(store=store, is_home=True))


DRAFT = PageSection.Status.DRAFT


def drafts(page):
    return page_sections(page, DRAFT)


def ids(page):
    return list(drafts(page).values_list("pk", flat=True))


def publish(admin_client):
    r = admin_client.post(reverse("builder:publish"))
    assert r.status_code == 302


# ---------- دسترسی ----------

def test_anonymous_redirected_to_login(client, store):
    r = client.get(reverse("builder:dashboard"))
    assert r.status_code == 302 and reverse("accounts:login") in r["Location"]


def test_customer_forbidden(client, store):
    client.force_login(make_user("c@example.com", staff=False))
    assert client.get(reverse("builder:dashboard")).status_code == 403


def test_staff_without_permissions_forbidden(client, store):
    client.force_login(make_user("s@example.com"))
    assert client.get(reverse("builder:dashboard")).status_code == 403


def test_permissions_are_per_area(client, store, home):
    client.force_login(make_user("designer@example.com", perms=["themes.change_themesettings"]))
    assert client.get(reverse("builder:theme")).status_code == 200
    assert client.get(reverse("builder:page", args=[home.pk])).status_code == 403
    client.force_login(make_user("editor@example.com", perms=["pages.change_pagesection"]))
    assert client.get(reverse("builder:page", args=[home.pk])).status_code == 200
    assert client.get(reverse("builder:theme")).status_code == 403
    section = drafts(home).first()
    # بدون مجوز حذف/افزودن
    assert client.post(reverse("builder:section_delete", args=[home.pk, section.pk])).status_code == 403
    assert client.post(reverse("builder:section_add", args=[home.pk]), {"type": "faq"}).status_code == 403
    assert PageSection.objects.filter(pk=section.pk).exists()


def test_actions_require_post(admin_client, home):
    section = drafts(home).first()
    assert admin_client.get(reverse("builder:section_toggle", args=[home.pk, section.pk])).status_code == 405


def test_cannot_edit_other_store_page(admin_client, other_store):
    other_home = editable_page(Page.objects.get(store=other_store, is_home=True))
    section = drafts(other_home).first()
    assert admin_client.get(reverse("builder:page", args=[other_home.pk])).status_code == 404
    assert admin_client.post(reverse("builder:section_toggle", args=[other_home.pk, section.pk])).status_code == 404
    section.refresh_from_db()
    assert section.is_enabled


# ---------- صفحه‌ها ----------

def test_all_studio_pages_render(admin_client, home):
    for name, args in [("builder:dashboard", []), ("builder:pages", []), ("builder:page", [home.pk])]:
        assert admin_client.get(reverse(name, args=args)).status_code == 200
    for panel in PANELS:
        r = admin_client.get(reverse("builder:theme_panel", args=[panel]))
        assert r.status_code == 200, panel
    for section in drafts(home):
        assert admin_client.get(reverse("builder:section", args=[home.pk, section.pk])).status_code == 200


def test_studio_is_not_themed_by_store(admin_client, ts):
    """پالت خراب فروشگاه روی ظاهر استودیو اثر ندارد."""
    ts.overrides = {"colors": {"background": "#ffffff", "text": "#ffffff"}}
    ts.save()
    body = admin_client.get(reverse("builder:dashboard")).content.decode()
    assert f"--color-background:{T._rgb(T.DEFAULT_TOKENS['colors']['background'])}" in body.split("studio-tokens")[1][:200]


def test_move_up_and_down(admin_client, home):
    before = ids(home)
    url = reverse("builder:section_move", args=[home.pk, before[1]])
    admin_client.post(url, {"direction": "up"})
    assert ids(home) == [before[1], before[0], *before[2:]]
    admin_client.post(url, {"direction": "down"})
    assert ids(home) == before
    # اولین بخش بالاتر نمی‌رود
    admin_client.post(reverse("builder:section_move", args=[home.pk, before[0]]), {"direction": "up"})
    assert ids(home) == before


def test_drag_and_drop_reorder(admin_client, home, shopper):
    before = ids(home)
    new = list(reversed(before))
    r = admin_client.post(reverse("builder:section_reorder", args=[home.pk]), {"order": new}, HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and 'id="sections"' in r.content.decode()
    assert ids(home) == new


def test_reorder_ignores_foreign_and_garbage_ids(admin_client, home, other_store):
    before = ids(home)
    foreign = page_sections(Page.objects.get(store=other_store, is_home=True)).first().pk
    admin_client.post(reverse("builder:section_reorder", args=[home.pk]), {"order": [before[2], foreign, "x", before[2]]})
    assert ids(home) == [before[2], *[i for i in before if i != before[2]]]


def test_reordered_home_renders_in_new_order(admin_client, home, shopper):
    order = ids(home)
    hero, newsletter = order[0], order[-1]
    admin_client.post(reverse("builder:section_reorder", args=[home.pk]), {"order": [newsletter, *order[:-1]]})
    publish(admin_client)
    body = shopper.get("/").content.decode()
    assert body.index("عضویت در خبرنامه") < body.index("دنیای رایحه‌های")
    assert PageSection.objects.get(pk=hero).order > PageSection.objects.get(pk=newsletter).order


def test_toggle_hides_section(admin_client, home, shopper):
    banner = drafts(home).get(type="banner")
    admin_client.post(reverse("builder:section_toggle", args=[home.pk, banner.pk]), HTTP_HX_REQUEST="true")
    banner.refresh_from_db()
    publish(admin_client)
    assert not banner.is_enabled and "هنر عطرسازی" not in shopper.get("/").content.decode()


def test_add_edit_and_delete_section(admin_client, home, shopper):
    r = admin_client.post(reverse("builder:section_add", args=[home.pk]), {"type": "faq"})
    faq = drafts(home).last()
    assert faq.type == "faq" and r["Location"] == reverse("builder:section", args=[home.pk, faq.pk])
    url = reverse("builder:section", args=[home.pk, faq.pk])
    assert "items-rows" in admin_client.get(url).content.decode()
    r = admin_client.post(url, {
        "title": "سؤالات شما",
        "items-rows": "3",
        "items-0-question": "ارسال چند روز طول می‌کشد؟", "items-0-answer": "۲ تا ۴ روز کاری.",
        "items-1-question": "", "items-1-answer": "",  # ردیف خالی نادیده گرفته می‌شود
        "items-2-question": "<script>alert(1)</script>", "items-2-answer": "امن",
    })
    assert r.status_code == 302
    faq.refresh_from_db()
    assert len(faq.settings["items"]) == 2 and faq.settings["title"] == "سؤالات شما"
    publish(admin_client)
    body = shopper.get("/").content.decode()
    assert "ارسال چند روز طول می‌کشد؟" in body and "<script>alert(1)</script>" not in body
    admin_client.post(reverse("builder:section_delete", args=[home.pk, faq.pk]))
    assert not PageSection.objects.filter(pk=faq.pk).exists()


def test_add_unknown_type_rejected(admin_client, home):
    count = drafts(home).count()
    admin_client.post(reverse("builder:section_add", args=[home.pk]), {"type": "evil"})
    assert drafts(home).count() == count


def test_section_form_rejects_unsafe_values(admin_client, home):
    hero = drafts(home).get(type="hero")
    url = reverse("builder:section", args=[home.pk, hero.pk])
    r = admin_client.post(url, {"title": "x", "cta_url": "javascript:alert(1)", "image_static": "../../etc/passwd"})
    assert r.status_code == 200
    hero.refresh_from_db()
    assert hero.settings["cta_url"] == "/shop/"


def test_features_repeater_validates_icons(admin_client, home):
    features = drafts(home).get(type="features")
    url = reverse("builder:section", args=[home.pk, features.pk])
    r = admin_client.post(url, {"items-rows": "1", "items-0-icon": "not-an-icon", "items-0-title": "t", "items-0-text": ""})
    assert r.status_code == 200
    features.refresh_from_db()
    assert len(features.settings["items"]) == 4


def test_section_image_upload_and_clear(admin_client, home, shopper):
    hero = drafts(home).get(type="hero")
    url = reverse("builder:section", args=[home.pk, hero.pk])
    data = dict(hero.settings)
    admin_client.post(url, {**data, "image": SimpleUploadedFile("h.png", PNG, content_type="image/png")})
    hero.refresh_from_db()
    publish(admin_client)
    assert hero.image and hero.image.url in shopper.get("/").content.decode()
    admin_client.post(url, {**data, "clear_image": "on"})
    hero.refresh_from_db()
    assert not hero.image


def test_section_image_rejects_svg_and_fake_images(admin_client, home):
    hero = drafts(home).get(type="hero")
    url = reverse("builder:section", args=[home.pk, hero.pk])
    svg = SimpleUploadedFile("x.svg", b"<svg onload=alert(1)></svg>", content_type="image/svg+xml")
    fake = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
    for upload in (svg, fake):
        assert admin_client.post(url, {**hero.settings, "image": upload}).status_code == 200
    hero.refresh_from_db()
    assert not hero.image


# ---------- ظاهر ----------

def test_apply_preset_clears_overrides(admin_client, ts, shopper):
    ts.overrides = {"colors": {"primary": "#123456"}}
    ts.save()
    emerald = ThemePreset.objects.get(theme=ts.theme, code="luxury-emerald")
    admin_client.post(reverse("builder:theme_panel", args=["preset"]), {"action": "preset", "preset": emerald.pk})
    ts.refresh_from_db()
    assert ts.preset == emerald and ts.overrides == {}
    emerald_bg = T.merge(emerald.tokens)["colors"]["background"]
    publish(admin_client)
    assert f"--color-background:{T._rgb(emerald_bg)}" in shopper.get("/").content.decode()


def test_preset_from_other_theme_rejected(admin_client, ts):
    from apps.themes.models import Theme

    other = Theme.objects.create(code="other", name="دیگر")
    foreign = ThemePreset.objects.create(theme=other, code="x", name="x")
    admin_client.post(reverse("builder:theme_panel", args=["preset"]), {"action": "preset", "preset": foreign.pk})
    ts.refresh_from_db()
    assert ts.preset_id != foreign.pk


def colors_post(tokens, **changes):
    data = {f"color__{k}": v for k, v in tokens["colors"].items()}
    data.update({f"color__{k}": v for k, v in changes.items()})
    return data


def test_colors_saved_as_diff_and_rendered(admin_client, ts, shopper):
    url = reverse("builder:theme_panel", args=["colors"])
    admin_client.post(url, colors_post(T.resolve(ts), primary="#AA1122"))
    ts.refresh_from_db()
    assert ts.overrides == {"colors": {"primary": "#aa1122"}}  # فقط تفاوت با پیش‌تنظیم
    publish(admin_client)
    assert "--color-primary:170 17 34" in shopper.get("/").content.decode()
    admin_client.post(url, {"action": "reset"})
    ts.refresh_from_db()
    assert "colors" not in ts.overrides


def test_invalid_color_rejected(admin_client, ts):
    r = admin_client.post(reverse("builder:theme_panel", args=["colors"]),
                          colors_post(T.resolve(ts), primary="red;}</style><script>"))
    assert r.status_code == 200 and "#RRGGBB" in r.content.decode()
    ts.refresh_from_db()
    assert ts.overrides == {}


def test_typography_and_components(admin_client, ts, shopper):
    tokens = T.resolve(ts)
    data = {"font_display": "Lalezar", "font_body": "Vazirmatn", "typography__base_size": 17,
            "radius__sm": 2, "radius__base": 6, "radius__lg": 8, "spacing__section": 70}
    admin_client.post(reverse("builder:theme_panel", args=["typography"]), data)
    admin_client.post(reverse("builder:theme_panel", args=["components"]), {**tokens["components"], "button": "outline"})
    ts.refresh_from_db()
    assert ts.overrides == {
        "typography": {"font_display": "Lalezar", "base_size": 17}, "radius": {"base": 6},
        "components": {"button": "outline"},
    }
    publish(admin_client)
    body = shopper.get("/").content.decode()
    assert 'data-button="outline"' in body and "family=Lalezar" in body


def test_typography_rejects_unknown_font_and_out_of_range(admin_client, ts):
    data = {"font_display": "Comic Sans", "font_body": "Vazirmatn", "typography__base_size": 99,
            "radius__sm": 2, "radius__base": 4, "radius__lg": 8, "spacing__section": 70}
    assert admin_client.post(reverse("builder:theme_panel", args=["typography"]), data).status_code == 200
    ts.refresh_from_db()
    assert ts.overrides == {}


def test_logo_and_favicon_upload(admin_client, ts, shopper):
    url = reverse("builder:theme_panel", args=["branding"])
    admin_client.post(url, {
        "logo": SimpleUploadedFile("logo.png", PNG, content_type="image/png"),
        "favicon": SimpleUploadedFile("fav.png", PNG, content_type="image/png"),
        "logo_height": 48, "monogram": "م",
    })
    ts.refresh_from_db()
    assert ts.logo and ts.favicon and ts.header["logo_height"] == 48
    publish(admin_client)
    body = shopper.get("/").content.decode()
    assert ts.logo.url in body and "height:48px" in body and f'rel="icon" href="{ts.favicon.url}"' in body
    admin_client.post(url, {"clear_logo": "on", "clear_favicon": "on", "logo_height": 48, "monogram": ""})
    ts.refresh_from_db()
    assert not ts.logo and not ts.favicon


def test_branding_rejects_svg_and_large_files(admin_client, ts):
    url = reverse("builder:theme_panel", args=["branding"])
    svg = SimpleUploadedFile("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>", content_type="image/svg+xml")
    big = SimpleUploadedFile("big.png", PNG + b"\0" * (2 * 1024 * 1024 + 1), content_type="image/png")
    gif = SimpleUploadedFile("a.gif", GIF, content_type="image/gif")
    for upload, error in ((svg, "field-error"), (big, "حداکثر 2 مگابایت"), (gif, "فقط این قالب‌ها")):
        r = admin_client.post(url, {"logo": upload, "logo_height": 40, "monogram": ""})
        assert r.status_code == 200 and error in r.content.decode(), error
    ts.refresh_from_db()
    assert not ts.logo


def test_header_menu_editing(admin_client, ts, shopper):
    url = reverse("builder:theme_panel", args=["header"])
    r = admin_client.post(url, {
        "menu-rows": "3",
        "menu-0-label": "فروشگاه", "menu-0-url": "/shop/",
        "menu-1-label": "حراج", "menu-1-url": "/shop/?sort=price",
        "menu-2-label": "بد", "menu-2-url": "javascript:alert(1)",
        "show_account": "on", "sticky": "on",
    })
    assert r.status_code == 200  # پیوند ناامن ← فرم با خطا
    admin_client.post(url, {
        "menu-rows": "2",
        "menu-0-label": "فروشگاه", "menu-0-url": "/shop/",
        "menu-1-label": "حراج", "menu-1-url": "/shop/?sort=price",
        "show_account": "on",
    })
    ts.refresh_from_db()
    assert [m["label"] for m in ts.header["menu"]] == ["فروشگاه", "حراج"]
    assert ts.header["show_search"] is False and ts.header["sticky"] is False
    publish(admin_client)
    body = shopper.get("/shop/").content.decode()
    assert 'href="/shop/?sort=price"' in body and "data-search-open" not in body
    assert 'class="relative z-50' in body
    admin_client.post(url, {"action": "reset"})
    ts.refresh_from_db()
    assert not {"menu", "show_search", "sticky"} & set(ts.header)


def test_footer_editing(admin_client, ts, shopper):
    data = {k: v for k, v in chrome.defaults("footer").items() if not isinstance(v, list)}
    data.update({"hours": "همه روزه ۹ تا ۲۲", "links-rows": "1", "links-0-label": "وبلاگ", "links-0-url": "/blog/",
                 "service_links-rows": "0", "show_social": ""})
    admin_client.post(reverse("builder:theme_panel", args=["footer"]), data)
    ts.refresh_from_db()
    publish(admin_client)
    body = shopper.get("/").content.decode()
    assert "همه روزه ۹ تا ۲۲" in body and "footer-social" not in body
    assert ts.footer["service_links"] == [] and ts.footer["links"] == [{"label": "وبلاگ", "url": "/blog/"}]


def test_default_chrome_matches_previous_markup(client, store):
    """بدون تنظیمات، هدر و فوتر دقیقاً همان پیوندها و متن‌های قبلی را دارند."""
    body = client.get("/").content.decode()
    for label in ["خانه", "فروشگاه", "کالکشن‌ها", "مجله", "درباره ما", "تماس با ما", "دسترسی سریع", "خدمات مشتریان",
                  "پیگیری سفارش", "شنبه تا پنجشنبه، ۱۰ تا ۲۱", "تمامی حقوق محفوظ است.", "رایحه‌هایی برای ماندگاری در خاطره‌ها."]:
        assert label in body
    assert body.count("is-active") == 1 and '<a href="/" class="nav-link is-active">' in body


@pytest.mark.parametrize("path,label", [("/shop/", "فروشگاه"), ("/product/abc/", "فروشگاه"), ("/blog/x/", "مجله"),
                                        ("/about/", "درباره ما"), ("/", "خانه")])
def test_active_menu_item(path, label):
    menu = chrome.defaults("header")["menu"]
    active = [item["label"] for item in menu if chrome.is_active_link(item["url"], path)]
    assert active == [label]


def test_broken_stored_chrome_falls_back_to_defaults(client, store):
    ThemeSettings.objects.filter(store=store, status=ThemeSettings.Status.PUBLISHED).update(header={"menu": [{"label": "x", "url": "javascript:alert(1)"}]})
    r = client.get("/")
    body = r.content.decode()
    assert r.status_code == 200 and "javascript:alert" not in body and "کالکشن‌ها" in body
