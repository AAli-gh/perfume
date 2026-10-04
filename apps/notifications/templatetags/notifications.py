from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def otp_login_enabled(context):
    from ..views import otp_enabled

    request = context.get("request")
    store = getattr(request, "store", None)
    return bool(store and otp_enabled(store))
