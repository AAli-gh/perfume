import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.themes import tokens as T
from apps.themes.models import ThemePreset, ThemeSettings
from apps.themes.registry import read_manifest

# ---------- اعتبارسنجی و امنیت ----------

@pytest.mark.parametrize("bad", [
    {"colors": {"primary": "red"}},
    {"colors": {"primary": "#fff"}},                                   # فقط #RRGGBB
    {"colors": {"primary": "#c47a45;}</style><script>alert(1)</script>"}},
    {"colors": {"primary": "#c47a45; background:url(//evil)"}},
    {"colors": {"unknown-color": "#000000"}},
    {"typography": {"font_body": "Comic Sans'; } body{display:none"}},
    {"typography": {"base_size": 99}},
    {"typography": {"base_size": "16"}},
    {"radius": {"base": -1}},
    {"radius": {"huge": 4}},
    {"components": {"button": "javascript"}},
    {"components": {"nope": "x"}},
    {"evil": {"x": 1}},
    "not a dict",
])
def test_invalid_tokens_rejected(bad):
    with pytest.raises(ValidationError):
        T.validate(bad, partial=True)


def test_valid_partial_override_is_normalised():
    assert T.validate({"colors": {"primary": "#ABCDEF"}}, partial=True) == {"colors": {"primary": "#abcdef"}}


def test_merge_order_defaults_preset_overrides():
    merged = T.merge({"colors": {"primary": "#111111", "accent": "#222222"}}, {"colors": {"accent": "#333333"}})
    assert merged["colors"]["primary"] == "#111111"
    assert merged["colors"]["accent"] == "#333333"
    assert merged["colors"]["text"] == T.DEFAULT_TOKENS["colors"]["text"]  # بقیه از پیش‌فرض


# ---------- خروجی CSS ----------

def test_css_output_uses_rgb_channels_and_only_safe_characters():
    css = T.to_css({"colors": {"primary": "#c47a45"}})
    assert css.startswith(":root{") and css.endswith("}")
    assert "--color-primary:196 122 69" in css
    assert "--radius:4px" in css and "--font-body:\"Vazirmatn\", Tahoma, sans-serif" in css
    assert "<" not in css and "</style" not in css


def test_component_attrs_and_fonts_url():
    assert 'data-button="gradient"' in T.component_attrs({})
    assert 'data-button="solid"' in T.component_attrs({"components": {"button": "solid"}})
    # پیش‌فرض دقیقاً همان لینک فونت قبلی را تولید می‌کند
    assert T.google_fonts_url({}) == (
        "https://fonts.googleapis.com/css2?family=Aref+Ruqaa:wght@400;700&family=Vazirmatn:wght@300;400;500;700&display=swap"
    )
    url = T.google_fonts_url({"typography": {"font_body": "Vazirmatn", "font_display": "Vazirmatn"}})
    assert url.count("family=") == 1  # فونت تکراری یک بار بارگذاری می‌شود


# ---------- پیش‌تنظیم‌ها ----------

PRESETS = read_manifest("luxury")["presets"] + read_manifest("standard")["presets"]


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p["code"])
def test_every_preset_is_valid_and_defines_all_colors(preset):
    T.validate(preset["tokens"], partial=True)
    assert set(preset["tokens"]["colors"]) == set(T.COLORS)


def test_required_presets_exist():
    assert [p["code"] for p in read_manifest("luxury")["presets"]] == [
        "luxury-gold", "luxury-emerald", "luxury-black", "pearl", "minimal-light"]
    assert [p["code"] for p in read_manifest("standard")["presets"]] == ["ds-indigo", "ds-green", "ds-dark"]


def test_design_system_theme_matches_figma_tokens():
    """پوسته «استاندارد» از Design System فیگما: Inter، ایندیگو ۵۰۰ (#4E61F6)، دکمه یکدست و سبک رابط system."""
    indigo = read_manifest("standard")["presets"][0]["tokens"]
    assert indigo["colors"]["primary"] == "#4e61f6" and indigo["colors"]["text-strong"] == "#131927"
    assert indigo["typography"]["font_body"] == "Inter"
    assert indigo["components"]["ui"] == "system" and indigo["components"]["button"] == "solid"
    assert 'data-ui="system"' in T.component_attrs(indigo)
    assert 'data-ui="classic"' in T.component_attrs({})
    # Inter حروف فارسی ندارد ← وزیرمتن همراهش بارگذاری می‌شود
    url = T.google_fonts_url(indigo)
    assert "family=Inter:" in url and "family=Vazirmatn:" in url and url.count("family=") == 2


