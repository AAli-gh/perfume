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


@register.simple_tag(takes_context=True)
def referral_summary(context):
    """کد و لینک دعوت کاربر واردشده و آمار دعوت‌ها (یا None اگر معرفی به دوستان خاموش است)."""
    from django.urls import reverse

    from apps.discounts import referrals
    from apps.discounts.models import Referral

    request = context.get("request")
    store = getattr(request, "store", None)
    conf = referrals.config(store) if store is not None else None
    if conf is None or not request.user.is_authenticated:
        return None
    code = referrals.code_for(store, request.user)
    mine = Referral.objects.filter(store=store, friend=request.user).first()
    return {"code": code.code, "link": request.build_absolute_uri(reverse("referral", args=[code.code])),
            "percent": conf.referral_friend_percent, "points": conf.referral_reward_points if credits.loyalty_config(store) else 0,
            "friend_coupon": mine.friend_coupon if mine else "", **referrals.stats(store, request.user)}
