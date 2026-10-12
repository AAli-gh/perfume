"""Design Tokens: schema، اعتبارسنجی، ترکیب و تبدیل به CSS Variables.

ترتیب ترکیب توکن‌ها (هر لایه لایه قبلی را بازنویسی می‌کند):
    DEFAULT_TOKENS  ←  پیش‌تنظیم (ThemePreset.tokens)  ←  شخصی‌سازی فروشگاه (ThemeSettings.overrides)

امنیت: هیچ مقداری بدون اعتبارسنجی وارد CSS نمی‌شود — رنگ‌ها فقط #RRGGBB، فونت‌ها فقط از فهرست مجاز،
اعداد در بازه مجاز و گونه‌های کامپوننت فقط از گزینه‌های تعریف‌شده. پس تزریق CSS/HTML ممکن نیست.
"""

import copy
import re

from django.core.exceptions import ValidationError

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# ---------- رنگ‌ها ----------
# name: (پیش‌فرض = طراحی فعلی «طلایی لوکس», برچسب فارسی, گروه)
COLORS = {
    "background": ("#110b08", "پس‌زمینه", "پایه"),
    "background-2": ("#170f0b", "پس‌زمینه دوم", "پایه"),
    "surface": ("#1d140f", "سطح (کشوها، پیام‌ها)", "پایه"),
    "panel": ("#221610", "پنل‌ها", "پایه"),
    "media": ("#0d0806", "زمینه تصاویر", "پایه"),
    "hero": ("#150d09", "زمینه و سایه هیرو", "پایه"),
    "overlay": ("#0a0604", "پوشش (جستجو، منوی موبایل)", "پایه"),
    "footer": ("#0c0806", "فوتر", "پایه"),
    "input": ("#000000", "زمینه فیلدها", "پایه"),
    "primary": ("#c47a45", "رنگ اصلی", "برند"),
    "primary-dark": ("#8a4119", "رنگ اصلی تیره", "برند"),
    "accent": ("#e7b98c", "رنگ تأکیدی (تیترها)", "برند"),
    "accent-soft": ("#d8a77a", "تأکیدی ملایم (لینک‌ها)", "برند"),
    "text-strong": ("#f0dcc6", "متن پررنگ", "متن"),
    "text": ("#dccab8", "متن", "متن"),
    "muted": ("#9b8574", "متن کم‌رنگ", "متن"),
    "placeholder": ("#7a6656", "متن راهنمای فیلد", "متن"),
    "price": ("#f3dcc4", "قیمت", "متن"),
    "border": ("#c48454", "خطوط و حاشیه‌ها", "پایه"),
    "success": ("#9cc28a", "موفقیت", "وضعیت"),
    "danger": ("#e0806a", "خطا", "وضعیت"),
    "button-from": ("#a9582a", "دکمه — شروع گرادیان", "دکمه"),
    "button-to": ("#7d3a16", "دکمه — پایان گرادیان", "دکمه"),
    "button-border": ("#c9763d", "دکمه — حاشیه", "دکمه"),
    "button-text": ("#f6dcc4", "دکمه — متن", "دکمه"),
    "button-text-hover": ("#fff3e6", "دکمه — متن (hover)", "دکمه"),
    "button-highlight": ("#ffd2aa", "دکمه — برق بالایی", "دکمه"),
    "card-from": ("#281b14", "کارت محصول — بالا", "کارت"),
    "card-to": ("#18100c", "کارت محصول — پایین", "کارت"),
    "glow-1": ("#8c461e", "درخشش پس‌زمینه ۱", "جلوه"),
    "glow-2": ("#783c19", "درخشش پس‌زمینه ۲", "جلوه"),
    "glow-3": ("#6e3719", "درخشش پس‌زمینه ۳", "جلوه"),
}

