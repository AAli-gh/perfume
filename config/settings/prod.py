"""تنظیمات محیط عملیاتی (production)."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
PAYMENT_TEST_GATEWAY_ENABLED = False  # درگاه آزمایشی هرگز در production فعال نمی‌شود
if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY باید در متغیرهای محیطی تنظیم شود.")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure") or len(set(SECRET_KEY)) < 5:  # noqa: F405
    raise ImproperlyConfigured(
        "SECRET_KEY ضعیف است (حداقل ۵۰ نویسه تصادفی). بسازید با: "
        "python -c \"import secrets; print(secrets.token_urlsafe(50))\""
    )

STORAGES = {  # noqa: F405
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
# HSTS: مرورگر تا یک سال فقط با HTTPS وصل می‌شود. فقط وقتی کل دامنه HTTPS است فعال بماند.
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
# includeSubDomains و preload تصمیم مالک دامنه است (زیردامنه‌های غیر HTTPS از کار می‌افتند)؛ تا وقتی عمداً
# خاموش‌اند، هشدار check --deploy برایشان ساکت می‌شود تا هشدارهای واقعی دیده شوند.
SILENCED_SYSTEM_CHECKS = (["security.W005"] if not SECURE_HSTS_INCLUDE_SUBDOMAINS else []) + (
    ["security.W021"] if not SECURE_HSTS_PRELOAD else []
)
CSP_UPGRADE_INSECURE = True
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=1)  # nginx در docker-compose
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_HTTPONLY = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
