"""ظاهر خود استودیو: همیشه با توکن‌های پیش‌فرض (مستقل از پوسته فروشگاه)، تا خراب شدن پالت فروشگاه
هیچ‌وقت ابزار ویرایش آن را غیرقابل استفاده نکند."""

from django import template
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from apps.themes import tokens as T

register = template.Library()


@register.simple_tag
def studio_head():
    defaults = T.merge()
    return format_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '  <link href="{}" rel="stylesheet">\n'
        '  <style id="studio-tokens">{}</style>',
        T.google_fonts_url(defaults), mark_safe(T.to_css(defaults)),
    )


@register.simple_tag
def studio_attrs():
    return mark_safe(T.component_attrs(T.merge()))


@register.filter
def token_css_vars(tokens):
    """متغیرهای توکن برای پیش‌نمایش کوچک داخل استودیو (برای ویژگی style؛ escape‌شده)."""
    css = T.to_css(tokens)
    return escape(css[len(":root{"):-1])
