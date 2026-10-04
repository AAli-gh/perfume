from django import template

from ..compare import CompareList

register = template.Library()


@register.inclusion_tag("discovery/partials/compare_button.html", takes_context=True)
def compare_button(context, product, variant="button"):
    """variant: button (صفحه محصول) یا icon (کارت محصول)."""
    request = context["request"]
    return {"product": product, "active": product.pk in CompareList(request), "variant": variant,
            "csrf_token": context.get("csrf_token")}


@register.inclusion_tag("discovery/partials/compare_badge.html", takes_context=True)
def compare_badge(context):
    return {"compare": CompareList(context["request"])}


@register.simple_tag(takes_context=True)
def recommendations_for_user(context, limit=8):
    """(محصولات پیشنهادی، نت‌های محبوب، منابع) برای صفحه حساب و بخش «پیشنهاد برای شما»."""
    from ..taste import recommendations_for

    products, taste, sources = recommendations_for(context["request"], limit=limit)
    return {"products": products, "favorite_notes": taste.favorite_notes(), "sources": sources}
