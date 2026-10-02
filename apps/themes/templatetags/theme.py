"""تزریق Design Tokens پوسته فعال به صفحه: <style>:root{--color-…}</style>، فونت‌ها، رنگ مرورگر و favicon."""

from urllib.parse import quote

from django import template
from django.core.cache import cache
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .. import tokens as T

register = template.Library()


def page_tokens(context):
    """توکن‌های نهایی برای این درخواست (یک بار محاسبه و cache می‌شود)."""
    request = context.get("request")
    cached = getattr(request, "_theme_tokens", None) if request else None
    if cached is not None:
        return cached
    settings_ = context.get("THEME_SETTINGS")
    key = f"theme-tokens:{settings_.pk}:{settings_.updated_at.timestamp()}:{settings_.preset_id}" if settings_ else None
    resolved = cache.get(key) if key else None
    if resolved is None:
        resolved = T.resolve(settings_)
        if key:
            cache.set(key, resolved, 3600)
    if request is not None:
        request._theme_tokens = resolved
    return resolved


def _favicon(context, tokens):
    settings_ = context.get("THEME_SETTINGS")
    if settings_ and settings_.favicon:
        return settings_.favicon.url
    site = context.get("SITE") or {}
    monogram = ((settings_.header or {}).get("monogram") if settings_ else None) or (site.get("name") or "•")[:1]
    bg, fg = tokens["colors"]["background"], tokens["colors"]["accent"]
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        f"<rect width='64' height='64' rx='12' fill='{bg}'/>"
        f"<text x='32' y='44' font-size='34' text-anchor='middle' fill='{fg}' font-family='serif'>{monogram[:1]}</text></svg>"
    )
    return "data:image/svg+xml," + quote(svg, safe="/:='. ")


@register.simple_tag(takes_context=True)
def theme_head(context):
    t = page_tokens(context)
    return format_html(
        '<meta name="theme-color" content="{}">\n'
        '  <link rel="icon" href="{}">\n'
        '  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '  <link href="{}" rel="stylesheet">\n'
        '  <style id="theme-tokens">{}</style>',
        t["colors"]["background"], _favicon(context, t), T.google_fonts_url(t), mark_safe(T.to_css(t)),
    )


@register.simple_tag(takes_context=True)
def theme_attrs(context):
    """data-button="gradient" data-card="…" … روی تگ <html>."""
    return mark_safe(T.component_attrs(page_tokens(context)))
