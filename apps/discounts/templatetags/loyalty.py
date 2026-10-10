from django import template

from apps.discounts import credits

register = template.Library()


@register.simple_tag(takes_context=True)
def loyalty_summary(context):
    """مانده امتیاز کاربر واردشده (یا None اگر باشگاه خاموش است)."""
    request = context.get("request")
    store = getattr(request, "store", None)
    config = credits.loyalty_config(store) if store is not None else None
    if config is None or not request.user.is_authenticated:
        return None
    points = credits.points_balance(store, request.user)
    return {"points": points, "value": points * config.loyalty_point_value, "min": config.loyalty_min_redeem,
            "earn_per": config.loyalty_earn_per}
