"""کد ورود یک‌بارمصرف پیامکی.

- کد ۶ رقمی تصادفی (secrets)، فقط hash آن (HMAC با SECRET_KEY) در cache نگه داشته می‌شود.
- اعتبار ۲ دقیقه، حداکثر ۵ تلاش اشتباه؛ پس از ورود موفق کد باطل می‌شود.
- محدودیت ارسال (هر شماره و هر IP) در viewها با rate limit اعمال می‌شود.
"""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.accounts.models import PHONE_ACCOUNT_DOMAIN

TTL_SECONDS = 120
MAX_ATTEMPTS = 5


class OTPError(Exception):
    pass


def _key(store, phone):
    return f"otp:{store.pk}:{phone}"


def _digest(phone, code):
    return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def issue(store, phone):
    code = f"{secrets.randbelow(10**6):06d}"
    cache.set(_key(store, phone), {"digest": _digest(phone, code), "attempts": 0}, TTL_SECONDS)
    return code


def verify(store, phone, code):
    key = _key(store, phone)
    data = cache.get(key)
    if not data:
        raise OTPError("کد منقضی شده است؛ دوباره درخواست کد بدهید.")
    if not hmac.compare_digest(data["digest"], _digest(phone, (code or "").strip())):
        data["attempts"] += 1
        if data["attempts"] >= MAX_ATTEMPTS:
            cache.delete(key)
            raise OTPError("تعداد تلاش‌های اشتباه زیاد بود؛ دوباره درخواست کد بدهید.")
        cache.set(key, data, TTL_SECONDS)
        raise OTPError("کد واردشده درست نیست.")
    cache.delete(key)


def user_for_phone(phone):
    """کاربر فعال با این موبایل؛ اگر نبود ساخته می‌شود. چند حساب با یک شماره ← OTPError (ورود با ایمیل)."""
    User = get_user_model()
    users = list(User.objects.filter(phone=phone)[:2])
    if len(users) > 1:
        raise OTPError("چند حساب با این شماره وجود دارد؛ لطفاً با ایمیل وارد شوید.")
    if users:
        if not users[0].is_active:
            raise OTPError("این حساب کاربری غیرفعال است.")
        return users[0], False
    user = User.objects.create_user(email=f"{phone}@{PHONE_ACCOUNT_DOMAIN}", password=None, phone=phone)
    return user, True
