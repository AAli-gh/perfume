"""محدودیت تعداد درخواست (rate limit) بر پایه cache (Redis در production).

    @ratelimit("login-ip", "20/10m")                          ← بر اساس IP
    @ratelimit("login-account", "5/15m", key=email_of)       ← بر اساس شناسه دلخواه (مثلاً ایمیل)

- پنجره لغزان تقریبی (دو پنجره وزن‌دار)؛ پس از عبور از حد، پاسخ ۴۲۹ با هدر Retry-After (برای HTMX هم یک اعلان نمایش داده می‌شود).
- IP واقعی فقط وقتی از X-Forwarded-For خوانده می‌شود که TRUSTED_PROXY_COUNT تنظیم شده باشد؛ وگرنه
  هر کسی می‌توانست با جعل این هدر محدودیت را دور بزند.
"""

import hashlib
import re
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render

UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
RATE = re.compile(r"^(\d+)/(\d*)([smhd])$")


def parse_rate(rate):
    m = RATE.match(rate)
    if not m:
        raise ValueError(f"invalid rate {rate!r}")
    return int(m.group(1)), int(m.group(2) or 1) * UNITS[m.group(3)]


def client_ip(request):
    remote = request.META.get("REMOTE_ADDR", "")
    proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    if proxies > 0:
        chain = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(chain) >= proxies:
            return chain[-proxies]
    return remote


def hit(scope, ident, limit, period):
    """یک درخواست ثبت می‌کند؛ خروجی (مجاز است؟، ثانیه تا آزاد شدن).

    پنجره لغزان تقریبی: شمارش پنجره قبلی به نسبت زمان باقی‌مانده آن حساب می‌شود. با پنجره ثابت ساده،
    درخواست‌هایی که دو طرف مرز پنجره بیفتند شمارنده را صفر می‌کنند و تا دو برابر حد مجاز عبور می‌کنند.
    """
    now = time.time()
    window, elapsed = int(now // period), (now % period) / period
    digest = hashlib.sha256(f"{scope}:{ident}".encode()).hexdigest()[:32]
    key, previous_key = f"rl:{scope}:{digest}:{window}", f"rl:{scope}:{digest}:{window - 1}"
    ttl = 2 * period + 5  # پنجره جاری باید در پنجره بعدی هم خوانده شود
    if cache.add(key, 1, ttl):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:  # کلید همین الان منقضی شد
            cache.add(key, 1, ttl)
            count = 1
    previous = cache.get(previous_key) or 0
    estimated = previous * (1 - elapsed) + count
    return estimated <= limit, max(1, int(period - (now % period)))


def _identity(request, key):
    if callable(key):
        return key(request)
    if key == "user":
        return f"u{request.user.pk}" if request.user.is_authenticated else client_ip(request)
    return client_ip(request)


def too_many_requests(request, retry_after):
    response = render(request, "429.html", {"retry_after": retry_after}, status=429)
    response["Retry-After"] = str(retry_after)
    return response


def ratelimit(scope, rate, *, key="ip", methods=("POST",)):
    limit, period = parse_rate(rate)

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if getattr(settings, "RATELIMIT_ENABLED", True) and request.method in methods:
                ident = _identity(request, key)
                if ident:
                    allowed, retry = hit(scope, ident, limit, period)
                    if not allowed:
                        from .audit import record

                        record("ratelimit.blocked", request, target=scope, path=request.path)
                        return too_many_requests(request, retry)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
