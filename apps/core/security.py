"""هدرهای امنیتی پاسخ: Content-Security-Policy (با nonce)، Permissions-Policy و Cross-Origin-*.

CSP:
- اسکریپت فقط از همین دامنه ('self')؛ هیچ اسکریپت inline یا eval مجاز نیست.
- <style> درون‌خطی (توکن‌های پوسته) فقط با nonce همان درخواست: {{ request.csp_nonce }}
- ویژگی style="" مجاز است (style-src-attr) چون قالب‌ها برای تصویر هیرو و … از آن استفاده می‌کنند.
- اپ‌ها منابع اضافه را ثبت می‌کنند (مثلاً درگاه پرداخت برای form-action):  add_source("form-action", "https://…")
- CSP_REPORT_ONLY=True ← فقط گزارش (برای آزمایش قبل از اعمال)
"""

import secrets

from django.conf import settings

BASE_POLICY = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'", "https://fonts.googleapis.com"],
    "style-src-attr": ["'unsafe-inline'"],
    "font-src": ["'self'", "https://fonts.gstatic.com", "data:"],
    "img-src": ["'self'", "data:"],
    "connect-src": ["'self'"],
    "frame-src": ["'self'", "https://www.openstreetmap.org"],  # پیش‌نمایش استودیو و نقشه صفحه تماس
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
}
_extra = {}

PERMISSIONS_POLICY = ", ".join(
    f"{feature}=()" for feature in
    ("camera", "microphone", "geolocation", "payment", "usb", "magnetometer", "gyroscope", "accelerometer",
     "interest-cohort", "browsing-topics")
)


def add_source(directive, *sources):
    """ثبت منبع مجاز اضافه توسط اپ‌ها (در AppConfig.ready)."""
    bucket = _extra.setdefault(directive, [])
    for source in sources:
        if source not in bucket:
            bucket.append(source)


def build_policy(nonce, *, frame_ancestors=None):
    policy = {k: list(v) for k, v in BASE_POLICY.items()}
    for directive, sources in _extra.items():
        policy.setdefault(directive, []).extend(sources)
    for directive, sources in getattr(settings, "CSP_EXTRA_SOURCES", {}).items():
        policy.setdefault(directive, []).extend(sources)
    policy["style-src"].append(f"'nonce-{nonce}'")
    if frame_ancestors:
        policy["frame-ancestors"] = frame_ancestors
    parts = [f"{d} {' '.join(dict.fromkeys(s))}" for d, s in policy.items()]
    if getattr(settings, "CSP_UPGRADE_INSECURE", False):
        parts.append("upgrade-insecure-requests")
    return "; ".join(parts)


class SecurityHeadersMiddleware:
    """باید بعد از middlewareهایی بیاید که X-Frame-Options را تغییر می‌دهند (preview)، یعنی بالاتر در فهرست."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        if getattr(settings, "CSP_ENABLED", True) and "Content-Security-Policy" not in response:
            # پیش‌نمایش استودیو تنها حالتی است که صفحه داخل iframe (همین دامنه) نمایش داده می‌شود
            same_origin = response.get("X-Frame-Options", "").upper() == "SAMEORIGIN"
            header = "Content-Security-Policy-Report-Only" if getattr(settings, "CSP_REPORT_ONLY", False) \
                else "Content-Security-Policy"
            response[header] = build_policy(request.csp_nonce, frame_ancestors=["'self'"] if same_origin else None)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response
