import pytest
from django.core import signing
from django.test import Client
from django.urls import reverse

from apps.builder import services as builder
from apps.builder.models import Revision, Workspace
from apps.builder.preview import SESSION_TOKEN
from apps.builder.services import editable_page
from apps.pages.models import Page, PageSection
from apps.pages.services import page_sections
from apps.themes.models import ThemePreset, ThemeSettings
from apps.themes.services import draft_settings

from .test_studio import make_user

pytestmark = pytest.mark.django_db
DRAFT, PUBLISHED = PageSection.Status.DRAFT, PageSection.Status.PUBLISHED


@pytest.fixture
def boss(store):
    return make_user("boss@example.com", superuser=True)


@pytest.fixture
def admin_client(boss):
    c = Client()
    c.force_login(boss)
    return c


@pytest.fixture
def shopper(store):
    return Client()


@pytest.fixture
def home(store):
    return editable_page(Page.objects.get(store=store, is_home=True))


def set_primary(admin_client, store, hex_color):
    data = {f"color__{k}": v for k, v in builder.T.resolve(draft_settings(store))["colors"].items()}
    data["color__primary"] = hex_color
    assert admin_client.post(reverse("builder:theme_panel", args=["colors"]), data).status_code == 302


def rgb(hex_color):
    h = hex_color.lstrip("#")
    return " ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


# ---------- پیش‌نویس جدا از فروشگاه ----------

def test_edits_do_not_reach_customers_until_publish(admin_client, shopper, store, home):
    set_primary(admin_client, store, "#123456")
    banner = page_sections(home, DRAFT).get(type="banner")
    admin_client.post(reverse("builder:section_toggle", args=[home.pk, banner.pk]))
    body = shopper.get("/").content.decode()
    assert "--color-primary:18 52 86" not in body and "هنر عطرسازی" in body
    assert builder.pending_changes(store) == ["رنگ‌ها", "صفحه «صفحه اصلی»"]
    admin_client.post(reverse("builder:publish"), {"label": "رنگ تازه"})
    body = shopper.get("/").content.decode()
    assert "--color-primary:18 52 86" in body and "هنر عطرسازی" not in body
    assert builder.pending_changes(store) == []


def test_publish_records_revisions_with_baseline(admin_client, store, boss):
    set_primary(admin_client, store, "#123456")
    admin_client.post(reverse("builder:publish"), {"label": "رنگ تازه"})
    baseline, first = Revision.objects.for_store(store).order_by("number")
    assert baseline.kind == "baseline" and baseline.snapshot["theme"]["overrides"] == {}
    assert first.number == 2 and first.label == "رنگ تازه" and first.created_by == boss
    assert first.changes == ["رنگ‌ها"] and first.snapshot["theme"]["overrides"] == {"colors": {"primary": "#123456"}}


def test_publish_without_changes_is_noop(admin_client, store):
    admin_client.post(reverse("builder:publish"))
    assert not Revision.objects.for_store(store).exists()


def test_discard_resets_draft(admin_client, store, home):
    set_primary(admin_client, store, "#123456")
    admin_client.post(reverse("builder:section_add", args=[home.pk]), {"type": "faq"})
    admin_client.post(reverse("builder:discard"))
    assert builder.pending_changes(store) == []
    assert draft_settings(store).overrides == {}
    assert not page_sections(home, DRAFT).filter(type="faq").exists()


def test_restore_previous_revision_into_draft(admin_client, shopper, store):
    set_primary(admin_client, store, "#111111")
    admin_client.post(reverse("builder:publish"))
    set_primary(admin_client, store, "#222222")
    admin_client.post(reverse("builder:publish"))
    first = Revision.objects.for_store(store).get(number=2)
    r = admin_client.post(reverse("builder:restore", args=[first.number]))
    assert r["Location"] == reverse("builder:preview")
    assert rgb("#222222") in shopper.get("/").content.decode()  # فروشگاه هنوز نسخه فعلی
    assert draft_settings(store).overrides == {"colors": {"primary": "#111111"}}
    admin_client.post(reverse("builder:publish"))
    assert f"--color-primary:{rgb('#111111')}" in shopper.get("/").content.decode()


