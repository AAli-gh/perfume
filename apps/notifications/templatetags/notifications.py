from django import template
from ..services import settings_for

register = template.Library()


@register.simple_tag(takes_context=True)
def otp_login_enabled(context):
    from ..views import otp_enabled

    request = context.get("request")
    store = getattr(request, "store", None)
    return bool(store and otp_enabled(store))


@register.simple_tag(takes_context=True)
def price_drop_enabled(context):
    """خبر کاهش قیمت علاقه‌مندی‌ها در این فروشگاه روشن است؟"""
    store = getattr(context.get("request"), "store", None)
    return store is not None and settings_for(store).price_drop_enabled
