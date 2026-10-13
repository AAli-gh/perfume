"""معرفی به دوستان.

۱. هر مشتری کد دعوت دارد: لینک /r/<code>/ کد را در نشست بازدیدکننده نگه می‌دارد (۳۰ روز).
۲. وقتی بازدیدکننده با همان نشست حساب تازه بسازد (ثبت‌نام یا ورود پیامکی اول)، Referral ثبت و یک کد تخفیف
   یک‌بارمصرف برای اولین خریدش ساخته می‌شود.
۳. وقتی اولین سفارش دوست «تحویل» شد، معرف امتیاز باشگاه (یا اگر باشگاه خاموش است، کد تخفیف) می‌گیرد.
   پاداش فقط یک بار و فقط برای سفارش تحویل‌شده است، پس لغو و مرجوعی پاداش نمی‌سازند.
"""

import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .credits import ALPHABET, add_points, loyalty_config
from .models import Coupon, LoyaltyEntry, Referral, ReferralCode

SESSION_KEY = "referral_code"
NEW_ACCOUNT_WINDOW = timedelta(minutes=30)
COUPON_DAYS = 30


def config(store):
    conf = getattr(store, "config", None)
    return conf if conf is not None and conf.referral_enabled else None


def code_for(store, user):
    """کد دعوت مشتری (در صورت نبود ساخته می‌شود)."""
    existing = ReferralCode.objects.filter(store=store, user=user).first()
    if existing:
        return existing
    for _ in range(10):
        try:
            with transaction.atomic():
                return ReferralCode.objects.create(store=store, user=user,
                                                   code="".join(secrets.choice(ALPHABET) for _ in range(7)))
        except IntegrityError:
            existing = ReferralCode.objects.filter(store=store, user=user).first()
            if existing:
                return existing
    raise RuntimeError("ساخت کد دعوت ممکن نشد")


def find_code(store, code):
    return ReferralCode.objects.filter(store=store, code=(code or "").strip().upper()[:12]).select_related("user").first()


def _coupon(store, prefix, percent, cap):
    for _ in range(10):
        code = prefix + "".join(secrets.choice(ALPHABET) for _ in range(6))
        if not Coupon.objects.filter(store=store, code=code).exists():
            return Coupon.objects.create(store=store, code=code, percent=percent, max_discount=cap or None,
                                         usage_limit=1, valid_to=timezone.now() + timedelta(days=COUPON_DAYS))
    raise RuntimeError("ساخت کد تخفیف ممکن نشد")


def attach(store, user, code):
    """ثبت دوست دعوت‌شده (فقط حساب تازه و نه خود معرف). خروجی: Referral یا None."""
    conf = config(store)
    ref_code = find_code(store, code) if conf else None
    if (ref_code is None or ref_code.user_id == user.pk or not user.date_joined
            or user.date_joined < timezone.now() - NEW_ACCOUNT_WINDOW
            or Referral.objects.filter(store=store, friend=user).exists()):
        return None
    coupon = _coupon(store, "HI", conf.referral_friend_percent, conf.referral_friend_max)
    try:
        with transaction.atomic():
            return Referral.objects.create(store=store, referrer=ref_code.user, friend=user, friend_coupon=coupon.code)
    except IntegrityError:
        coupon.delete()
        return None


def reward_for_order(order):
    """پس از تحویل سفارش: اگر اولین سفارش تحویل‌شده دوست دعوت‌شده است، معرف پاداش می‌گیرد."""
    if not order.user_id:
        return None
    conf = getattr(order.store, "config", None)
    with transaction.atomic():
        ref = (Referral.objects.select_for_update().select_related("referrer")
               .filter(store=order.store, friend_id=order.user_id, status=Referral.Status.PENDING).first())
        if ref is None or conf is None:
            return None
        if loyalty_config(order.store) is not None and conf.referral_reward_points:
            add_points(order.store, ref.referrer, conf.referral_reward_points, LoyaltyEntry.Reason.REFERRAL,
                       order_number=order.number, note="پاداش معرفی دوست")
            ref.reward_points = conf.referral_reward_points
        else:
            ref.reward_coupon = _coupon(order.store, "TY", conf.referral_friend_percent, conf.referral_friend_max).code
        ref.status, ref.order_number, ref.rewarded_at = Referral.Status.REWARDED, order.number, timezone.now()
        ref.save(update_fields=["status", "order_number", "rewarded_at", "reward_points", "reward_coupon"])
    from .signals import referral_rewarded

    transaction.on_commit(lambda: referral_rewarded.send(sender=Referral, referral=ref))
    return ref


def stats(store, user):
    refs = Referral.objects.filter(store=store, referrer=user)
    return {"invited": refs.count(), "rewarded": refs.filter(status=Referral.Status.REWARDED).count()}