# ---------- حالت شب و روز ----------
# پالت اصلی (colors) هر پوسته یک حالت است و colors_alt حالت مقابل آن. اگر پالت اصلی تیره باشد، حالت دوم «روز»
# است و پیش‌فرضش DAY_COLORS؛ اگر روشن باشد، حالت دوم «شب» است و پیش‌فرضش رنگ‌های «طلایی لوکس».
DAY_COLORS = {
    "background": "#faf6f1", "background-2": "#f3ece4", "surface": "#ffffff", "panel": "#ffffff",
    "media": "#efe7de", "hero": "#f4ece3", "overlay": "#faf6f1", "footer": "#f1e9e0", "input": "#ffffff",
    "primary": "#b0683a", "primary-dark": "#8a4119", "accent": "#7a4524", "accent-soft": "#93532b",
    "text-strong": "#2b1d17", "text": "#4a3a33", "muted": "#7d6a60", "placeholder": "#a8968c", "price": "#5a3a2e",
    "border": "#b08b78", "success": "#4f8a3c", "danger": "#b4483a",
    "button-from": "#b8673a", "button-to": "#8a4119", "button-border": "#8a4119", "button-text": "#ffffff",
    "button-text-hover": "#ffffff", "button-highlight": "#ffe2c9", "card-from": "#ffffff", "card-to": "#f6efe8",
    "glow-1": "#e8c9b8", "glow-2": "#f0d9cc", "glow-3": "#e6d3c3",
}
MODE_DEFAULTS = ("main", "alt", "system")  # حالت پیش‌فرض بازدیدکننده تازه: پالت اصلی / حالت دوم / مطابق دستگاه
MODE_COOKIE = "majd_mode"


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def scheme_of(colors):
    """dark یا light بر اساس روشنایی پس‌زمینه."""
    return "dark" if _luminance(colors["background"]) < 0.4 else "light"


# ---------- فونت‌ها (فقط از این فهرست؛ نام فونت مستقیماً وارد CSS و URL می‌شود) ----------
FONTS = {
    "Vazirmatn": {"google": "Vazirmatn:wght@300;400;500;700", "stack": '"Vazirmatn", Tahoma, sans-serif'},
    "Aref Ruqaa": {"google": "Aref+Ruqaa:wght@400;700", "stack": '"Aref Ruqaa", "Vazirmatn", serif'},
    "Lalezar": {"google": "Lalezar", "stack": '"Lalezar", "Vazirmatn", sans-serif'},
    "Noto Naskh Arabic": {"google": "Noto+Naskh+Arabic:wght@400;500;700", "stack": '"Noto Naskh Arabic", "Vazirmatn", serif'},
    "Amiri": {"google": "Amiri:wght@400;700", "stack": '"Amiri", "Vazirmatn", serif'},
    "Markazi Text": {"google": "Markazi+Text:wght@400;500;700", "stack": '"Markazi Text", "Vazirmatn", serif'},
    "Noto Sans Arabic": {"google": "Noto+Sans+Arabic:wght@300;400;500;700", "stack": '"Noto Sans Arabic", Tahoma, sans-serif'},
    # Inter حروف فارسی ندارد: متن لاتین و ارقام انگلیسی با Inter و حروف فارسی با وزیرمتن (همراه بارگذاری می‌شود)
    "Inter": {"google": "Inter:wght@400;500;600;700", "stack": '"Inter", "Vazirmatn", Tahoma, sans-serif',
              "with": ["Vazirmatn:wght@300;400;500;700"]},
}

# ---------- اعداد (px) ----------
SIZES = {
    "typography.base_size": (16, 14, 20, "اندازه پایه متن"),
    "radius.sm": (2, 0, 16, "گردی گوشه کوچک"),
    "radius.base": (4, 0, 24, "گردی گوشه پایه"),
    "radius.lg": (8, 0, 32, "گردی گوشه بزرگ"),
    "spacing.section": (70, 24, 140, "فاصله عمودی بخش‌ها"),
}

# ---------- گونه‌های کامپوننت ----------
COMPONENTS = {
    "button": ("gradient", ["gradient", "solid", "outline"], "سبک دکمه"),
    "card": ("gradient", ["gradient", "flat", "outline"], "سبک کارت محصول"),
    "header": ("blur", ["blur", "solid"], "سبک هدر"),
    "background": ("glow", ["glow", "plain"], "جلوه پس‌زمینه"),
    "texture": ("noise", ["noise", "none"], "بافت پس‌زمینه"),
    "shadow": ("strong", ["strong", "soft", "none"], "سایه پنل‌ها و کارت‌ها"),
    # system: قواعد Design System (وزن فونت، حالت‌های دکمه، فوکوس، بج‌ها، کارت و فیلدها) — static/src/input.css
    "ui": ("classic", ["classic", "system"], "سبک رابط کاربری"),
}


