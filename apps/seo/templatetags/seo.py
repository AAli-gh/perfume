"""{% seo_head %} — همه متاتگ‌های سئوی صفحه در <head>.

    {% seo_head %}                                  ← صفحه عمومی با پیش‌فرض‌ها
    {% seo_head title="فروشگاه" %}                  ← «فروشگاه | نام فروشگاه»
    {% seo_head product %} / {% seo_head post %}    ← عنوان، توضیح، تصویر و JSON-LD از خود آیتم
    {% seo_head page home=True %}                   ← صفحه اصلی (WebSite + OnlineStore)
    {% seo_head title="یافت نشد" noindex=True %}

قالب خروجی در لایه پوسته است (components/seo_head.html) و هر پوسته می‌تواند آن را override کند.
"""

from django import template
from django.template.loader import render_to_string

from ..meta import build

register = template.Library()


@register.simple_tag(takes_context=True)
def seo_head(context, obj=None, **kwargs):
    request = context.get("request")
    if request is None:
        return ""
    seo = build(request, context, obj, **kwargs)
    return render_to_string("components/seo_head.html", {"seo": seo}, request=None)
