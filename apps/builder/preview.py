"""حالت پیش‌نمایش فروشگاه.

دو راه ورود:
1. کارمند استودیو (session) — با باز کردن صفحه پیش‌نمایش در استودیو فعال می‌شود.
2. لینک امضاشده و موقت (برای نشان دادن به دیگران پیش از انتشار) — فقط دیدن، بدون دسترسی ویرایش.

در حالت پیش‌نمایش:
- request.is_preview = True ← ThemeMiddleware و صفحه اصلی پیش‌نویس را نشان می‌دهند
- پاسخ‌ها cache و index نمی‌شوند و فقط داخل iframe همین دامنه (استودیو) قابل نمایش‌اند
"""

from .access import can_use_studio

SESSION_STAFF = "builder_preview"
SESSION_TOKEN = "builder_preview_token"


def preview_state(request):
    """'staff' | 'link' | None"""
    session = getattr(request, "session", None)
    store = getattr(request, "store", None)
    if session is None or store is None:
        return None
    if session.get(SESSION_STAFF) == store.pk and can_use_studio(request.user):
        return "staff"
    token = session.get(SESSION_TOKEN)
    if token:
        from .services import check_preview_token

        if check_preview_token(token, store):
            return "link"
        session.pop(SESSION_TOKEN, None)  # لینک باطل یا منقضی شده
    return None


def enter_staff_preview(request):
    request.session[SESSION_STAFF] = request.store.pk


def enter_link_preview(request, token):
    request.session[SESSION_TOKEN] = token


def exit_preview(request):
    request.session.pop(SESSION_STAFF, None)
    request.session.pop(SESSION_TOKEN, None)


class PreviewMiddleware:
    """بعد از Session/Auth/Store و قبل از ThemeMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_studio = request.path.startswith("/studio/")
        state = None if is_studio else preview_state(request)
        request.is_preview = state is not None
        request.preview_mode = state
        response = self.get_response(request)
        if request.is_preview:
            response["Cache-Control"] = "private, no-store"
            response["X-Robots-Tag"] = "noindex, nofollow"
            response["X-Frame-Options"] = "SAMEORIGIN"  # برای iframe پیش‌نمایش در استودیو
            vary = response.get("Vary", "")
            if "Cookie" not in vary:
                response["Vary"] = f"{vary}, Cookie" if vary else "Cookie"
        return response
