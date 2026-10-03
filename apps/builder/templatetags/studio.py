"""ظاهر خود استودیو: همیشه با توکن‌های پیش‌فرض (مستقل از پوسته فروشگاه)، تا خراب شدن پالت فروشگاه
هیچ‌وقت ابزار ویرایش آن را غیرقابل استفاده نکند."""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.themes import tokens as T

register = template.Library()


@register.simple_tag(takes_context=True)
def studio_head(context):
    defaults = T.merge()
    request = context.get("request")
    nonce = getattr(request, "csp_nonce", "") if request is not None else ""
    return format_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '  <link href="{}" rel="stylesheet">\n'
        '  <style id="studio-tokens" nonce="{}">{}</style>',
        T.google_fonts_url(defaults), nonce, mark_safe(T.to_css(defaults)),
    )


@register.simple_tag
def studio_attrs():
    return mark_safe(T.component_attrs(T.merge()))


@register.simple_tag(takes_context=True)
def studio_status(context):
    """وضعیت پیش‌نویس برای نوار انتشار: بخش‌های تغییرکرده و مجوز انتشار کاربر."""
    from ..access import PUBLISH_PERM
    from ..services import pending_changes

    request = context["request"]
    return {"changes": pending_changes(request.store), "can_publish": request.user.has_perm(PUBLISH_PERM)}