def _defaults():
    return {
        "colors": {k: v[0] for k, v in COLORS.items()},
        "typography": {"font_body": "Vazirmatn", "font_display": "Aref Ruqaa", "base_size": 16},
        "radius": {"sm": 2, "base": 4, "lg": 8},
        "spacing": {"section": 70},
        "components": {k: v[0] for k, v in COMPONENTS.items()},
        "colors_alt": {},  # فقط رنگ‌های تغییرکرده؛ بقیه از پالت مقابل (merge کامل می‌کند)
        "mode": {"toggle": True, "default": "main"},
    }


_RAW_DEFAULTS = _defaults()


def merge(*layers):
    """ترکیب عمیق لایه‌های توکن (لایه بعدی برنده است). colors_alt در پایان با پالت مقابل کامل می‌شود."""
    result = copy.deepcopy(_RAW_DEFAULTS)
    for layer in layers:
        for group, values in (layer or {}).items():
            if isinstance(values, dict) and isinstance(result.get(group), dict):
                result[group].update(values)
            else:
                result[group] = values
    counterpart = DAY_COLORS if scheme_of(result["colors"]) == "dark" else _RAW_DEFAULTS["colors"]
    result["colors_alt"] = {**counterpart, **result["colors_alt"]}
    return result


DEFAULT_TOKENS = merge()


def validate(tokens, *, partial=False):
    """اعتبارسنجی توکن‌ها؛ خروجی: نسخه پاک‌شده. partial=True برای overrides (فقط کلیدهای داده‌شده)."""
    errors = {}
    tokens = tokens or {}
    if not isinstance(tokens, dict):
        raise ValidationError("توکن‌ها باید یک شیء JSON باشند.")
    clean = {}
    unknown_groups = set(tokens) - set(DEFAULT_TOKENS)
    if unknown_groups:
        errors["groups"] = f"گروه ناشناخته: {', '.join(sorted(map(str, unknown_groups)))}"

    colors = tokens.get("colors", {})
    if colors:
        clean["colors"] = {}
        for name, value in colors.items():
            if name not in COLORS:
                errors[f"colors.{name}"] = "رنگ ناشناخته"
            elif not isinstance(value, str) or not HEX.match(value):
                errors[f"colors.{name}"] = "رنگ باید به شکل #RRGGBB باشد"
            else:
                clean["colors"][name] = value.lower()

    alt = tokens.get("colors_alt", {})
    if alt:
        clean["colors_alt"] = {}
        for name, value in alt.items():
            if name not in COLORS:
                errors[f"colors_alt.{name}"] = "رنگ ناشناخته"
            elif not isinstance(value, str) or not HEX.match(value):
                errors[f"colors_alt.{name}"] = "رنگ باید به شکل #RRGGBB باشد"
            else:
                clean["colors_alt"][name] = value.lower()

    mode = tokens.get("mode", {})
    if mode:
        clean["mode"] = {}
        if "toggle" in mode:
            if not isinstance(mode["toggle"], bool):
                errors["mode.toggle"] = "باید true یا false باشد"
            else:
                clean["mode"]["toggle"] = mode["toggle"]
        if "default" in mode:
            if mode["default"] not in MODE_DEFAULTS:
                errors["mode.default"] = f"یکی از: {', '.join(MODE_DEFAULTS)}"
            else:
                clean["mode"]["default"] = mode["default"]
        unknown = set(mode) - {"toggle", "default"}
        if unknown:
            errors["mode"] = f"کلید ناشناخته: {', '.join(sorted(map(str, unknown)))}"

    typo = tokens.get("typography", {})
    if typo:
        clean["typography"] = {}
        for key in ("font_body", "font_display"):
            if key in typo:
                if typo[key] not in FONTS:
                    errors[f"typography.{key}"] = "فونت مجاز نیست"
                else:
                    clean["typography"][key] = typo[key]
        unknown = set(typo) - {"font_body", "font_display", "base_size"}
        if unknown:
            errors["typography"] = f"کلید ناشناخته: {', '.join(sorted(unknown))}"

    for path, (_, lo, hi, _label) in SIZES.items():
        group, key = path.split(".")
        if key in tokens.get(group, {}):
            value = tokens[group][key]
            if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
                errors[path] = f"عدد صحیح بین {lo} و {hi}"
            else:
                clean.setdefault(group, {})[key] = value
    for group in ("radius", "spacing"):
        allowed = {p.split(".")[1] for p in SIZES if p.startswith(group + ".")}
        unknown = set(tokens.get(group, {})) - allowed
        if unknown:
            errors[group] = f"کلید ناشناخته: {', '.join(sorted(unknown))}"

    comps = tokens.get("components", {})
    for name, value in comps.items():
        if name not in COMPONENTS:
            errors[f"components.{name}"] = "کامپوننت ناشناخته"
        elif value not in COMPONENTS[name][1]:
            errors[f"components.{name}"] = f"یکی از: {', '.join(COMPONENTS[name][1])}"
        else:
            clean.setdefault("components", {})[name] = value

    if errors:
        raise ValidationError(errors)
    return clean if partial else merge(clean)


