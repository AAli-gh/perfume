"""گزارش خطاهای سرور به Sentry (اختیاری؛ فقط وقتی SENTRY_DSN تنظیم شده و sentry-sdk نصب است).

اطلاعات شخصی مشتری (موبایل، ایمیل، آدرس، رمز، کوکی) پیش از ارسال حذف می‌شود؛ از کاربر فقط شناسه می‌رود.
"""

import logging
import re

log = logging.getLogger(__name__)

PHONE_RE = re.compile(r"(?:\+98|0098|0)?9\d{9}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
FILTERED = "[حذف شد]"
# کلیدهایی که مقدارشان هرگز ارسال نمی‌شود (افزون بر فهرست پیش‌فرض Sentry: password، token، cookie، …)
SENSITIVE_KEYS = [
    "phone", "mobile", "email", "address", "postal_code", "first_name", "last_name", "national_code",
    "card", "card_number", "code", "otp", "gift_message", "recipient", "sessionid", "csrftoken", "x-csrftoken",
]


def _scrub_text(value):
    return EMAIL_RE.sub(FILTERED, PHONE_RE.sub(FILTERED, value)) if isinstance(value, str) else value


def _scrub(obj):
    if isinstance(obj, dict):
        return {k: (FILTERED if str(k).lower() in SENSITIVE_KEYS else _scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return _scrub_text(obj)


def before_send(event, hint=None):
    """حذف PII: کاربر فقط با شناسه، بدنه/کوکی درخواست حذف، شماره و ایمیل در متن خطاها پوشانده."""
    user = event.get("user") or {}
    event["user"] = {"id": user["id"]} if user.get("id") else {}
    request = event.get("request")
    if request:
        request.pop("cookies", None)
        request.pop("data", None)
        headers = request.get("headers") or {}
        request["headers"] = {k: v for k, v in headers.items() if k.lower() not in ("cookie", "authorization")}
        if "query_string" in request:
            request["query_string"] = _scrub_text(request["query_string"])
        if "url" in request:
            request["url"] = _scrub_text(request["url"])
    for key in ("message", "logentry", "exception", "breadcrumbs", "extra", "tags", "contexts"):
        if key in event:
            event[key] = _scrub(event[key])
    return event


def init_sentry(env, *, release=""):
    """فراخوانی از تنظیمات production؛ خروجی True اگر Sentry فعال شد."""
    dsn = env("SENTRY_DSN", default="")
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber
    except ImportError:  # pragma: no cover - sentry-sdk در requirements هست
        log.warning("SENTRY_DSN تنظیم شده ولی sentry-sdk نصب نیست؛ گزارش خطا غیرفعال است.")
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=env("SENTRY_ENVIRONMENT", default="production"),
        release=env("SENTRY_RELEASE", default=release) or None,
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
        send_default_pii=False,
        max_request_body_size="never",
        event_scrubber=EventScrubber(denylist=DEFAULT_DENYLIST + SENSITIVE_KEYS, recursive=True),
        before_send=before_send,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    return True