def test_luxury_gold_equals_platform_defaults():
    """«طلایی لوکس» = طراحی فعلی؛ پیش‌فرض‌های کد و theme.json نباید از هم جدا شوند."""
    assert T.merge(PRESETS[0]["tokens"]) == T.DEFAULT_TOKENS


def _contrast(a, b):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p["code"])
def test_preset_text_contrast_meets_wcag_aa(preset):
    c = preset["tokens"]["colors"]
    assert _contrast(c["text"], c["background"]) >= 4.5
    assert _contrast(c["text-strong"], c["background"]) >= 4.5
    assert _contrast(c["button-text"], c["button-to"]) >= 4.5
    assert _contrast(c["muted"], c["background"]) >= 3.0  # متن کمکی/کوچک‌تر


# ---------- رندر در صفحه ----------

@pytest.mark.django_db
def test_page_renders_tokens_from_selected_preset(client, store):
    html = client.get("/").content.decode()
    assert re.search(r'<style id="theme-tokens" nonce="[\w-]{16,}">:root\{--color-background:17 11 8', html)
    assert 'data-button="gradient"' in html
    s = ThemeSettings.objects.get(store=store, status="published")
    s.preset = ThemePreset.objects.get(code="minimal-light")
    s.save()
    html = client.get("/").content.decode()
    assert "--color-background:255 255 255" in html and 'data-button="solid"' in html
    assert '<meta name="theme-color" content="#ffffff">' in html


@pytest.mark.django_db
def test_store_overrides_apply_on_top_of_preset(client, store):
    s = ThemeSettings.objects.get(store=store, status="published")
    s.overrides = {"colors": {"primary": "#123456"}, "radius": {"base": 12}}
    s.full_clean()
    s.save()
    html = client.get("/").content.decode()
    assert "--color-primary:18 52 86" in html and "--radius:12px" in html
    assert "--color-accent:231 185 140" in html  # از پیش‌تنظیم


@pytest.mark.django_db
def test_invalid_overrides_rejected_by_model(store):
    s = ThemeSettings.objects.get(store=store, status="published")
    s.overrides = {"colors": {"primary": "red;}"}}
    with pytest.raises(ValidationError):
        s.full_clean()


@pytest.mark.django_db
def test_two_stores_two_palettes(client, store, other_store):
    s = ThemeSettings.objects.get(store=other_store, status="published")
    s.preset = ThemePreset.objects.get(code="luxury-emerald")
    s.save()
    assert "--color-background:17 11 8" in client.get("/").content.decode()
    assert "--color-background:7 19 15" in client.get("/", HTTP_HOST="second.test").content.decode()


@pytest.mark.django_db
def test_favicon_monogram(client, store):
    html = client.get("/").content.decode()
    assert "%D9%85" in html  # «م» برای فروشگاه پیش‌فرض (migration)


def test_built_css_has_no_hardcoded_store_colors():
    """همه رنگ‌های طراحی از CSS Variables می‌آیند (فقط پیش‌فرض‌های خنثی Tailwind preflight مجازند)."""
    css_file = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    if not css_file.exists():
        pytest.skip("CSS ساخته نشده (npm run build:css)")
    found = set(re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", css_file.read_text())) - {"#9ca3af", "#e5e7eb", "#fff", "#000"}
    assert not found, found


@pytest.mark.django_db
def test_switching_to_design_system_theme(client, store):
    from apps.themes import services
    from apps.themes.models import Theme
    from apps.themes.registry import sync

    sync()
    services.change_theme(ThemeSettings.objects.get(store=store, status="published"), Theme.objects.get(code="standard"))
    html = client.get("/").content.decode()
    assert 'data-ui="system"' in html and 'data-button="solid"' in html
    assert "--color-primary:78 97 246" in html and "family=Inter:" in html
