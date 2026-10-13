from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.shortcuts import redirect

from apps.core.ratelimit import ratelimit

from . import referrals


@ratelimit("referral-link", "30/10m", methods=("GET",))
def referral_landing(request, code):
    """لینک دعوت: کد در نشست می‌ماند تا هنگام ساخت حساب تازه، دوست ثبت و کد تخفیفش ساخته شود."""
    ref = referrals.find_code(request.store, code) if referrals.config(request.store) else None
    if ref is not None and not request.user.is_authenticated:
        request.session[referrals.SESSION_KEY] = ref.code
        request.session.set_expiry(60 * 60 * 24 * 30)
        name = ref.user.first_name or "دوستتان"
        messages.info(request, f"{name} شما را دعوت کرده است. با ساخت حساب، کد تخفیف اولین خرید می‌گیرید.")
    return redirect("accounts:register" if ref is not None and not request.user.is_authenticated else "pages:home")


@receiver(user_logged_in)
def _attach_referral(sender, request, user, **kwargs):
    """ثبت‌نام یا اولین ورود پیامکی با نشستی که لینک دعوت دارد ← دوست ثبت می‌شود."""
    code = request.session.pop(referrals.SESSION_KEY, None) if request is not None else None
    store = getattr(request, "store", None)
    if not code or store is None:
        return
    ref = referrals.attach(store, user, code)
    if ref is not None:
        messages.success(request, f"به دعوت دوستتان خوش آمدید! کد تخفیف اولین خرید شما: {ref.friend_coupon}")
