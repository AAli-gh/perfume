"""تنظیمات اجرای تست‌ها (pytest / manage.py test)."""

import tempfile

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # فقط برای سرعت تست
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
MEDIA_ROOT = tempfile.mkdtemp(prefix="majd-test-media-")
ALLOWED_HOSTS = ["testserver", "localhost", ".test"]
LOGGING = {"version": 1, "disable_existing_loggers": False, "root": {"level": "WARNING"}}
PAYMENT_TEST_GATEWAY_ENABLED = True