def test_restore_brings_back_page_layout(admin_client, store, home):
    before = list(page_sections(home, PUBLISHED).values_list("type", flat=True))
    admin_client.post(reverse("builder:publish"))  # بدون تغییر
    for s in page_sections(home, DRAFT).filter(type__in=["banner", "blog"]):
        admin_client.post(reverse("builder:section_delete", args=[home.pk, s.pk]))
    admin_client.post(reverse("builder:publish"))
    baseline = Revision.objects.for_store(store).get(kind="baseline")
    admin_client.post(reverse("builder:restore", args=[baseline.number]))
    admin_client.post(reverse("builder:publish"))
    assert list(page_sections(home, PUBLISHED).values_list("type", flat=True)) == before


def test_restore_of_other_store_revision_is_404(admin_client, other_store):
    rev = Revision.objects.create(store=other_store, number=1, snapshot={})
    assert admin_client.post(reverse("builder:restore", args=[rev.number])).status_code == 404


def test_old_revisions_pruned(store):
    for n in range(1, builder.KEEP_REVISIONS + 6):
        Revision.objects.create(store=store, number=n, snapshot={})
    ts = draft_settings(store)
    ts.overrides = {"colors": {"primary": "#123456"}}
    ts.save()
    builder.publish(store)
    assert Revision.objects.for_store(store).count() == builder.KEEP_REVISIONS


def test_publish_permission_required(client, store, home):
    editor = make_user("ed@example.com", perms=["themes.change_themesettings", "pages.change_pagesection"])
    client.force_login(editor)
    set_primary(client, store, "#123456")
    assert client.post(reverse("builder:publish")).status_code == 403
    assert client.post(reverse("builder:discard")).status_code == 403
    page = client.get(reverse("builder:dashboard")).content.decode()
    assert "تغییرات منتشرنشده" in page and "مجوز انتشار" in page
    assert ThemeSettings.objects.get(store=store, status="published").overrides == {}


def test_draft_shared_files_survive_publish_and_restore(admin_client, store, home):
    """تصویر بخش بین پیش‌نویس و نسخه منتشرشده مشترک است؛ با انتشار و بازگشت از بین نمی‌رود."""
    from .test_studio import PNG
    from django.core.files.uploadedfile import SimpleUploadedFile

    hero = page_sections(home, DRAFT).get(type="hero")
    url = reverse("builder:section", args=[home.pk, hero.pk])
    admin_client.post(url, {**hero.settings, "image": SimpleUploadedFile("h.png", PNG, content_type="image/png")})
    admin_client.post(reverse("builder:publish"))
    published = page_sections(home, PUBLISHED).get(type="hero")
    hero.refresh_from_db()
    assert published.image.name == hero.image.name and published.image.storage.exists(published.image.name)


# ---------- پیش‌نمایش ----------

def test_staff_preview_shows_draft_with_safe_headers(admin_client, store):
    set_primary(admin_client, store, "#123456")
    assert admin_client.get(reverse("builder:preview")).status_code == 200
    r = admin_client.get("/")
    body = r.content.decode()
    assert "--color-primary:18 52 86" in body and "data-preview-banner" in body
    assert r["Cache-Control"] == "private, no-store" and "noindex" in r["X-Robots-Tag"]
    assert r["X-Frame-Options"] == "SAMEORIGIN"
    admin_client.get(reverse("builder:preview_exit"))
    r = admin_client.get("/")
    assert "--color-primary:18 52 86" not in r.content.decode() and r["X-Frame-Options"] == "DENY"


def test_storefront_not_framable_outside_preview(shopper, store):
    r = shopper.get("/")
    assert r["X-Frame-Options"] == "DENY" and "data-preview-banner" not in r.content.decode()


def test_preview_session_ignored_after_losing_staff(admin_client, boss, store):
    set_primary(admin_client, store, "#123456")
    admin_client.get(reverse("builder:preview"))
    boss.is_staff = False
    boss.save()
    assert "--color-primary:18 52 86" not in admin_client.get("/").content.decode()


def test_preview_page_shows_draft_of_page_layout(admin_client, store, home):
    banner = page_sections(home, DRAFT).get(type="banner")
    admin_client.post(reverse("builder:section_toggle", args=[home.pk, banner.pk]))
    admin_client.get(reverse("builder:preview"))
    assert "هنر عطرسازی" not in admin_client.get("/").content.decode()