def resolve(theme_settings):
    """توکن‌های نهایی یک ThemeSettings (پیش‌فرض ← پیش‌تنظیم ← شخصی‌سازی)، اعتبارسنجی‌شده."""
    preset = getattr(theme_settings, "preset", None) if theme_settings else None
    layers = [preset.tokens if preset else {}, theme_settings.overrides if theme_settings else {}]
    return merge(*(validate(layer, partial=True) for layer in layers))


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)} {int(h[2:4], 16)} {int(h[4:6], 16)}"


def _color_vars(colors):
    return [f"--color-{name}:{_rgb(value)}" for name, value in colors.items()] + [f"color-scheme:{scheme_of(colors)}"]


def to_css(tokens):
    """:root { --color-primary: 196 122 69; … } — رنگ‌ها به‌صورت کانال RGB تا Tailwind بتواند شفافیت (/20) اعمال کند.

    حالت شب/روز: html[data-mode="alt"] پالت دوم را جایگزین می‌کند (انتخاب بازدیدکننده در کوکی). اگر پیش‌فرض
    «مطابق دستگاه» باشد، تا وقتی بازدیدکننده انتخابی نکرده (بدون data-mode) media query تصمیم می‌گیرد.
    """
    t = merge(validate(tokens, partial=True))
    lines = _color_vars(t["colors"])
    lines += [
        f"--font-body:{FONTS[t['typography']['font_body']]['stack']}",
        f"--font-display:{FONTS[t['typography']['font_display']]['stack']}",
        f"--font-size-base:{t['typography']['base_size']}px",
        f"--radius-sm:{t['radius']['sm']}px",
        f"--radius:{t['radius']['base']}px",
        f"--radius-lg:{t['radius']['lg']}px",
        f"--space-section:{t['spacing']['section']}px",
    ]
    css = ":root{" + ";".join(lines) + "}"
    mode = t["mode"]
    if mode["toggle"] or mode["default"] != "main":
        alt = ";".join(_color_vars(t["colors_alt"]))
        css += 'html[data-mode="alt"]{' + alt + "}"
        if mode["default"] == "system" and mode["toggle"]:
            css += f"@media (prefers-color-scheme:{scheme_of(t['colors_alt'])}){{html:not([data-mode]){{{alt}}}}}"
    return css


def mode_info(tokens):
    """برای قالب‌ها: حالت اصلی/دوم (dark|light)، پیش‌فرض و نمایش دکمه."""
    t = merge(validate(tokens, partial=True))
    return {"main": scheme_of(t["colors"]), "alt": scheme_of(t["colors_alt"]), "default": t["mode"]["default"],
            "toggle": t["mode"]["toggle"]}


def initial_mode(tokens, cookie_value):
    """data-mode روی <html>: انتخاب بازدیدکننده (کوکی)، وگرنه پیش‌فرض؛ برای «مطابق دستگاه» خالی (media query)."""
    info = mode_info(tokens)
    if info["toggle"] and cookie_value in ("main", "alt"):
        return cookie_value
    if info["default"] == "system":
        return "" if info["toggle"] else "main"
    return info["default"]


def component_attrs(tokens):
    """ویژگی‌های data-* روی <html> برای انتخاب گونه کامپوننت‌ها در CSS."""
    comps = merge(validate(tokens, partial=True))["components"]
    return " ".join(f'data-{name}="{value}"' for name, value in comps.items())


def google_fonts_url(tokens):
    typo = merge(validate(tokens, partial=True))["typography"]
    families = []
    for key in ("font_display", "font_body"):  # ترتیب فعلی لینک: Aref Ruqaa سپس Vazirmatn
        for spec in (FONTS[typo[key]]["google"], *FONTS[typo[key]].get("with", ())):
            if spec not in families:
                families.append(spec)
    return "https://fonts.googleapis.com/css2?" + "&".join(f"family={f}" for f in families) + "&display=swap"
