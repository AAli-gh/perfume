import json
import os

import pytest
from django.core.exceptions import ValidationError
from django.template import engines
from django.template.loader import get_template, render_to_string
from django.urls import reverse

from apps.core.models import Store
from apps.themes.loaders import theme_template_dirs
from apps.themes.models import Theme, ThemePreset, ThemeSettings
from apps.themes.registry import read_manifest, sync, theme_path
from apps.themes.runtime import get_active_theme_code, use_theme

REAL_THEMES = os.path.join(os.path.dirname(__file__), "..", "..", "..", "themes")


@pytest.fixture
def themes_dir(tmp_path, settings):
    """پوشه موقت پوسته‌ها: base واقعی (لینک) + پوسته آزمایشی «alt» که یک قالب را override می‌کند."""
    (tmp_path / "base").symlink_to(os.path.abspath(os.path.join(REAL_THEMES, "base")), target_is_directory=True)
    (tmp_path / "luxury").symlink_to(os.path.abspath(os.path.join(REAL_THEMES, "luxury")), target_is_directory=True)
    alt = tmp_path / "alt"
    (alt / "templates" / "components").mkdir(parents=True)
    (alt / "templates" / "components" / "toast.html").write_text('<div class="alt-toast">{{ text }}</div>')
    (alt / "templates" / "only_in_alt.html").write_text("ALT ONLY")
    (alt / "theme.json").write_text(json.dumps({
        "code": "alt", "name": "آزمایشی", "presets": [{"code": "alt-one", "name": "یک", "tokens": {"colors": {"primary": "#000000"}}}],
    }))
    settings.THEMES_DIR = tmp_path
    _clear_template_cache()
    yield tmp_path
    _clear_template_cache()


def _clear_template_cache():
    for loader in engines["django"].engine.template_loaders:
        if hasattr(loader, "reset"):
            loader.reset()


# ---------- پیدا کردن قالب ----------

def test_active_theme_overrides_and_falls_back_to_base(themes_dir):
    with use_theme("alt"):
        assert render_to_string("components/toast.html", {"text": "سلام"}) == '<div class="alt-toast">سلام</div>'
        assert "pagination" in get_template("components/pagination.html").origin.name  # از base
        assert render_to_string("only_in_alt.html") == "ALT ONLY"


def test_cache_is_isolated_per_theme(themes_dir):
    """یک نام قالب در دو پوسته، در یک پروسه و پشت سر هم: هر پوسته نسخه خودش را می‌گیرد."""
    with use_theme("alt"):
        alt = render_to_string("components/toast.html", {"text": "x"})
    with use_theme("luxury"):
        lux = render_to_string("components/toast.html", {"text": "x"})
    with use_theme("alt"):
        assert render_to_string("components/toast.html", {"text": "x"}) == alt
    assert alt != lux and 'class="toast"' in lux


def test_template_only_in_other_theme_not_visible(themes_dir):
    from django.template import TemplateDoesNotExist

    with use_theme("luxury"), pytest.raises(TemplateDoesNotExist):
        get_template("only_in_alt.html")


@pytest.mark.parametrize("code", ["../etc", "..", "Alt", "a/b", "", "x" * 60, "base/../alt"])
def test_invalid_theme_codes_never_resolve_outside_themes_dir(themes_dir, code):
    assert theme_path(code) is None
    dirs = theme_template_dirs(code)
    assert dirs == [themes_dir / "base" / "templates"]  # فقط base


def test_admin_templates_still_load(admin_client):
    assert admin_client.get(reverse("admin:index")).status_code == 200


# ---------- ثبت پوسته‌ها ----------

@pytest.mark.django_db
def test_sync_registers_themes_and_presets_idempotently(themes_dir):
    sync(); sync()
    assert Theme.objects.filter(code="alt").count() == 1
    preset = ThemePreset.objects.get(theme__code="alt", code="alt-one")
    assert preset.is_default and preset.tokens["colors"]["primary"] == "#000000"
    assert not Theme.objects.filter(code="base").exists()  # base پوسته قابل انتخاب نیست


@pytest.mark.django_db
def test_manifest_code_must_match_folder(themes_dir):
    (themes_dir / "bad").mkdir()
    (themes_dir / "bad" / "theme.json").write_text(json.dumps({"code": "other", "name": "x"}))
    with pytest.raises(ValueError):
        read_manifest("bad")


def test_luxury_manifest_matches_current_design():
    manifest = read_manifest("luxury")
    gold = manifest["presets"][0]
    assert gold["code"] == "luxury-gold" and gold["tokens"]["colors"]["primary"] == "#c47a45"


# ---------- انتخاب پوسته برای هر فروشگاه ----------

@pytest.mark.django_db
def test_default_store_uses_luxury_after_migration(store):
    settings_ = ThemeSettings.objects.get(store=store, status="published")
    assert settings_.theme.code == "luxury" and settings_.preset.code == "luxury-gold"


@pytest.mark.django_db
def test_new_store_gets_default_theme():
    s = Store.objects.create(name="فروشگاه تازه", code="fresh")
    assert ThemeSettings.objects.get(store=s, status="published").theme.code == "luxury"


@pytest.mark.django_db
def test_middleware_picks_theme_per_store(client, themes_dir, other_store):
    sync()
    alt = Theme.objects.get(code="alt")
    ThemeSettings.objects.filter(store=other_store).update(theme=alt, preset=None)
    assert client.get("/").context["THEME_CODE"] == "luxury"
    assert client.get("/", HTTP_HOST="second.test").context["THEME_CODE"] == "alt"
    assert get_active_theme_code() == "luxury"  # ContextVar بعد از درخواست بازنشانی شده


@pytest.mark.django_db
def test_unavailable_theme_falls_back_to_default(client, store):
    Theme.objects.filter(code="luxury").update(is_available=False)
    assert client.get("/").context["THEME_CODE"] == "luxury"  # DEFAULT_THEME
    assert client.get("/").context["THEME_SETTINGS"] is None


@pytest.mark.django_db
def test_preset_must_belong_to_theme(themes_dir, store):
    sync()
    s = ThemeSettings.objects.get(store=store)
    s.preset = ThemePreset.objects.get(code="alt-one")
    with pytest.raises(ValidationError):
        s.full_clean()