def share_link(admin_client):
    admin_client.post(reverse("builder:preview_link"))
    page = admin_client.get(reverse("builder:preview")).content.decode()
    start = page.index('value="', page.index('id="share-link"')) + len('value="')
    return page[start:page.index('"', start)]


def test_share_link_lets_anonymous_preview(admin_client, shopper, store):
    set_primary(admin_client, store, "#123456")
    link = share_link(admin_client)
    assert "/studio/preview/s/" in link
    r = shopper.get(link)
    assert r.status_code == 302
    body = shopper.get("/").content.decode()
    assert "--color-primary:18 52 86" in body and "data-preview-banner" in body
    assert shopper.get(reverse("builder:dashboard")).status_code == 302  # بدون دسترسی استودیو


def test_share_link_revoked_on_publish(admin_client, shopper, store):
    set_primary(admin_client, store, "#123456")
    link = share_link(admin_client)
    shopper.get(link)
    admin_client.post(reverse("builder:publish"))
    set_primary(admin_client, store, "#654321")
    assert rgb("#654321") not in shopper.get("/").content.decode()
    assert SESSION_TOKEN not in shopper.session
    assert shopper.get(link).status_code == 404


def test_share_link_rejects_tampered_expired_and_foreign_tokens(admin_client, shopper, store, other_store):
    link = share_link(admin_client)
    token = link.rstrip("/").rsplit("/", 1)[1]
    assert shopper.get(reverse("builder:preview_share", args=[token[:-2] + "xx"])).status_code == 404
    foreign = signing.dumps({"s": other_store.pk, "k": Workspace.objects.get(store=store).preview_key.hex},
                            salt=builder.PREVIEW_SALT, compress=True)
    assert shopper.get(reverse("builder:preview_share", args=[foreign])).status_code == 404
    from unittest import mock

    import time

    later = time.time() + (builder.PREVIEW_LINK_HOURS + 1) * 3600
    with mock.patch("django.core.signing.time.time", return_value=later):
        assert shopper.get(reverse("builder:preview_share", args=[token])).status_code == 404


def test_share_link_requires_publish_permission(client, store):
    client.force_login(make_user("ed@example.com", perms=["themes.change_themesettings"]))
    assert client.post(reverse("builder:preview_link")).status_code == 403


def test_preview_path_cannot_point_outside(admin_client):
    for bad in ["https://evil.example/", "//evil.example/", "/studio/theme/", "javascript:alert(1)"]:
        page = admin_client.get(reverse("builder:preview"), {"path": bad}).content.decode()
        assert 'src="/"' in page, bad


def test_publish_next_redirect_is_safe(admin_client, store):
    set_primary(admin_client, store, "#123456")
    r = admin_client.post(reverse("builder:publish"), {"next": "https://evil.example/"})
    assert r["Location"] == reverse("builder:dashboard")


def test_preset_change_listed_in_changes(admin_client, store):
    ts = draft_settings(store)
    emerald = ThemePreset.objects.get(theme=ts.theme, code="luxury-emerald")
    admin_client.post(reverse("builder:theme_panel", args=["preset"]), {"action": "preset", "preset": emerald.pk})
    assert builder.pending_changes(store) == ["پوسته و پیش‌تنظیم"]


def test_history_and_preview_pages_render(admin_client, store):
    set_primary(admin_client, store, "#123456")
    admin_client.post(reverse("builder:publish"), {"label": "<b>x</b>"})
    page = admin_client.get(reverse("builder:history")).content.decode()
    assert "&lt;b&gt;x&lt;/b&gt;" in page and "نسخه فعلی فروشگاه" in page
    assert admin_client.get(reverse("builder:preview")).status_code == 200


def test_htmx_section_change_refreshes_preview_and_publish_bar(admin_client, home):
    banner = page_sections(home, DRAFT).get(type="banner")
    r = admin_client.post(reverse("builder:section_toggle", args=[home.pk, banner.pk]), HTTP_HX_REQUEST="true")
    assert r["HX-Trigger"] == "preview-refresh"
    body = r.content.decode()
    assert 'id="publish-bar"' in body and 'hx-swap-oob="true"' in body and "تغییرات منتشرنشده" in body
