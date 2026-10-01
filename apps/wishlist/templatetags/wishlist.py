from django import template

from ..services import is_wishlisted

register = template.Library()


@register.inclusion_tag("wishlist/partials/button.html", takes_context=True)
def wishlist_button(context, product):
    return {"product": product, "active": is_wishlisted(context["request"].user, product), "csrf_token": context.get("csrf_token")}
