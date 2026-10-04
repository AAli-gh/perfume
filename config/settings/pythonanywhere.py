"""اجرای نمایشی روی PythonAnywhere (حساب رایگان): SQLite، بدون Redis و Celery worker.

برای فروش واقعی از stack اصلی استفاده کنید (PostgreSQL + Redis + Celery، DEPLOY.md). محدودیت‌های این حالت:
- جستجو: تطبیق متن نرمال‌شده فارسی به‌جای جستجوی تمام‌متن PostgreSQL (apps/core/db.py).
- taskها هم‌زمان در همان درخواست اجرا می‌شوند؛ لغو خودکار سفارش‌های پرداخت‌نشده (beat) اجرا نمی‌شود.
- پیامک و ایمیل فقط در لاگ نوشته می‌شوند (console)، مگر SMS_PROVIDER / EMAIL_URL تنظیم شوند.

متغیرها از فایل .env کنار manage.py خوانده می‌شوند (SECRET_KEY، ALLOWED_HOSTS، CSRF_TRUSTED_ORIGINS، DATABASE_URL).
"""

from .prod import *  # noqa: F401,F403
from .prod import env

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}  # noqa: F405
DATABASES["default"].setdefault("OPTIONS", {})
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    DATABASES["default"]["OPTIONS"].setdefault("timeout", 20)  # چند worker هم‌زمان روی یک فایل SQLite

# cache مشترک بین workerها (rate limit) بدون Redis: جدول دیتابیس (manage.py createcachetable)
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

# HTTPS را خود PythonAnywhere اجباری می‌کند (Force HTTPS در تنظیمات وب‌اپ)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)

if not env("EMAIL_URL", default=""):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SMS_PROVIDER = env("SMS_PROVIDER", default="console")
LOG_FORMAT = env("LOG_FORMAT", default="text")
LOGGING["handlers"]["console"]["formatter"] = LOG_FORMAT  # noqa: F405
# W008: ریدایرکت HTTPS را PythonAnywhere انجام می‌دهد (force_https)، نه Django
SILENCED_SYSTEM_CHECKS = [*SILENCED_SYSTEM_CHECKS, "security.W008"]  # noqa: F405
